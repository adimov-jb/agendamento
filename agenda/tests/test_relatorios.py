from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from agenda import relatorios, servicos
from agenda.models import Agendamento, Bloqueio
from core.templatetags.formatos import percentual

from .conftest import hora

pytestmark = pytest.mark.django_db

Origem = Agendamento.Origem


@pytest.fixture
def cenario(ana, bia, segunda, marcar):
    """Na segunda: Ana tem 1 atendido, 1 falta, 1 cancelado e 1 a realizar; Bia tem 1 atendido."""
    depois = hora(segunda, "20:00")

    atendido = marcar(ana, hora(segunda, "09:00"))
    servicos.registrar_presenca(atendido, compareceu=True, agora=depois)
    falta = marcar(ana, hora(segunda, "13:00"))
    servicos.registrar_presenca(falta, compareceu=False, agora=depois)
    servicos.cancelar(marcar(ana, hora(segunda, "14:15")), por=Origem.CLIENTE)
    marcar(ana, hora(segunda, "15:30"))  # continua agendado

    da_bia = marcar(bia, hora(segunda, "10:15"))
    servicos.registrar_presenca(da_bia, compareceu=True, agora=depois)
    return segunda


def test_totais(cenario):
    # "agora" antes da segunda: o agendado ainda está por vir
    r = relatorios.gerar(cenario, cenario, agora=hora(cenario, "08:00"))
    t = r["totais"]
    assert t["total"] == 5
    assert (t["atendidos"], t["faltas"], t["cancelados"], t["a_realizar"], t["sem_registro"]) == (2, 1, 1, 1, 0)
    assert t["realizado"] == Decimal("300.00")  # 2 × 150
    assert t["previsto"] == Decimal("450.00")  # + o agendado
    assert t["taxa_faltas"] == pytest.approx(1 / 3)


def test_agendado_que_ja_passou_fica_sem_registro(cenario):
    t = relatorios.gerar(cenario, cenario, agora=hora(cenario, "20:00"))["totais"]
    assert (t["a_realizar"], t["sem_registro"]) == (0, 1)


def test_por_profissional(cenario, ana, bia):
    linhas = {l["profissional__nome"]: l for l in relatorios.gerar(cenario, cenario)["por_profissional"]}
    assert linhas["Ana"]["total"] == 4
    assert linhas["Ana"]["taxa_faltas"] == 0.5
    assert linhas["Bia"]["atendidos"] == 1
    assert linhas["Bia"]["taxa_faltas"] == 0


def test_profissional_quebrado_por_data(cenario, ana, marcar):
    semana_seguinte = cenario + timedelta(days=7)
    marcar(ana, hora(semana_seguinte, "09:00"))
    linhas = {l["profissional__nome"]: l for l in relatorios.gerar(cenario, semana_seguinte)["por_profissional"]}

    dias_da_ana = [(d["dia"], d["total"], d["previsto"]) for d in linhas["Ana"]["dias"]]
    assert dias_da_ana == [(cenario, 4, Decimal("300.00")), (semana_seguinte, 1, Decimal("150.00"))]
    assert linhas["Ana"]["dias"][0]["taxa_faltas"] == 0.5
    assert [d["dia"] for d in linhas["Bia"]["dias"]] == [cenario]


def test_filtro_por_profissional(cenario, bia):
    r = relatorios.gerar(cenario, cenario, profissional=bia)
    assert r["totais"]["total"] == 1
    assert [l["profissional__nome"] for l in r["por_profissional"]] == ["Bia"]


def test_periodo_fora_nao_conta(cenario):
    dia_seguinte = cenario + timedelta(days=1)
    assert relatorios.gerar(dia_seguinte, dia_seguinte)["totais"]["total"] == 0
    assert relatorios.gerar(dia_seguinte, dia_seguinte)["totais"]["taxa_faltas"] is None


def test_clientes_faltosos(cenario):
    r = relatorios.gerar(cenario, cenario)
    assert [(c["cliente__nome"], c["faltas"], c["atendidos"]) for c in r["clientes_faltosos"]] == [("Carla", 1, 2)]


def test_precisa_reagendar_fica_fora_do_previsto(cenario, ana):
    bloqueio = Bloqueio.objects.create(profissional=ana, inicio=hora(cenario, "15:00"), fim=hora(cenario, "18:00"))
    servicos.aplicar_bloqueio(bloqueio)
    t = relatorios.gerar(cenario, cenario)["totais"]
    assert t["reagendar"] == 1
    assert t["previsto"] == Decimal("300.00")


def test_preco_do_momento_do_agendamento(cenario, limpeza):
    limpeza.preco = 999
    limpeza.save()
    assert relatorios.gerar(cenario, cenario)["totais"]["realizado"] == Decimal("300.00")


@pytest.mark.parametrize("fracao,texto", [(None, "—"), (0, "0%"), (0.5, "50%"), (1 / 3, "33,3%"), (1, "100%")])
def test_filtro_percentual(fracao, texto):
    assert percentual(fracao) == texto


# Tela


def test_tela_exige_gerente(client, ana):
    client.force_login(ana.usuario)
    assert client.get(reverse("agenda:gerente_relatorios")).status_code == 403


def test_tela_padrao_e_o_mes_atual(cliente_gerente):
    response = cliente_gerente.get(reverse("agenda:gerente_relatorios"))
    inicio, fim = response.context["periodo"]
    assert inicio.day == 1 and inicio.month == fim.month and (fim + timedelta(days=1)).day == 1


def test_tela_com_filtros(cliente_gerente, cenario, ana):
    response = cliente_gerente.get(
        reverse("agenda:gerente_relatorios"),
        {"inicio": cenario.isoformat(), "fim": cenario.isoformat(), "profissional": ana.pk},
    )
    html = response.content.decode()
    assert response.context["relatorio"]["totais"]["total"] == 4
    assert "R$ 150,00" in html  # realizado da Ana
    assert "50%" in html
    assert "Carla" in html and "(11) 99999-8888" in html


def test_profissional_ve_so_o_proprio_relatorio(client, cenario, ana, bia):
    client.force_login(ana.usuario)
    url = reverse("agenda:relatorio")
    periodo = {"inicio": cenario.isoformat(), "fim": cenario.isoformat()}

    response = client.get(url, periodo)
    assert response.status_code == 200
    assert response.context["relatorio"]["totais"]["total"] == 4  # a Bia tem mais 1 no dia
    assert [l["profissional__nome"] for l in response.context["relatorio"]["por_profissional"]] == ["Ana"]
    html = response.content.decode()
    assert "Meu relatório" in html and 'name="profissional"' not in html

    # Tentar filtrar outro profissional pela URL não muda nada
    assert client.get(url, {**periodo, "profissional": bia.pk}).context["relatorio"]["totais"]["total"] == 4


def test_relatorio_do_profissional_exige_perfil_profissional(cliente_gerente):
    assert cliente_gerente.get(reverse("agenda:relatorio")).status_code == 403


def test_tela_periodo_invertido(cliente_gerente, cenario):
    response = cliente_gerente.get(
        reverse("agenda:gerente_relatorios"),
        {"inicio": cenario.isoformat(), "fim": (cenario - timedelta(days=1)).isoformat()},
    )
    assert "A data final deve ser igual ou posterior à inicial." in response.content.decode()
    assert "relatorio" not in response.context
