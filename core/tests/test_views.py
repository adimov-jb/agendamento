import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from core.permissions import GRUPO_GERENTE
from core.templatetags.formatos import duracao

pytestmark = pytest.mark.django_db


def test_home(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200


def test_health_consulta_banco(client):
    response = client.get(reverse("core:health"))
    assert response.json() == {"status": "ok"}


def test_grupo_gerente_criado_pela_migracao():
    assert Group.objects.filter(name=GRUPO_GERENTE).exists()


def test_painel_exige_login(client):
    response = client.get(reverse("core:painel"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_painel_leva_gerente_para_area_do_gerente(cliente_gerente):
    response = cliente_gerente.get(reverse("core:painel"))
    assert response.url == reverse("core:gerente")


def test_painel_leva_profissional_para_agenda(client, profissional):
    client.force_login(profissional.usuario)
    assert client.get(reverse("core:painel")).url == reverse("agenda:dia")


def test_superusuario_conta_como_gerente(client, django_user_model):
    admin = django_user_model.objects.create_superuser("admin", "admin@clinica.com", "x")
    client.force_login(admin)
    assert client.get(reverse("core:gerente")).status_code == 200


@pytest.mark.parametrize(
    "rota",
    ["core:gerente", "equipe:profissionais", "catalogo:procedimentos", "catalogo:recursos", "clinica:configuracoes"],
)
def test_area_do_gerente_bloqueada(client, profissional, rota):
    url = reverse(rota)
    assert client.get(url).status_code == 302  # anônimo vai para o login

    client.force_login(profissional.usuario)
    assert client.get(url).status_code == 403


def test_login_com_email(client, profissional):
    from conftest import SENHA

    response = client.post(reverse("login"), {"username": "ana@clinica.com", "password": SENHA})
    assert response.url == reverse("core:painel")


@pytest.mark.parametrize("minutos,esperado", [(45, "45 min"), (60, "1h"), (75, "1h15"), (125, "2h05")])
def test_filtro_duracao(minutos, esperado):
    assert duracao(minutos) == esperado
