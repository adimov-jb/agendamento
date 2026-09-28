import smtplib
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse

from catalogo.models import Procedimento
from conftest import SENHA
from equipe.models import Convite, Profissional

pytestmark = pytest.mark.django_db

URL_NOVO = reverse("equipe:profissional_novo")


@pytest.fixture
def limpeza(estabelecimento):
    return Procedimento.objects.create(estabelecimento=estabelecimento, nome="Limpeza de pele", duracao_minutos=60, preco=150)


def convidar(cliente, **dados):
    return cliente.post(URL_NOVO, {"nome": "Bia Souza", "email": "Bia@Clinica.com", **dados})


def url_do_convite(convite):
    return reverse("equipe:convite", args=[convite.token])


# Convite


def test_cadastrar_profissional_envia_convite(cliente_gerente, estabelecimento, limpeza):
    response = convidar(cliente_gerente, procedimentos=[limpeza.pk])
    assert response.url == reverse("equipe:profissionais")

    convite = Convite.objects.get()
    assert convite.email == "bia@clinica.com"
    assert convite.estabelecimento == estabelecimento
    assert list(convite.procedimentos.all()) == [limpeza]
    assert not Profissional.objects.exists()  # só depois de aceitar

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == ["bia@clinica.com"]
    assert "Clínica Bella" in email.subject
    assert f"http://testserver{url_do_convite(convite)}" in email.body


def test_convite_pendente_aparece_na_lista(cliente_gerente):
    convidar(cliente_gerente)
    html = cliente_gerente.get(reverse("equipe:profissionais")).content.decode()
    assert "Convites pendentes" in html and "bia@clinica.com" in html
    assert url_do_convite(Convite.objects.get()) in html  # link para mandar de outra forma


def test_convite_duplicado(cliente_gerente):
    convidar(cliente_gerente)
    response = convidar(cliente_gerente, nome="Bia de novo")
    assert "Já existe um convite pendente para este e-mail." in response.content.decode()
    assert Convite.objects.count() == 1


def test_email_de_quem_ja_e_profissional(cliente_gerente, profissional):
    response = convidar(cliente_gerente, email="ANA@clinica.com")
    assert "Este e-mail já é de um profissional deste estabelecimento." in response.content.decode()


def test_gerente_se_cadastra_como_profissional_sem_convite(cliente_gerente, gerente, estabelecimento, limpeza):
    response = convidar(cliente_gerente, nome="Gê", email="gerente@clinica.com", procedimentos=[limpeza.pk])
    assert response.status_code == 302
    assert not mail.outbox

    profissional = Profissional.objects.get()
    assert profissional.usuario == gerente
    assert profissional.estabelecimento == estabelecimento
    assert list(profissional.procedimentos.all()) == [limpeza]
    assert estabelecimento.gerentes.filter(pk=gerente.pk).exists()  # continua gerente


def test_falha_no_envio_mantem_o_convite(cliente_gerente):
    with mock.patch("equipe.convites.send_mail", side_effect=smtplib.SMTPException):
        response = convidar(cliente_gerente)
    assert Convite.objects.exists()
    mensagens = [str(m) for m in response.wsgi_request._messages]
    assert any("Não foi possível enviar" in m for m in mensagens)


def test_reenviar_troca_o_link(cliente_gerente):
    convidar(cliente_gerente)
    convite = Convite.objects.get()
    token_antigo = convite.token
    cliente_gerente.post(reverse("equipe:convite_reenviar", args=[convite.pk]))
    convite.refresh_from_db()
    assert convite.token != token_antigo
    assert len(mail.outbox) == 2
    assert url_do_convite(convite) in mail.outbox[1].body


def test_cancelar_convite(cliente_gerente, client):
    convidar(cliente_gerente)
    convite = Convite.objects.get()
    cliente_gerente.post(reverse("equipe:convite_cancelar", args=[convite.pk]))
    assert not Convite.objects.exists()
    client.logout()
    assert client.get(url_do_convite(convite)).status_code == 404


def test_procedimentos_oferecidos_sao_os_ativos_do_estabelecimento(cliente_gerente, limpeza, outro_estabelecimento):
    Procedimento.objects.create(estabelecimento=limpeza.estabelecimento, nome="Peeling antigo", duracao_minutos=30, preco=80, ativo=False)
    Procedimento.objects.create(estabelecimento=outro_estabelecimento, nome="Corte", duracao_minutos=30, preco=50)
    opcoes = cliente_gerente.get(URL_NOVO).context["form"].fields["procedimentos"].queryset
    assert list(opcoes) == [limpeza]


# Aceite


@pytest.fixture
def convite(estabelecimento, gerente, limpeza):
    convite = Convite.objects.create(
        estabelecimento=estabelecimento, email="bia@clinica.com", nome="Bia Souza", criado_por=gerente
    )
    convite.procedimentos.add(limpeza)
    return convite


def test_aceitar_criando_o_login(client, convite, limpeza):
    url = url_do_convite(convite)
    html = client.get(url).content.decode()
    assert "Crie a sua senha" in html and "bia@clinica.com" in html

    response = client.post(url, {"nome": "Bia", "senha": SENHA, "confirmacao": SENHA})
    assert response.url == reverse("core:painel")

    profissional = Profissional.objects.get()
    assert profissional.nome == "Bia Souza"  # nome dado pelo gerente
    assert profissional.usuario.email == "bia@clinica.com"
    assert profissional.usuario.first_name == "Bia"
    assert list(profissional.procedimentos.all()) == [limpeza]
    convite.refresh_from_db()
    assert convite.aceito_em is not None

    # Já entrou e está na agenda do novo estabelecimento
    assert client.get(reverse("core:painel")).url == reverse("agenda:dia")
    client.logout()
    assert client.login(username="bia@clinica.com", password=SENHA)
    # O link não vale de novo
    client.logout()
    assert client.get(url).status_code == 404


