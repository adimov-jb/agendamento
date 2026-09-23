from datetime import time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from agenda import servicos
from agenda.models import Agendamento, AgendamentoRecurso, Bloqueio, Cliente
from agenda.telefone import normalizar_telefone
from catalogo.models import Procedimento
from clinica.models import HorarioClinica
from core.templatetags.formatos import telefone

from .conftest import dar_expediente, hora

pytestmark = pytest.mark.django_db

Status = Agendamento.Status


def livres(profissional, procedimento, data, **kwargs):
    kwargs.setdefault("respeitar_antecedencia", False)
    return [f"{h:%H:%M}" for h in servicos.horarios_disponiveis(profissional, procedimento, data, **kwargs)]


# Disponibilidade


def test_expediente_respeita_horario_da_clinica(ana, segunda):
    HorarioClinica.objects.filter(dia_semana=0).update(inicio=time(10), fim=time(17))
    periodos = [(f"{a:%H:%M}", f"{b:%H:%M}") for a, b in servicos.expediente(ana, segunda)]
    assert periodos == [("10:00", "12:00"), ("13:00", "17:00")]


def test_clinica_fechada_nao_tem_horarios(ana, segunda):
    HorarioClinica.objects.filter(dia_semana=0).delete()
    assert livres(ana, ana.procedimentos.get(), segunda) == []


def test_horarios_cabem_com_intervalo(ana, limpeza, segunda):
    horarios = livres(ana, limpeza, segunda)
    # 60 min + 15 de intervalo precisam caber: manhã até 10:45, tarde até 16:45
    assert horarios[0] == "09:00"
    assert "10:45" in horarios and "11:00" not in horarios
    assert "13:00" in horarios and "16:45" in horarios and "17:00" not in horarios


def test_grade_alinha_os_horarios(profissional, limpeza, clinica_aberta, segunda):
    profissional.procedimentos.add(limpeza)
    dar_expediente(profissional, (time(9, 10), time(12)))
    assert livres(profissional, limpeza, segunda)[0] == "09:15"


