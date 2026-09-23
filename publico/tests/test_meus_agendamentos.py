from datetime import date

import pytest
from django.urls import reverse

from agenda.models import Agendamento, Cliente
from agenda.servicos import agendar
from agenda.tests.conftest import hora
from publico.acesso import LIMITE_POR_TELEFONE, ip_de

pytestmark = pytest.mark.django_db

Status = Agendamento.Status
ACESSO = {"telefone": "(11) 99999-8888", "data_nascimento": "1990-05-20"}


@pytest.fixture
def carla(cliente):
    """Cliente da agenda (telefone +5511999998888) com data de nascimento."""
    cliente.data_nascimento = date(1990, 5, 20)
    cliente.save()
    return cliente


@pytest.fixture
def cliente_logado(client, carla):
    client.post(reverse("publico:meus"), ACESSO)
    return client


def test_entrar_e_ver_agendamentos(cliente_logado, ana, segunda, marcar):
    marcar(ana, hora(segunda, "09:00"))
    html = cliente_logado.get(reverse("publico:meus")).content.decode()
    assert "Olá, Carla" in html
    assert "Limpeza de pele com Ana" in html


def test_dados_errados(client, carla):
    response = client.post(reverse("publico:meus"), {**ACESSO, "data_nascimento": "1991-05-20"})
    assert "não conferem" in response.content.decode()


def test_cliente_sem_nascimento_nao_entra(client, cliente):
    response = client.post(reverse("publico:meus"), ACESSO)
    assert "não conferem" in response.content.decode()


def test_bloqueia_apos_muitas_tentativas(client, carla):
    for _ in range(LIMITE_POR_TELEFONE):
        client.post(reverse("publico:meus"), {**ACESSO, "data_nascimento": "2000-01-01"})
    # Mesmo com os dados certos, fica bloqueado por um tempo
    response = client.post(reverse("publico:meus"), ACESSO)
    assert "Muitas tentativas" in response.content.decode()


def test_cancelar(cliente_logado, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    cliente_logado.post(reverse("publico:cancelar", args=[agendamento.pk]))
    agendamento.refresh_from_db()
    assert agendamento.status == Status.CANCELADO
    assert agendamento.cancelado_por == "cliente"


def test_nao_mexe_em_agendamento_de_outro_cliente(cliente_logado, ana, limpeza, segunda):
    outro = Cliente.objects.create(nome="Outra", telefone="+5511911112222")
    agendamento = agendar(
        cliente=outro, profissional=ana, procedimento=limpeza, inicio=hora(segunda, "09:00"),
        origem=Agendamento.Origem.CLIENTE, respeitar_antecedencia=False,
    )
    assert cliente_logado.post(reverse("publico:cancelar", args=[agendamento.pk])).status_code == 404
    assert cliente_logado.get(reverse("publico:remarcar", args=[agendamento.pk])).status_code == 404


def test_acoes_exigem_identificacao(client, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    response = client.post(reverse("publico:cancelar", args=[agendamento.pk]))
    assert response.url == reverse("publico:meus")
    agendamento.refresh_from_db()
    assert agendamento.status == Status.AGENDADO


def test_remarcar_livre(cliente_logado, ana, segunda, marcar):
    from clinica.models import Configuracao

    agendamento = marcar(ana, hora(segunda, "09:00"))
    Configuracao.objects.update(antecedencia_maxima_dias=3)  # não vale para remarcação do cliente
    nova = hora(segunda, "15:00")
    response = cliente_logado.post(
        reverse("publico:remarcar", args=[agendamento.pk]), {"data": segunda.isoformat(), "inicio": nova.isoformat()}
    )
    assert response.url == reverse("publico:meus")
    agendamento.refresh_from_db()
    assert agendamento.inicio == nova


def test_horarios_de_remarcacao(cliente_logado, ana, segunda, marcar):
    agendamento = marcar(ana, hora(segunda, "09:00"))
    html = cliente_logado.get(
        reverse("publico:horarios_remarcacao", args=[agendamento.pk]), {"data": segunda.isoformat()}
    ).content.decode()
    assert ">09:30<" in html  # pode sobrepor o próprio horário


def test_sair(cliente_logado):
    cliente_logado.post(reverse("publico:sair"))
    assert "Informe o telefone" in cliente_logado.get(reverse("publico:meus")).content.decode()


@pytest.mark.parametrize(
    "proxies,encaminhado,esperado",
    [
        (0, "1.1.1.1", "10.0.0.9"),  # sem proxy configurado: ignora o cabeçalho
        (1, "6.6.6.6, 1.1.1.1", "1.1.1.1"),  # o primeiro pode ter sido inventado pelo cliente
        (2, "6.6.6.6, 1.1.1.1, 2.2.2.2", "1.1.1.1"),
        (1, "", "10.0.0.9"),
    ],
)
def test_ip_do_cliente_atras_de_proxy(rf, settings, proxies, encaminhado, esperado):
    settings.PROXIES_CONFIAVEIS = proxies
    request = rf.get("/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR=encaminhado)
    assert ip_de(request) == esperado
