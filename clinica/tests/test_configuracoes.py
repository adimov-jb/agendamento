from datetime import time

import pytest
from django.urls import reverse

from clinica.models import DiaSemana, Estabelecimento, HorarioFuncionamento

pytestmark = pytest.mark.django_db

URL = reverse("clinica:configuracoes")


def dados_validos(**extra):
    dados = {
        "nome": "Clínica Bella Vista",
        "tipo": "clinica",
        "slug": "bella-vista",
        "grade_minutos": "15",
        "antecedencia_minima_horas": "2",
        "antecedencia_maxima_dias": "60",
    }
    for dia in DiaSemana.values:
        dados[f"dia{dia}-inicio"] = "09:00"
        dados[f"dia{dia}-fim"] = "18:00"
    # segunda a sexta abertas; sábado e domingo fechados
    for dia in range(5):
        dados[f"dia{dia}-aberto"] = "on"
    dados.update(extra)
    return dados


def test_pagina_abre_com_link_publico(cliente_gerente):
    html = cliente_gerente.get(URL).content.decode()
    assert "Configurações do estabelecimento" in html
    assert "http://testserver/bella/" in html


def test_salva_dados_regras_e_horarios(cliente_gerente, estabelecimento):
    response = cliente_gerente.post(URL, dados_validos(tipo="salao"))
    assert response.status_code == 302

    estabelecimento.refresh_from_db()
    assert estabelecimento.nome == "Clínica Bella Vista"
    assert estabelecimento.tipo == Estabelecimento.Tipo.SALAO
    assert estabelecimento.slug == "bella-vista"
    assert list(estabelecimento.horarios.values_list("dia_semana", flat=True)) == [0, 1, 2, 3, 4]
    assert estabelecimento.horarios.get(dia_semana=0).fim == time(18)


def test_desmarcar_dia_fecha_o_estabelecimento(cliente_gerente, estabelecimento):
    cliente_gerente.post(URL, dados_validos())
    dados = dados_validos()
    del dados["dia0-aberto"]
    cliente_gerente.post(URL, dados)
    assert not estabelecimento.horarios.filter(dia_semana=0).exists()


def test_fechamento_antes_da_abertura_e_rejeitado(cliente_gerente, estabelecimento):
    response = cliente_gerente.post(URL, dados_validos(**{"dia2-inicio": "18:00", "dia2-fim": "09:00"}))
    assert response.status_code == 200
    assert "O fechamento deve ser depois da abertura." in response.content.decode()
    assert not HorarioFuncionamento.objects.exists()
    estabelecimento.refresh_from_db()
    assert estabelecimento.nome == "Clínica Bella"


def test_nome_do_estabelecimento_aparece_no_cabecalho(cliente_gerente):
    cliente_gerente.post(URL, dados_validos())
    assert "Clínica Bella Vista" in cliente_gerente.get(reverse("agenda:gerente_dia")).content.decode()


@pytest.mark.parametrize("slug", ["gerente", "admin", "senha", "Com Espaço"])
def test_endereco_invalido_ou_reservado(cliente_gerente, slug):
    response = cliente_gerente.post(URL, dados_validos(slug=slug))
    assert response.status_code == 200
    assert response.context["form"].errors["slug"]


def test_endereco_de_outro_estabelecimento(cliente_gerente, outro_estabelecimento):
    response = cliente_gerente.post(URL, dados_validos(slug="ze"))
    assert response.context["form"].errors["slug"]
    response = cliente_gerente.post(URL, dados_validos(slug="ZE"))  # maiúsculas não enganam
    assert response.context["form"].errors["slug"]


def test_endereco_fica_em_minusculas(cliente_gerente, estabelecimento):
    cliente_gerente.post(URL, dados_validos(slug="Bella-Vista"))
    estabelecimento.refresh_from_db()
    assert estabelecimento.slug == "bella-vista"


def test_endereco_antigo_com_maiusculas_abre_de_qualquer_jeito(client, estabelecimento):
    Estabelecimento.objects.filter(pk=estabelecimento.pk).update(slug="Bella")
    assert client.get("/bella/").status_code == 200
    assert client.get("/BELLA/meus-agendamentos/").status_code == 200


def test_horarios_sao_de_cada_estabelecimento(cliente_gerente, outro_estabelecimento):
    HorarioFuncionamento.objects.create(
        estabelecimento=outro_estabelecimento, dia_semana=5, inicio=time(8), fim=time(12)
    )
    cliente_gerente.post(URL, dados_validos())
    assert outro_estabelecimento.horarios.count() == 1  # não foi mexido


# Cadastro de estabelecimento


def test_super_admin_cadastra_estabelecimento(cliente_super_admin):
    response = cliente_super_admin.post(
        reverse("clinica:novo"), {"nome": "Barbearia do Zé", "tipo": "barbearia", "slug": ""}
    )
    assert response.url == reverse("clinica:configuracoes")

    estabelecimento = Estabelecimento.objects.get()
    assert estabelecimento.tipo == Estabelecimento.Tipo.BARBEARIA
    assert estabelecimento.slug == "barbearia-do-ze"  # gerado a partir do nome
    assert not estabelecimento.gerentes.exists()  # o Super Admin entra sem precisar ser gerente cadastrado
    # Já entra como gerente do novo estabelecimento
    assert cliente_super_admin.get(reverse("core:painel")).url == reverse("agenda:gerente_dia")
    assert "Barbearia do Zé" in cliente_super_admin.get(reverse("agenda:gerente_dia")).content.decode()


def test_so_o_super_admin_cadastra_estabelecimento(client, cliente_gerente, django_user_model):
    assert cliente_gerente.get(reverse("clinica:novo")).status_code == 403
    response = cliente_gerente.post(reverse("clinica:novo"), {"nome": "Outro", "tipo": "salao", "slug": ""})
    assert response.status_code == 403
    assert Estabelecimento.objects.count() == 1

    # Nem um superusuário do Django que não seja o Super Admin
    client.force_login(django_user_model.objects.create_superuser("admin", "admin@exemplo.com", "x"))
    assert client.get(reverse("clinica:novo")).status_code == 403

    client.logout()
    assert client.get(reverse("clinica:novo")).url.startswith(reverse("login"))


def test_tipo_obrigatorio(cliente_super_admin):
    response = cliente_super_admin.post(reverse("clinica:novo"), {"nome": "Sem tipo", "tipo": ""})
    assert response.status_code == 200
    assert not Estabelecimento.objects.exists()


def test_slug_gerado_nao_repete(cliente_super_admin, estabelecimento):
    cliente_super_admin.post(reverse("clinica:novo"), {"nome": "Bella", "tipo": "clinica", "slug": ""})
    assert Estabelecimento.objects.filter(slug="bella-2").exists()