def test_agendamento_ocupa_duracao_mais_intervalo(ana, limpeza, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    horarios = livres(ana, limpeza, segunda)
    assert "09:00" not in horarios and "10:00" not in horarios
    assert "10:15" in horarios


def test_bloqueio_do_profissional_e_geral(ana, limpeza, segunda):
    Bloqueio.objects.create(profissional=ana, inicio=hora(segunda, "09:00"), fim=hora(segunda, "12:00"))
    assert "09:00" not in livres(ana, limpeza, segunda)
    assert "13:00" in livres(ana, limpeza, segunda)

    Bloqueio.objects.create(profissional=None, inicio=hora(segunda, "00:00"), fim=hora(segunda + timedelta(days=1), "00:00"))
    assert livres(ana, limpeza, segunda) == []


def test_recurso_compartilhado_entre_profissionais(ana, bia, limpeza, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    # Só existe uma sala: Bia não pode usar no mesmo período
    horarios_bia = livres(bia, limpeza, segunda)
    assert "09:00" not in horarios_bia
    assert "10:15" in horarios_bia


def test_recurso_inativo_nao_conta(ana, limpeza, sala, segunda):
    sala.recursos.update(ativo=False)
    assert livres(ana, limpeza, segunda) == []


def test_antecedencia_minima_e_maxima(ana, limpeza, segunda):
    agora = hora(segunda, "08:00")
    horarios = livres(ana, limpeza, segunda, respeitar_antecedencia=True, agora=agora)
    assert horarios[0] == "10:00"  # mínimo de 2h

    longe = segunda + timedelta(days=63)  # também segunda-feira, além dos 60 dias
    assert livres(ana, limpeza, longe, respeitar_antecedencia=True, agora=agora) == []
    assert livres(ana, limpeza, longe, respeitar_antecedencia=False, agora=agora) != []


# Agendar, remarcar, cancelar


def test_agendar_copia_dados_e_aloca_sala(ana, limpeza, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    assert agendamento.fim == hora(segunda, "10:15")
    assert agendamento.fim_atendimento == hora(segunda, "10:00")
    assert agendamento.preco == 150
    assert [r.nome for r in agendamento.recursos.all()] == ["Sala 1"]

    # Mudar o procedimento depois não altera o agendamento
    Procedimento.objects.filter(pk=limpeza.pk).update(preco=200)
    agendamento.refresh_from_db()
    assert agendamento.preco == 150


def test_agendar_horario_ocupado_falha(ana, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    with pytest.raises(servicos.AgendamentoInvalido):
        marcar(ana, hora(segunda, "09:30"))


def test_agendar_fora_da_grade_falha(ana, segunda, marcar):
    with pytest.raises(servicos.AgendamentoInvalido):
        marcar(ana, hora(segunda, "09:07"))


def test_procedimento_que_o_profissional_nao_faz(ana, limpeza, segunda, marcar):
    ana.procedimentos.remove(limpeza)
    with pytest.raises(servicos.AgendamentoInvalido, match="não realiza"):
        marcar(ana, hora(segunda, "09:00"))


def test_banco_impede_sobreposicao(ana, limpeza, cliente, segunda, marcar):
    existente = marcar(ana, hora(segunda, "09:00"))
    with pytest.raises(IntegrityError):
        Agendamento.objects.create(
            cliente=cliente,
            profissional=ana,
            procedimento=limpeza,
            inicio=existente.inicio + timedelta(minutes=30),
            fim=existente.fim + timedelta(minutes=30),
            duracao_minutos=60,
            intervalo_minutos=15,
            preco=150,
            origem="profissional",
        )


def test_banco_impede_sala_em_dobro(ana, bia, segunda, marcar):
    de_ana = marcar(ana, hora(segunda, "09:00"))
    de_bia = marcar(bia, hora(segunda, "10:15"))
    with pytest.raises(IntegrityError):
        AgendamentoRecurso.objects.create(
            agendamento=de_bia, recurso=de_ana.recursos.get(), inicio=de_ana.inicio, fim=de_ana.fim
        )


def test_remarcar_pode_sobrepor_o_proprio_horario(ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    servicos.reagendar(agendamento, hora(segunda, "09:30"))
    agendamento.refresh_from_db()
    assert agendamento.inicio == hora(segunda, "09:30")
    assert AgendamentoRecurso.objects.get().inicio == hora(segunda, "09:30")


def test_remarcar_para_horario_ocupado_falha(ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    marcar(ana, hora(segunda, "13:00"))
    with pytest.raises(servicos.AgendamentoInvalido):
        servicos.reagendar(agendamento, hora(segunda, "13:30"))
    agendamento.refresh_from_db()
    assert agendamento.inicio == hora(segunda, "09:00")


def test_cancelar_libera_horario_e_sala(ana, bia, limpeza, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    servicos.cancelar(agendamento, por=Agendamento.Origem.CLIENTE)

    agendamento.refresh_from_db()
    assert agendamento.status == Status.CANCELADO
    assert agendamento.cancelado_por == "cliente"
    assert "09:00" in livres(bia, limpeza, segunda)
    with pytest.raises(servicos.AgendamentoInvalido):
        servicos.cancelar(agendamento, por=Agendamento.Origem.CLIENTE)


def test_presenca_so_depois_do_horario(ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    with pytest.raises(servicos.AgendamentoInvalido):
        servicos.registrar_presenca(agendamento, compareceu=True)

    servicos.registrar_presenca(agendamento, compareceu=False, agora=hora(segunda, "09:30"))
    assert agendamento.status == Status.FALTOU
    servicos.registrar_presenca(agendamento, compareceu=True, agora=hora(segunda, "09:30"))
    assert agendamento.status == Status.ATENDIDO


# Bloqueios e mudanças de expediente


def test_bloqueio_sinaliza_agendamentos_do_periodo(ana, bia, segunda, marcar):
    manha = marcar(ana, hora(segunda, "09:00"))
    tarde = marcar(ana, hora(segunda, "14:00"))
    de_bia = marcar(bia, hora(segunda, "10:15"))

    bloqueio = Bloqueio.objects.create(profissional=ana, inicio=hora(segunda, "08:00"), fim=hora(segunda, "12:00"))
    assert servicos.aplicar_bloqueio(bloqueio) == 1

    manha.refresh_from_db(), tarde.refresh_from_db(), de_bia.refresh_from_db()
    assert manha.status == Status.PRECISA_REAGENDAR
    assert not manha.alocacoes.exists()
    assert tarde.status == Status.AGENDADO
    assert de_bia.status == Status.AGENDADO


def test_bloqueio_geral_afeta_todos(ana, bia, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    marcar(bia, hora(segunda, "10:15"))
    bloqueio = Bloqueio.objects.create(inicio=hora(segunda, "00:00"), fim=hora(segunda + timedelta(days=1), "00:00"))
    assert servicos.aplicar_bloqueio(bloqueio) == 2


def test_agendamento_sinalizado_pode_ser_remarcado(ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    bloqueio = Bloqueio.objects.create(profissional=ana, inicio=hora(segunda, "09:00"), fim=hora(segunda, "12:00"))
    servicos.aplicar_bloqueio(bloqueio)
    agendamento.refresh_from_db()

    servicos.reagendar(agendamento, hora(segunda, "13:00"))
    assert agendamento.status == Status.AGENDADO
    assert agendamento.alocacoes.count() == 1


def test_mudar_expediente_sinaliza_quem_ficou_fora(ana, segunda, marcar):
    manha = marcar(ana, hora(segunda, "09:00"))
    tarde = marcar(ana, hora(segunda, "14:00"))
    ana.horarios.filter(inicio=time(9)).delete()  # deixa de atender de manhã

    assert servicos.sinalizar_fora_do_expediente(ana) == 1
    manha.refresh_from_db(), tarde.refresh_from_db()
    assert manha.status == Status.PRECISA_REAGENDAR
    assert tarde.status == Status.AGENDADO


# Cliente e telefone


def test_cliente_identificado_pelo_telefone(cliente):
    mesmo = servicos.obter_cliente("Carla Souza", "+5511999998888", data_nascimento=segunda_de_1990())
    assert mesmo.pk == cliente.pk
    assert mesmo.nome == "Carla"  # nome existente é mantido
    assert mesmo.data_nascimento == segunda_de_1990()  # nascimento é completado
    assert Cliente.objects.count() == 1


def segunda_de_1990():
    from datetime import date

    return date(1990, 1, 1)


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("(11) 99999-8888", "+5511999998888"),
        ("11 3333-4444", "+551133334444"),
        ("+55 21 98888-7777", "+5521988887777"),
    ],
)
def test_normalizar_telefone(entrada, esperado):
    assert normalizar_telefone(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "99999-8888", "+1 555 123 4567"])
def test_telefone_invalido(entrada):
    with pytest.raises(ValidationError):
        normalizar_telefone(entrada)


def test_filtro_telefone():
    assert telefone("+5511999998888") == "(11) 99999-8888"
    assert telefone("+551133334444") == "(11) 3333-4444"
