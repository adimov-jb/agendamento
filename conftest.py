import pytest
from django.contrib.auth.models import Group

from core.permissions import GRUPO_GERENTE

SENHA = "Senha-Forte-2026"


@pytest.fixture
def gerente(django_user_model):
    usuario = django_user_model.objects.create_user("gerente@clinica.com", "gerente@clinica.com", SENHA)
    usuario.groups.add(Group.objects.get(name=GRUPO_GERENTE))
    return usuario


@pytest.fixture
def cliente_gerente(client, gerente):
    client.force_login(gerente)
    return client


@pytest.fixture
def profissional(django_user_model):
    from equipe.models import Profissional

    usuario = django_user_model.objects.create_user("ana@clinica.com", "ana@clinica.com", SENHA)
    return Profissional.objects.create(usuario=usuario, nome="Ana")
