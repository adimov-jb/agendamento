import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from conftest import SENHA
from core.templatetags.formatos import duracao
from equipe.models import Profissional

pytestmark = pytest.mark.django_db


def test_home_sem_estabelecimentos(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert "Nenhum estabelecimento" in response.content.decode()


def test_health_consulta_banco(client):
    response = client.get(reverse("core:health"))
    assert response.json() == {"status": "ok"}


def test_grupo_gerente_nao_e_mais_usado():
    # A migração passou os gerentes do grupo para o estabelecimento
    assert not Group.objects.filter(name="Gerente").exists()


def test_painel_exige_login(client):
    response = client.get(reverse("core:painel"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_painel_leva_gerente_para_area_do_gerente(cliente_gerente):
    response = cliente_gerente.get(reverse("core:painel"))
    assert response.url == reverse("agenda:gerente_dia")


def test_painel_leva_profissional_para_agenda(client, profissional):
    client.force_login(profissional.usuario)
    assert client.get(reverse("core:painel")).url == reverse("agenda:dia")


def test_usuario_sem_estabelecimento_nao_cadastra_um(client, django_user_model, estabelecimento):
    usuario = django_user_model.objects.create_superuser("admin", "admin@exemplo.com", "x")
    client.force_login(usuario)
    assert client.get(reverse("core:painel")).url == reverse("core:acesso")
    html = client.get(reverse("core:acesso")).content.decode()
    assert "Nenhum estabelecimento" in html
    assert "fale com o administrador" in html
    assert reverse("clinica:novo") not in html
    # Superusuário do Django não é Super Admin: não entra nos estabelecimentos
    assert client.get(reverse("agenda:gerente_dia")).status_code == 403


# Super Admin


def test_super_admin_escolhe_qualquer_estabelecimento_como_gerente(
    cliente_super_admin, estabelecimento, outro_estabelecimento
):
    assert cliente_super_admin.get(reverse("core:painel")).url == reverse("core:acesso")
    html = cliente_super_admin.get(reverse("core:acesso")).content.decode()
    assert "Clínica Bella" in html and "Barbearia do Zé" in html
    assert "Entrar como profissional" not in html
    assert reverse("clinica:novo") in html

    for e in (estabelecimento, outro_estabelecimento):
        escolha = {"estabelecimento": e.pk, "perfil": "gerente"}
        assert cliente_super_admin.post(reverse("core:acesso"), escolha).url == reverse("agenda:gerente_dia")
        html = cliente_super_admin.get(reverse("agenda:gerente_dia")).content.decode()
        assert e.nome in html and "· Super Admin" in html
        assert cliente_super_admin.get(reverse("clinica:configuracoes")).status_code == 200


def test_super_admin_com_um_so_estabelecimento_entra_direto(cliente_super_admin, estabelecimento):
    assert cliente_super_admin.get(reverse("core:painel")).url == reverse("agenda:gerente_dia")
    # Continua vendo o link da lista de estabelecimentos, para cadastrar outros
    assert reverse("core:acesso") in cliente_super_admin.get(reverse("agenda:gerente_dia")).content.decode()


def test_super_admin_e_so_o_login_configurado(client, django_user_model, estabelecimento):
    # Outro usuário com o mesmo e-mail (o e-mail não é único), mas outro login
    impostor = django_user_model.objects.create_user("impostor", "andredimov@hotmail.com", "x")
    client.force_login(impostor)
    assert client.get(reverse("agenda:gerente_dia")).status_code == 403
    assert client.get(reverse("clinica:novo")).status_code == 403


def test_super_admin_que_tambem_e_profissional(cliente_super_admin, super_admin, estabelecimento):
    Profissional.objects.create(usuario=super_admin, estabelecimento=estabelecimento, nome="André")
    html = cliente_super_admin.get(reverse("core:acesso")).content.decode()
    assert "Entrar como gerente" in html and "Entrar como profissional" in html


@pytest.mark.parametrize(
    "rota",
    ["agenda:gerente_dia", "equipe:profissionais", "catalogo:procedimentos", "catalogo:recursos", "clinica:configuracoes"],
)
def test_area_do_gerente_bloqueada(client, profissional, rota):
    url = reverse(rota)
    assert client.get(url).status_code == 302  # anônimo vai para o login

    client.force_login(profissional.usuario)
    assert client.get(url).status_code == 403


def test_login_com_email(client, profissional):
    response = client.post(reverse("login"), {"username": "ana@clinica.com", "password": SENHA})
    assert response.url == reverse("core:painel")


@pytest.mark.parametrize("minutos,esperado", [(45, "45 min"), (60, "1h"), (75, "1h15"), (125, "2h05")])
def test_filtro_duracao(minutos, esperado):
    assert duracao(minutos) == esperado


@pytest.fixture
def gerente_profissional(profissional, estabelecimento):
    """Ana é profissional e também gerente: um só login."""
    estabelecimento.gerentes.add(profissional.usuario)
    return profissional


def test_quem_tem_os_dois_perfis_escolhe_ao_entrar(client, gerente_profissional):
    client.force_login(gerente_profissional.usuario)
    assert client.get(reverse("core:painel")).url == reverse("core:acesso")
    html = client.get(reverse("core:acesso")).content.decode()
    assert "Onde você quer entrar?" in html
    assert "Entrar como gerente" in html and "Entrar como profissional" in html


@pytest.mark.parametrize(
    "perfil,inicio,bloqueada",
    [("gerente", "agenda:gerente_dia", "agenda:dia"), ("profissional", "agenda:dia", "agenda:gerente_dia")],
)
def test_perfil_escolhido_define_a_area(client, gerente_profissional, estabelecimento, perfil, inicio, bloqueada):
    client.force_login(gerente_profissional.usuario)
    escolha = {"estabelecimento": estabelecimento.pk, "perfil": perfil}
    assert client.post(reverse("core:acesso"), escolha).url == reverse(inicio)
    assert client.get(reverse("core:painel")).url == reverse(inicio)
    assert client.get(reverse(inicio)).status_code == 200
    # A área do outro perfil pede para trocar de perfil
    assert client.get(reverse(bloqueada)).url == reverse("core:acesso")


def test_menu_mostra_troca_de_perfil(client, gerente_profissional, estabelecimento):
    client.force_login(gerente_profissional.usuario)
    client.post(reverse("core:acesso"), {"estabelecimento": estabelecimento.pk, "perfil": "gerente"})
    html = client.get(reverse("agenda:gerente_dia")).content.decode()
    assert "Ir para profissional" in html
    assert "Minha agenda" not in html
    assert "Clínica · Gerente" in html  # tipo do estabelecimento e perfil em uso


def test_escolha_invalida_nao_e_aceita(client, profissional, estabelecimento):
    client.force_login(profissional.usuario)
    # Quem só é profissional não pode escolher o perfil de gerente
    escolha = {"estabelecimento": estabelecimento.pk, "perfil": "gerente"}
    assert client.post(reverse("core:acesso"), escolha).url == reverse("core:painel")
    assert client.get(reverse("agenda:gerente_dia")).status_code == 403


# Vários estabelecimentos


@pytest.fixture
def em_dois(profissional, outro_estabelecimento):
    """Ana é profissional na Clínica Bella e gerente na Barbearia do Zé."""
    outro_estabelecimento.gerentes.add(profissional.usuario)
    return profissional


def test_quem_esta_em_dois_estabelecimentos_escolhe_ao_entrar(client, em_dois, estabelecimento, outro_estabelecimento):
    client.force_login(em_dois.usuario)
    assert client.get(reverse("core:painel")).url == reverse("core:acesso")
    html = client.get(reverse("core:acesso")).content.decode()
    assert "Clínica Bella" in html and "Barbearia do Zé" in html

    client.post(reverse("core:acesso"), {"estabelecimento": outro_estabelecimento.pk, "perfil": "gerente"})
    html = client.get(reverse("agenda:gerente_dia")).content.decode()
    assert "Barbearia do Zé" in html
    assert "Trocar" in html  # pode voltar para a escolha de estabelecimento
    assert "Ir para profissional" not in html  # não é profissional na barbearia

    # Na barbearia só é gerente: a agenda de profissional pede nova escolha
    assert client.get(reverse("agenda:dia")).url == reverse("core:acesso")


def test_nao_escolhe_estabelecimento_de_que_nao_participa(client, profissional, outro_estabelecimento):
    client.force_login(profissional.usuario)
    escolha = {"estabelecimento": outro_estabelecimento.pk, "perfil": "profissional"}
    assert client.post(reverse("core:acesso"), escolha).url == reverse("core:painel")
    assert client.get(reverse("core:painel")).url == reverse("agenda:dia")  # continua no dele


def test_escolha_perde_efeito_se_o_acesso_acabar(client, em_dois, outro_estabelecimento):
    client.force_login(em_dois.usuario)
    client.post(reverse("core:acesso"), {"estabelecimento": outro_estabelecimento.pk, "perfil": "gerente"})
    outro_estabelecimento.gerentes.remove(em_dois.usuario)
    # Sobrou só a Clínica Bella como profissional: entra direto nela
    assert client.get(reverse("core:painel")).url == reverse("agenda:dia")


def test_profissional_inativo_perde_o_acesso_ao_estabelecimento(client, profissional):
    Profissional.objects.filter(pk=profissional.pk).update(ativo=False)
    client.force_login(profissional.usuario)
    assert client.get(reverse("core:painel")).url == reverse("core:acesso")
    assert client.get(reverse("agenda:dia")).status_code == 403
