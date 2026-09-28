import pytest

from clinica.models import Estabelecimento

SENHA = "Senha-Forte-2026"


@pytest.fixture
def estabelecimento():
    return Estabelecimento.objects.create(nome="Clínica Bella", tipo=Estabelecimento.Tipo.CLINICA, slug="bella")


@pytest.fixture
def outro_estabelecimento():
    return Estabelecimento.objects.create(nome="Barbearia do Zé", tipo=Estabelecimento.Tipo.BARBEARIA, slug="ze")


@pytest.fixture
def gerente(django_user_model, estabelecimento):
    usuario = django_user_model.objects.create_user("gerente@clinica.com", "gerente@clinica.com", SENHA)
    estabelecimento.gerentes.add(usuario)
    return usuario


@pytest.fixture
def super_admin(django_user_model):
    return django_user_model.objects.create_user("andredimov@hotmail.com", "andredimov@hotmail.com", SENHA)


@pytest.fixture
def cliente_super_admin(client, super_admin):
    client.force_login(super_admin)
    return client


@pytest.fixture
def cliente_gerente(client, gerente):
    client.force_login(gerente)
    return client


@pytest.fixture
def profissional(django_user_model, estabelecimento):
    from equipe.models import Profissional

    usuario = django_user_model.objects.create_user("ana@clinica.com", "ana@clinica.com", SENHA)
    return Profissional.objects.create(usuario=usuario, estabelecimento=estabelecimento, nome="Ana")
