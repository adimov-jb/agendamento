from datetime import time, timedelta

import pytest
from django.urls import reverse

from agenda.models import Agendamento, Bloqueio, Cliente, HorarioTrabalho

from .conftest import hora

pytestmark = pytest.mark.django_db

Status = Agendamento.Status


@pytest.fixture
def cliente_ana(client, ana):
    client.force_login(ana.usuario)
    return client


def test_painel_leva_profissional_para_agenda(cliente_ana):
    assert cliente_ana.get(reverse("core:painel")).url == reverse("agenda:dia")


def test_agenda_exige_profissional(cliente_gerente):
    assert cliente_gerente.get(reverse("agenda:dia")).status_code == 403


def test_agenda_do_dia_e_da_semana(cliente_ana, ana, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    html = cliente_ana.get(reverse("agenda:dia"), {"data": segunda.isoformat()}).content.decode()
    assert "Carla" in html and "09:00–10:00" in html
    assert "Expediente: 09:00–12:00, 13:00–18:00" in html

    html = cliente_ana.get(reverse("agenda:semana"), {"data": segunda.isoformat()}).content.decode()
    assert "Carla" in html


def test_horarios_livres_htmx(cliente_ana, limpeza, segunda):
    response = cliente_ana.get(
        reverse("agenda:horarios_livres"), {"procedimento": limpeza.pk, "data": segunda.isoformat()}
    )
    html = response.content.decode()
    assert hora(segunda, "09:00").isoformat() in html
    assert ">09:00<" in html


def test_horarios_livres_com_parametros_invalidos(cliente_ana):
    response = cliente_ana.get(reverse("agenda:horarios_livres"), {"procedimento": "abc", "data": "ontem"})
    assert response.status_code == 200
    assert "Escolha o procedimento" in response.content.decode()


def dados_novo(limpeza, inicio, **extra):
    dados = {
        "procedimento": limpeza.pk,
        "data": inicio.date().isoformat(),
        "inicio": inicio.isoformat(),
        "nome": "Daniela",
        "telefone": "(21) 98888-7777",
        "data_nascimento": "",
    }
    dados.update(extra)
    return dados


def test_novo_agendamento(cliente_ana, ana, limpeza, segunda):
    response = cliente_ana.post(reverse("agenda:novo"), dados_novo(limpeza, hora(segunda, "13:00")))
    assert response.status_code == 302

    agendamento = Agendamento.objects.get()
    assert agendamento.profissional == ana
    assert agendamento.origem == Agendamento.Origem.PROFISSIONAL
    assert agendamento.cliente.telefone == "+5521988887777"


def test_novo_agendamento_em_horario_ocupado(cliente_ana, ana, limpeza, segunda, marcar):
    marcar(ana, hora(segunda, "13:00"))
    response = cliente_ana.post(reverse("agenda:novo"), dados_novo(limpeza, hora(segunda, "13:30")))
    assert response.status_code == 200
    assert "não está mais disponível" in response.content.decode()
    assert Agendamento.objects.count() == 1
    assert not Cliente.objects.filter(nome="Daniela").exists()  # tudo desfeito


def test_novo_agendamento_exige_horario(cliente_ana, limpeza, segunda):
    dados = dados_novo(limpeza, hora(segunda, "13:00"))
    dados["inicio"] = ""
    response = cliente_ana.post(reverse("agenda:novo"), dados)
    assert "Escolha um horário." in response.content.decode()


def test_detalhe_de_outro_profissional_nao_aparece(client, bia, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    client.force_login(bia.usuario)
    assert client.get(reverse("agenda:detalhe", args=[agendamento.pk])).status_code == 404
    assert client.post(reverse("agenda:cancelar", args=[agendamento.pk])).status_code == 404


def test_gerente_ve_qualquer_agendamento(cliente_gerente, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    assert cliente_gerente.get(reverse("agenda:detalhe", args=[agendamento.pk])).status_code == 200


def test_remarcar(cliente_ana, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    nova = hora(segunda, "15:00")
    response = cliente_ana.post(
        reverse("agenda:remarcar", args=[agendamento.pk]), {"data": segunda.isoformat(), "inicio": nova.isoformat()}
    )
    assert response.status_code == 302
    agendamento.refresh_from_db()
    assert agendamento.inicio == nova


def test_cancelar_pelo_profissional(cliente_ana, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    cliente_ana.post(reverse("agenda:cancelar", args=[agendamento.pk]))
    agendamento.refresh_from_db()
    assert agendamento.status == Status.CANCELADO
    assert agendamento.cancelado_por == "profissional"


def test_presenca_antes_do_horario_mostra_erro(cliente_ana, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    response = cliente_ana.post(reverse("agenda:presenca", args=[agendamento.pk]), {"compareceu": "1"}, follow=True)
    assert "depois do horário marcado" in response.content.decode()
    agendamento.refresh_from_db()
    assert agendamento.status == Status.AGENDADO


def dados_horarios(dias):
    """dias: {0: [("09:00","12:00"), ("13:00","18:00")], ...}"""
    dados = {}
    for dia in range(7):
        periodos = dias.get(dia, [])
        if periodos:
            dados[f"dia{dia}-trabalha"] = "on"
        for i, (inicio, fim) in enumerate(periodos, start=1):
            dados[f"dia{dia}-inicio{i}"] = inicio
            dados[f"dia{dia}-fim{i}"] = fim
    return dados


def test_salvar_horarios(cliente_ana, ana):
    response = cliente_ana.post(
        reverse("agenda:horarios"), dados_horarios({1: [("08:00", "12:00"), ("14:00", "19:00")]})
    )
    assert response.status_code == 302
    periodos = list(ana.horarios.values_list("dia_semana", "inicio", "fim"))
    assert periodos == [(1, time(8), time(12)), (1, time(14), time(19))]


def test_horarios_fora_da_clinica(cliente_ana, ana):
    response = cliente_ana.post(reverse("agenda:horarios"), dados_horarios({0: [("07:00", "12:00")]}))
    assert "Fora do horário da clínica" in response.content.decode()
    response = cliente_ana.post(reverse("agenda:horarios"), dados_horarios({6: [("09:00", "12:00")]}))
    assert "A clínica não abre neste dia." in response.content.decode()
    assert ana.horarios.count() == 2  # nada mudou


def test_horarios_periodos_sobrepostos(cliente_ana):
    response = cliente_ana.post(
        reverse("agenda:horarios"), dados_horarios({0: [("09:00", "12:00"), ("11:00", "18:00")]})
    )
    assert "O segundo período deve começar depois do fim do primeiro." in response.content.decode()


def test_mudar_horarios_sinaliza_agendamentos(cliente_ana, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    response = cliente_ana.post(reverse("agenda:horarios"), dados_horarios({0: [("13:00", "18:00")]}), follow=True)
    assert "precisam ser reagendados" in response.content.decode()
    agendamento.refresh_from_db()
    assert agendamento.status == Status.PRECISA_REAGENDAR


def test_bloquear_dia_inteiro(cliente_ana, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    response = cliente_ana.post(
        reverse("agenda:bloqueios"), {"data_inicio": segunda.isoformat(), "motivo": "Consulta médica"}, follow=True
    )
    assert "(dia inteiro)" in response.content.decode()

    bloqueio = Bloqueio.objects.get()
    assert bloqueio.inicio == hora(segunda, "00:00")
    assert bloqueio.fim == hora(segunda + timedelta(days=1), "00:00")
    agendamento.refresh_from_db()
    assert agendamento.status == Status.PRECISA_REAGENDAR


def test_bloqueio_com_fim_antes_do_inicio(cliente_ana, segunda):
    response = cliente_ana.post(
        reverse("agenda:bloqueios"),
        {"data_inicio": segunda.isoformat(), "hora_inicio": "15:00", "hora_fim": "10:00"},
    )
    assert "O fim do bloqueio deve ser depois do início." in response.content.decode()
    assert not Bloqueio.objects.exists()


def test_excluir_bloqueio_apenas_o_proprio(cliente_ana, ana, bia, segunda):
    meu = Bloqueio.objects.create(profissional=ana, inicio=hora(segunda, "09:00"), fim=hora(segunda, "10:00"))
    alheio = Bloqueio.objects.create(profissional=bia, inicio=hora(segunda, "09:00"), fim=hora(segunda, "10:00"))
    geral = Bloqueio.objects.create(inicio=hora(segunda, "09:00"), fim=hora(segunda, "10:00"))

    assert cliente_ana.post(reverse("agenda:excluir_bloqueio", args=[alheio.pk])).status_code == 404
    assert cliente_ana.post(reverse("agenda:excluir_bloqueio", args=[geral.pk])).status_code == 404
    cliente_ana.post(reverse("agenda:excluir_bloqueio", args=[meu.pk]))
    assert set(Bloqueio.objects.values_list("pk", flat=True)) == {alheio.pk, geral.pk}


def test_mudar_horario_da_clinica_sinaliza_agendamentos(cliente_gerente, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    dados = {
        "nome_clinica": "Clínica",
        "grade_minutos": "15",
        "antecedencia_minima_horas": "2",
        "antecedencia_maxima_dias": "60",
    }
    for dia in range(5):
        dados.update({f"dia{dia}-aberto": "on", f"dia{dia}-inicio": "12:00", f"dia{dia}-fim": "20:00"})
    response = cliente_gerente.post(reverse("clinica:configuracoes"), dados, follow=True)
    assert "fora do horário da clínica" in response.content.decode()
    agendamento.refresh_from_db()
    assert agendamento.status == Status.PRECISA_REAGENDAR
    assert HorarioTrabalho.objects.filter(profissional=ana).count() == 2  # horários do profissional não mudam
