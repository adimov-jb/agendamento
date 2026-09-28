"""Cada estabelecimento só enxerga os próprios dados: agenda, clientes, bloqueios e área do cliente."""

from datetime import time, timedelta

import pytest
from django.urls import reverse

from agenda import servicos
from agenda.models import Agendamento, Bloqueio
from catalogo.models import Procedimento
from clinica.models import HorarioFuncionamento
from equipe.models import Profissional

from .conftest import dar_expediente, hora

pytestmark = pytest.mark.django_db


@pytest.fixture
def zeca(django_user_model, outro_estabelecimento):
    """Barbeiro da Barbearia do Zé, que atende às segundas das 9 às 18 e faz corte (sem recursos)."""
    for dia in range(5):
        HorarioFuncionamento.objects.create(
            estabelecimento=outro_estabelecimento, dia_semana=dia, inicio=time(8), fim=time(20)
        )
    usuario = django_user_model.objects.create_user("zeca@ze.com", "zeca@ze.com", "x")
    zeca = Profissional.objects.create(usuario=usuario, estabelecimento=outro_estabelecimento, nome="Zeca")
    corte = Procedimento.objects.create(estabelecimento=outro_estabelecimento, nome="Corte", duracao_minutos=30, preco=50)
    zeca.procedimentos.add(corte)
    dar_expediente(zeca, (time(9), time(18)))
    return zeca


@pytest.fixture
def corte_do_zeca(zeca, segunda):
    cliente = servicos.obter_cliente(zeca.estabelecimento, "Carla", "+5511999998888")
    return servicos.agendar(
        cliente=cliente,
        profissional=zeca,
        procedimento=zeca.procedimentos.get(),
        inicio=hora(segunda, "09:00"),
        origem=Agendamento.Origem.CLIENTE,
        respeitar_antecedencia=False,
    )


def test_mesmo_telefone_e_outro_cliente_em_outro_estabelecimento(cliente, corte_do_zeca):
    assert corte_do_zeca.cliente != cliente
    assert corte_do_zeca.cliente.telefone == cliente.telefone
    assert corte_do_zeca.estabelecimento == corte_do_zeca.profissional.estabelecimento


def test_nao_agenda_cliente_de_outro_estabelecimento(cliente, zeca, segunda):
    with pytest.raises(servicos.AgendamentoInvalido, match="estabelecimentos diferentes"):
        servicos.agendar(
            cliente=cliente,
            profissional=zeca,
            procedimento=zeca.procedimentos.get(),
            inicio=hora(segunda, "10:00"),
            origem=Agendamento.Origem.GERENTE,
            respeitar_antecedencia=False,
        )


