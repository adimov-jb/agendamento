import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from catalogo.models import Procedimento
from conftest import SENHA
from core.permissions import GRUPO_GERENTE, eh_gerente
from equipe.models import Profissional

pytestmark = pytest.mark.django_db

URL_NOVO = reverse("equipe:profissional_novo")


@pytest.fixture
def limpeza():
    return Procedimento.objects.create(nome="Limpeza de pele", duracao_minutos=60, preco=150)


def test_cria_profissional_com_login(cliente_gerente, client, limpeza):
    response = cliente_gerente.post(
        URL_NOVO,
        {"nome": "Bia Souza", "email": "Bia@Clinica.com", "senha": SENHA, "procedimentos": [limpeza.pk]},
    )
    assert response.status_code == 302

    profissional = Profissional.objects.get(nome="Bia Souza")
    assert profissional.usuario.email == "bia@clinica.com"
    assert list(profissional.procedimentos.all()) == [limpeza]

    client.logout()
    assert client.login(username="bia@clinica.com", password=SENHA)


def test_senha_obrigatoria_ao_criar(cliente_gerente):
    response = cliente_gerente.post(URL_NOVO, {"nome": "Bia", "email": "bia@clinica.com", "senha": ""})
    assert response.status_code == 200
    assert not Profissional.objects.filter(nome="Bia").exists()


def test_senha_fraca_rejeitada(cliente_gerente):
    response = cliente_gerente.post(URL_NOVO, {"nome": "Bia", "email": "bia@clinica.com", "senha": "123"})
    assert response.status_code == 200
    assert not Profissional.objects.filter(nome="Bia").exists()


def test_email_duplicado(cliente_gerente, profissional):
    response = cliente_gerente.post(URL_NOVO, {"nome": "Outra Ana", "email": "ANA@clinica.com", "senha": SENHA})
    assert "Já existe um usuário com este e-mail." in response.content.decode()


def test_editar_sem_senha_mantem_a_atual(cliente_gerente, client, profissional, limpeza):
    url = reverse("equipe:profissional_editar", args=[profissional.pk])
    response = cliente_gerente.post(
        url, {"nome": "Ana Lima", "email": "ana@clinica.com", "senha": "", "procedimentos": [limpeza.pk]}
    )
    assert response.status_code == 302

    profissional.refresh_from_db()
    assert profissional.nome == "Ana Lima"
    assert profissional.procedimentos.count() == 1
    client.logout()
    assert client.login(username="ana@clinica.com", password=SENHA)


def test_editar_proprio_email_nao_acusa_duplicado(cliente_gerente, profissional):
    url = reverse("equipe:profissional_editar", args=[profissional.pk])
    response = cliente_gerente.post(url, {"nome": "Ana", "email": "ana@clinica.com", "senha": ""})
    assert response.status_code == 302


def test_procedimento_inativo_nao_e_oferecido(cliente_gerente, limpeza):
    Procedimento.objects.create(nome="Peeling antigo", duracao_minutos=30, preco=80, ativo=False)
    opcoes = cliente_gerente.get(URL_NOVO).context["form"].fields["procedimentos"].queryset
    assert list(opcoes) == [limpeza]


def test_inativar_bloqueia_login(cliente_gerente, client, profissional):
    url = reverse("equipe:profissional_alternar", args=[profissional.pk])
    response = cliente_gerente.post(url, HTTP_HX_REQUEST="true")
    assert "Reativar" in response.content.decode()

    profissional.refresh_from_db()
    assert not profissional.ativo
    assert not profissional.usuario.is_active
    client.logout()
    assert not client.login(username="ana@clinica.com", password=SENHA)

    cliente_gerente.force_login(profissional.usuario.__class__.objects.get(email="gerente@clinica.com"))
    cliente_gerente.post(url, HTTP_HX_REQUEST="true")
    profissional.usuario.refresh_from_db()
    assert profissional.usuario.is_active


def test_marca_profissional_como_gerente(cliente_gerente, limpeza):
    cliente_gerente.post(
        URL_NOVO,
        {"nome": "Bia", "email": "bia@clinica.com", "senha": SENHA, "gerente": "on", "procedimentos": [limpeza.pk]},
    )
    usuario = Profissional.objects.get(nome="Bia").usuario
    assert eh_gerente(usuario)

    url = reverse("equipe:profissional_editar", args=[Profissional.objects.get(nome="Bia").pk])
    cliente_gerente.post(url, {"nome": "Bia", "email": "bia@clinica.com", "senha": ""})
    assert not eh_gerente(usuario)


def test_gerente_existente_vira_profissional_com_o_mesmo_login(cliente_gerente, client, gerente, limpeza):
    response = cliente_gerente.post(
        URL_NOVO, {"nome": "Gê", "email": "gerente@clinica.com", "senha": "", "procedimentos": [limpeza.pk]}
    )
    assert response.status_code == 302
    profissional = Profissional.objects.get(nome="Gê")
    assert profissional.usuario == gerente
    assert eh_gerente(gerente)  # continua gerente mesmo sem marcar a opção

    client.logout()
    assert client.login(username="gerente@clinica.com", password=SENHA)  # senha mantida


def test_vincular_gerente_nao_troca_a_senha(cliente_gerente, gerente):
    response = cliente_gerente.post(URL_NOVO, {"nome": "Gê", "email": "gerente@clinica.com", "senha": "Outra-Senha-2026"})
    assert "Deixe em branco para manter a senha atual." in response.content.decode()
    assert not Profissional.objects.exists()


def test_gerente_nao_remove_o_proprio_acesso(cliente_gerente, gerente):
    cliente_gerente.post(URL_NOVO, {"nome": "Gê", "email": "gerente@clinica.com", "senha": ""})
    url = reverse("equipe:profissional_editar", args=[gerente.profissional.pk])
    cliente_gerente.post(url, {"nome": "Gê", "email": "gerente@clinica.com", "senha": ""})
    assert eh_gerente(gerente)


def test_inativar_profissional_gerente_mantem_o_login(cliente_gerente, profissional):
    profissional.usuario.groups.add(Group.objects.get(name=GRUPO_GERENTE))
    cliente_gerente.post(reverse("equipe:profissional_alternar", args=[profissional.pk]))
    profissional.refresh_from_db()
    profissional.usuario.refresh_from_db()
    assert not profissional.ativo
    assert profissional.usuario.is_active