def test_senhas_diferentes_ou_fracas(client, convite):
    url = url_do_convite(convite)
    response = client.post(url, {"nome": "Bia", "senha": SENHA, "confirmacao": "outra"})
    assert "As senhas não conferem." in response.content.decode()
    response = client.post(url, {"nome": "Bia", "senha": "123", "confirmacao": "123"})
    assert response.context["form"].errors["senha"]
    assert not Profissional.objects.exists()


def test_quem_ja_tem_login_entra_para_aceitar(client, convite, estabelecimento, outro_estabelecimento, django_user_model):
    """Bia já atende na barbearia e passa a atender também na clínica, com o mesmo login."""
    bia = django_user_model.objects.create_user("bia@clinica.com", "bia@clinica.com", SENHA)
    Profissional.objects.create(usuario=bia, estabelecimento=outro_estabelecimento, nome="Bia")
    url = url_do_convite(convite)

    html = client.get(url).content.decode()
    assert "Você já tem login" in html and f"{reverse('login')}?next=" in html

    client.force_login(bia)
    assert "Aceitar convite" in client.get(url).content.decode()
    assert client.post(url).url == reverse("core:painel")

    assert set(bia.profissionais.values_list("estabelecimento__slug", flat=True)) == {"bella", "ze"}
    assert client.get(reverse("core:painel")).url == reverse("agenda:dia")  # entra no que acabou de aceitar
    assert "Trocar" in client.get(reverse("agenda:dia")).content.decode()


def test_convite_de_outra_pessoa(client, convite, django_user_model):
    client.force_login(django_user_model.objects.create_user("outra@x.com", "outra@x.com", SENHA))
    response = client.post(url_do_convite(convite))
    assert "Este convite é para" in response.content.decode()
    assert not Profissional.objects.exists()


def test_convite_como_gerente(client, convite, estabelecimento):
    convite.gerente = True
    convite.save()
    client.post(url_do_convite(convite), {"nome": "Bia", "senha": SENHA, "confirmacao": SENHA})
    assert estabelecimento.gerentes.filter(email="bia@clinica.com").exists()
    # Tem os dois perfis: escolhe ao entrar
    assert client.get(reverse("core:acesso")).status_code == 200


def test_convite_expirado(client, convite):
    Convite.objects.filter(pk=convite.pk).update(enviado_em=convite.enviado_em - Convite.VALIDADE - timedelta(minutes=1))
    response = client.get(url_do_convite(convite))
    assert response.status_code == 404
    assert "Convite inválido" in response.content.decode()


# Edição


def test_editar_nome_e_procedimentos(cliente_gerente, profissional, limpeza):
    url = reverse("equipe:profissional_editar", args=[profissional.pk])
    response = cliente_gerente.post(url, {"nome": "Ana Lima", "procedimentos": [limpeza.pk]})
    assert response.status_code == 302
    profissional.refresh_from_db()
    assert profissional.nome == "Ana Lima"
    assert list(profissional.procedimentos.all()) == [limpeza]


def test_marca_e_desmarca_gerente(cliente_gerente, profissional, estabelecimento):
    url = reverse("equipe:profissional_editar", args=[profissional.pk])
    cliente_gerente.post(url, {"nome": "Ana", "gerente": "on"})
    assert estabelecimento.gerentes.filter(pk=profissional.usuario_id).exists()
    cliente_gerente.post(url, {"nome": "Ana"})
    assert not estabelecimento.gerentes.filter(pk=profissional.usuario_id).exists()


def test_gerente_nao_remove_o_proprio_acesso(cliente_gerente, gerente, estabelecimento):
    convidar(cliente_gerente, nome="Gê", email="gerente@clinica.com")
    url = reverse("equipe:profissional_editar", args=[Profissional.objects.get(usuario=gerente).pk])
    cliente_gerente.post(url, {"nome": "Gê"})
    assert estabelecimento.gerentes.filter(pk=gerente.pk).exists()


def test_inativar_tira_o_acesso_so_deste_estabelecimento(cliente_gerente, profissional, outro_estabelecimento):
    Profissional.objects.create(usuario=profissional.usuario, estabelecimento=outro_estabelecimento, nome="Ana")
    url = reverse("equipe:profissional_alternar", args=[profissional.pk])
    response = cliente_gerente.post(url, HTTP_HX_REQUEST="true")
    assert "Reativar" in response.content.decode()

    profissional.refresh_from_db()
    assert not profissional.ativo
    assert profissional.usuario.is_active  # o login continua valendo na barbearia
    ana = Client()
    ana.force_login(profissional.usuario)
    assert "Barbearia do Zé" in ana.get(reverse("agenda:dia")).content.decode()

    cliente_gerente.post(url, HTTP_HX_REQUEST="true")
    profissional.refresh_from_db()
    assert profissional.ativo


def test_nao_mexe_em_profissional_de_outro_estabelecimento(cliente_gerente, outro_estabelecimento, django_user_model):
    usuario = django_user_model.objects.create_user("zeca@ze.com", "zeca@ze.com", SENHA)
    zeca = Profissional.objects.create(usuario=usuario, estabelecimento=outro_estabelecimento, nome="Zeca")
    assert cliente_gerente.get(reverse("equipe:profissional_editar", args=[zeca.pk])).status_code == 404
    assert cliente_gerente.post(reverse("equipe:profissional_alternar", args=[zeca.pk])).status_code == 404
    assert "Zeca" not in cliente_gerente.get(reverse("equipe:profissionais")).content.decode()