def test_nao_remarca_para_profissional_de_outro_estabelecimento(ana, zeca, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    with pytest.raises(servicos.AgendamentoInvalido):
        servicos.reagendar(agendamento, hora(segunda, "15:00"), profissional=zeca)


def test_fechamento_vale_so_para_o_proprio_estabelecimento(ana, zeca, limpeza, segunda, corte_do_zeca, marcar):
    marcar(ana, hora(segunda, "13:00"))
    fechamento = Bloqueio.objects.create(
        estabelecimento=ana.estabelecimento, inicio=hora(segunda, "00:00"), fim=hora(segunda + timedelta(days=1), "00:00")
    )
    assert servicos.aplicar_bloqueio(fechamento) == 1
    corte_do_zeca.refresh_from_db()
    assert corte_do_zeca.status == Agendamento.Status.AGENDADO
    assert servicos.horarios_disponiveis(zeca, zeca.procedimentos.get(), segunda, respeitar_antecedencia=False)


def test_horario_de_funcionamento_e_do_estabelecimento_do_profissional(ana, zeca, segunda):
    ana.estabelecimento.horarios.filter(dia_semana=0).delete()  # clínica fecha às segundas
    assert servicos.expediente(ana, segunda) == []
    assert servicos.expediente(zeca, segunda)


def test_gerente_so_ve_o_proprio_estabelecimento(cliente_gerente, ana, zeca, segunda, corte_do_zeca, marcar):
    marcar(ana, hora(segunda, "09:00"))
    servicos.aplicar_bloqueio(
        Bloqueio.objects.create(
            estabelecimento=zeca.estabelecimento, profissional=zeca, inicio=hora(segunda, "08:00"), fim=hora(segunda, "12:00")
        )
    )

    html = cliente_gerente.get(reverse("agenda:gerente_dia"), {"data": segunda.isoformat()}).content.decode()
    assert "Ana" in html and "Zeca" not in html
    assert "1 agendamento" in html
    assert cliente_gerente.get(reverse("agenda:gerente_pendencias")).context["pendencias"] == 0
    assert cliente_gerente.get(reverse("agenda:detalhe", args=[corte_do_zeca.pk])).status_code == 404
    assert cliente_gerente.post(reverse("agenda:cancelar", args=[corte_do_zeca.pk])).status_code == 404

    relatorio = cliente_gerente.get(
        reverse("agenda:gerente_relatorios"), {"inicio": segunda.isoformat(), "fim": segunda.isoformat()}
    ).context["relatorio"]
    assert relatorio["totais"]["total"] == 1


def test_gerente_nao_agenda_com_profissional_de_outro_estabelecimento(cliente_gerente, ana, zeca, segunda):
    response = cliente_gerente.get(reverse("agenda:gerente_novo"), {"profissional": zeca.pk})
    assert response.context.get("form") is None  # só oferece os profissionais da clínica
    assert list(response.context["profissionais"]) == [ana]

    params = {"profissional": zeca.pk, "procedimento": zeca.procedimentos.get().pk, "data": segunda.isoformat()}
    # Profissional de fora é ignorado; o gerente não é profissional na clínica, então não há agenda a mostrar
    assert cliente_gerente.get(reverse("agenda:horarios_livres"), params).status_code == 403


def test_fechamento_de_outro_estabelecimento_nao_aparece_nem_e_removido(cliente_gerente, zeca, segunda):
    alheio = Bloqueio.objects.create(
        estabelecimento=zeca.estabelecimento, inicio=hora(segunda, "00:00"), fim=hora(segunda + timedelta(days=1), "00:00")
    )
    assert not cliente_gerente.get(reverse("agenda:gerente_bloqueios")).context["bloqueios"]
    assert cliente_gerente.post(reverse("agenda:gerente_excluir_bloqueio", args=[alheio.pk])).status_code == 404


# Área do cliente


def test_pagina_inicial_lista_os_estabelecimentos(client, ana, zeca):
    html = client.get(reverse("core:home")).content.decode()
    assert "Clínica Bella" in html and "Barbearia do Zé" in html
    assert reverse("publico:inicio", args=["ze"]) in html


def test_com_um_so_estabelecimento_vai_direto_para_ele(client, ana):
    assert client.get(reverse("core:home")).url == reverse("publico:inicio", args=["bella"])


def test_cada_estabelecimento_mostra_os_proprios_procedimentos(client, ana, zeca, limpeza):
    html = client.get(reverse("publico:inicio", args=["ze"])).content.decode()
    assert "Corte" in html and "Limpeza de pele" not in html
    assert "Barbearia do Zé" in html
    # Procedimento de um estabelecimento não abre no endereço do outro
    assert client.get(reverse("publico:reservar", args=["ze", limpeza.pk])).status_code == 404


def test_estabelecimento_inexistente(client):
    assert client.get("/nao-existe/").status_code == 404


def test_cliente_identificado_em_um_nao_esta_no_outro(client, ana, zeca, cliente, corte_do_zeca):
    from datetime import date

    cliente.data_nascimento = date(1990, 5, 20)
    cliente.save()
    client.post(reverse("publico:meus", args=["bella"]), {"telefone": "(11) 99999-8888", "data_nascimento": "1990-05-20"})
    assert "Olá, Carla" in client.get(reverse("publico:meus", args=["bella"])).content.decode()
    # Na barbearia a Carla (sem data de nascimento lá) ainda precisa se identificar
    assert "Informe o telefone" in client.get(reverse("publico:meus", args=["ze"])).content.decode()
    assert client.post(reverse("publico:cancelar", args=["bella", corte_do_zeca.pk])).status_code == 404


def test_links_antigos_redirecionam(client, ana, limpeza):
    assert client.get(f"/agendar/{limpeza.pk}/").url == reverse("publico:reservar", args=["bella", limpeza.pk])
    assert client.get("/meus-agendamentos/").url == reverse("publico:meus", args=["bella"])
