from datetime import timedelta

import pytest
from django.urls import reverse

from agenda import servicos
from agenda.models import Agendamento, Bloqueio

from .conftest import hora

pytestmark = pytest.mark.django_db

Status = Agendamento.Status


@pytest.mark.parametrize(
    "rota", ["agenda:gerente_dia", "agenda:gerente_semana", "agenda:gerente_novo", "agenda:gerente_pendencias", "agenda:gerente_bloqueios"]
)
def test_area_do_gerente_bloqueada_para_profissional(client, ana, rota):
    client.force_login(ana.usuario)
    assert client.get(reverse(rota)).status_code == 403


def test_agenda_do_dia_com_todos(cliente_gerente, ana, bia, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    marcar(bia, hora(segunda, "10:15"))
    html = cliente_gerente.get(reverse("agenda:gerente_dia"), {"data": segunda.isoformat()}).content.decode()
    assert "Ana" in html and "Bia" in html
    assert "09:00–10:00" in html and "10:15–11:15" in html
    assert "2 agendamentos" in html


def test_semana_de_um_profissional(cliente_gerente, ana, bia, segunda, marcar):
    marcar(bia, hora(segunda, "10:15"))
    response = cliente_gerente.get(
        reverse("agenda:gerente_semana"), {"data": segunda.isoformat(), "profissional": bia.pk}
    )
    assert response.context["profissional_atual"] == bia
    assert "10:15–11:15" in response.content.decode()


def test_novo_agendamento_pede_profissional(cliente_gerente, ana):
    response = cliente_gerente.get(reverse("agenda:gerente_novo"))
    assert response.context.get("form") is None  # só o seletor de profissional
    assert "Escolha…" in response.content.decode()


def test_gerente_agenda_para_qualquer_profissional(cliente_gerente, bia, limpeza, segunda):
    inicio = hora(segunda, "14:00")
    response = cliente_gerente.post(
        reverse("agenda:gerente_novo") + f"?profissional={bia.pk}",
        {
            "profissional": bia.pk,
            "procedimento": limpeza.pk,
            "data": segunda.isoformat(),
            "inicio": inicio.isoformat(),
            "nome": "Eva",
            "telefone": "11 97777-6666",
        },
    )
    assert response.status_code == 302
    assert response.url.startswith(reverse("agenda:gerente_dia"))
    agendamento = Agendamento.objects.get()
    assert agendamento.profissional == bia
    assert agendamento.origem == Agendamento.Origem.GERENTE


def test_horarios_livres_de_outro_profissional(cliente_gerente, client, ana, bia, limpeza, segunda, marcar):
    marcar(bia, hora(segunda, "09:00"))
    params = {"profissional": bia.pk, "procedimento": limpeza.pk, "data": segunda.isoformat()}
    html = cliente_gerente.get(reverse("agenda:horarios_livres"), params).content.decode()
    assert ">09:00<" not in html and ">10:15<" in html

    # Um profissional não consegue consultar a agenda de outro: vê a própria
    client.force_login(ana.usuario)
    html = client.get(reverse("agenda:horarios_livres"), params).content.decode()
    assert ">09:00<" not in html  # a sala está ocupada pela Bia
    assert ">13:00<" in html  # e o expediente é o da Ana (almoço 12–13)


def test_remarcar_para_outro_profissional(cliente_gerente, ana, bia, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    nova = hora(segunda, "15:00")
    response = cliente_gerente.post(
        reverse("agenda:remarcar", args=[agendamento.pk]),
        {"profissional": bia.pk, "data": segunda.isoformat(), "inicio": nova.isoformat()},
    )
    assert response.status_code == 302
    agendamento.refresh_from_db()
    assert agendamento.profissional == bia
    assert agendamento.inicio == nova
    assert agendamento.alocacoes.get().inicio == nova


def test_remarcar_para_quem_nao_faz_o_procedimento(ana, bia, limpeza, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    bia.procedimentos.remove(limpeza)
    with pytest.raises(servicos.AgendamentoInvalido, match="não realiza"):
        servicos.reagendar(agendamento, hora(segunda, "15:00"), profissional=bia)


def test_profissional_nao_troca_o_profissional_ao_remarcar(client, ana, bia, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    client.force_login(ana.usuario)
    client.post(
        reverse("agenda:remarcar", args=[agendamento.pk]),
        {"profissional": bia.pk, "data": segunda.isoformat(), "inicio": hora(segunda, "15:00").isoformat()},
    )
    agendamento.refresh_from_db()
    assert agendamento.profissional == ana  # campo ignorado para quem não é gerente


def test_pendencias(cliente_gerente, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    bloqueio = Bloqueio.objects.create(profissional=ana, inicio=hora(segunda, "08:00"), fim=hora(segunda, "12:00"))
    servicos.aplicar_bloqueio(bloqueio)

    response = cliente_gerente.get(reverse("agenda:gerente_pendencias"))
    assert list(response.context["agendamentos"]) == [agendamento]
    assert response.context["pendencias"] == 1  # contador do menu

    cliente_gerente.post(reverse("agenda:cancelar", args=[agendamento.pk]))
    assert cliente_gerente.get(reverse("agenda:gerente_pendencias")).context["pendencias"] == 0
    agendamento.refresh_from_db()
    assert agendamento.cancelado_por == "gerente"


def test_feriado_fecha_a_clinica(cliente_gerente, ana, bia, limpeza, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    marcar(bia, hora(segunda, "10:15"))
    response = cliente_gerente.post(
        reverse("agenda:gerente_bloqueios"), {"data_inicio": segunda.isoformat(), "motivo": "Feriado"}, follow=True
    )
    assert "2 agendamento(s)" in response.content.decode()

    bloqueio = Bloqueio.objects.get()
    assert bloqueio.geral
    assert servicos.horarios_disponiveis(ana, limpeza, segunda, respeitar_antecedencia=False) == []

    cliente_gerente.post(reverse("agenda:gerente_excluir_bloqueio", args=[bloqueio.pk]))
    assert not Bloqueio.objects.exists()


def test_gerente_nao_exclui_bloqueio_de_profissional(cliente_gerente, ana, segunda):
    bloqueio = Bloqueio.objects.create(profissional=ana, inicio=hora(segunda, "09:00"), fim=hora(segunda, "10:00"))
    assert cliente_gerente.post(reverse("agenda:gerente_excluir_bloqueio", args=[bloqueio.pk])).status_code == 404


def test_profissional_ve_fechamento_mas_nao_remove(client, ana, segunda):
    Bloqueio.objects.create(inicio=hora(segunda, "00:00"), fim=hora(segunda + timedelta(days=1), "00:00"), motivo="Feriado")
    client.force_login(ana.usuario)
    html = client.get(reverse("agenda:bloqueios")).content.decode()
    assert "Clínica fechada · Feriado" in html
    assert "Remover" not in html
