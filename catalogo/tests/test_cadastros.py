from decimal import Decimal

import pytest
from django.urls import reverse

from catalogo.models import Procedimento, Recurso, TipoRecurso

pytestmark = pytest.mark.django_db


@pytest.fixture
def sala():
    tipo = TipoRecurso.objects.create(nome="Sala")
    Recurso.objects.create(tipo=tipo, nome="Sala 1")
    Recurso.objects.create(tipo=tipo, nome="Sala 2")
    return tipo


@pytest.fixture
def laser():
    tipo = TipoRecurso.objects.create(nome="Laser")
    Recurso.objects.create(tipo=tipo, nome="Laser 1")
    return tipo


def dados_procedimento(recursos=(), **extra):
    """recursos: lista de (tipo, quantidade)."""
    dados = {
        "nome": "Limpeza de pele",
        "descricao": "",
        "duracao_minutos": "60",
        "intervalo_minutos": "15",
        "preco": "150.00",
        "recursos-TOTAL_FORMS": "2",
        "recursos-INITIAL_FORMS": "0",
        "recursos-MIN_NUM_FORMS": "0",
        "recursos-MAX_NUM_FORMS": "1000",
    }
    # O navegador envia a quantidade padrão (1) também nas linhas vazias
    for i in range(3):
        dados[f"recursos-{i}-quantidade"] = "1"
    for i, (tipo, quantidade) in enumerate(recursos):
        dados[f"recursos-{i}-tipo"] = str(tipo.pk)
        dados[f"recursos-{i}-quantidade"] = str(quantidade)
    dados.update(extra)
    return dados


def test_cria_procedimento_com_recursos(cliente_gerente, sala, laser):
    response = cliente_gerente.post(
        reverse("catalogo:procedimento_novo"), dados_procedimento([(sala, 1), (laser, 1)])
    )
    assert response.status_code == 302

    procedimento = Procedimento.objects.get()
    assert procedimento.preco == Decimal("150.00")
    assert procedimento.tempo_total_minutos == 75
    assert {(r.tipo.nome, r.quantidade) for r in procedimento.recursos.all()} == {("Sala", 1), ("Laser", 1)}


def test_cria_procedimento_sem_recursos(cliente_gerente):
    response = cliente_gerente.post(reverse("catalogo:procedimento_novo"), dados_procedimento())
    assert response.status_code == 302
    assert Procedimento.objects.get().recursos.count() == 0


def test_linha_sem_tipo_e_ignorada_mesmo_com_quantidade_alterada(cliente_gerente, sala):
    dados = dados_procedimento([(sala, 1)], **{"recursos-1-quantidade": ""})
    response = cliente_gerente.post(reverse("catalogo:procedimento_novo"), dados)
    assert response.status_code == 302
    assert [(r.tipo.nome, r.quantidade) for r in Procedimento.objects.get().recursos.all()] == [("Sala", 1)]


def test_quantidade_maior_que_unidades_ativas(cliente_gerente, laser):
    response = cliente_gerente.post(reverse("catalogo:procedimento_novo"), dados_procedimento([(laser, 2)]))
    assert response.status_code == 200
    assert "Há apenas 1 unidade(s) ativa(s)" in response.content.decode()
    assert not Procedimento.objects.exists()


def test_tipo_repetido_e_rejeitado(cliente_gerente, sala):
    response = cliente_gerente.post(
        reverse("catalogo:procedimento_novo"), dados_procedimento([(sala, 1), (sala, 1)])
    )
    assert response.status_code == 200
    assert not Procedimento.objects.exists()


def test_duracao_minima(cliente_gerente):
    response = cliente_gerente.post(reverse("catalogo:procedimento_novo"), dados_procedimento(duracao_minutos="0"))
    assert response.status_code == 200
    assert not Procedimento.objects.exists()


def test_edita_e_remove_recurso(cliente_gerente, sala):
    cliente_gerente.post(reverse("catalogo:procedimento_novo"), dados_procedimento([(sala, 1)]))
    procedimento = Procedimento.objects.get()
    vinculo = procedimento.recursos.get()

    dados = dados_procedimento(
        nome="Limpeza de pele profunda",
        **{
            "recursos-TOTAL_FORMS": "3",
            "recursos-INITIAL_FORMS": "1",
            "recursos-0-id": str(vinculo.pk),
            "recursos-0-procedimento": str(procedimento.pk),
            "recursos-0-tipo": str(sala.pk),
            "recursos-0-quantidade": "1",
            "recursos-0-DELETE": "on",
        },
    )
    response = cliente_gerente.post(reverse("catalogo:procedimento_editar", args=[procedimento.pk]), dados)
    assert response.status_code == 302

    procedimento.refresh_from_db()
    assert procedimento.nome == "Limpeza de pele profunda"
    assert procedimento.recursos.count() == 0


def test_inativar_procedimento_via_htmx(cliente_gerente):
    procedimento = Procedimento.objects.create(nome="Peeling", duracao_minutos=30, preco=100)
    url = reverse("catalogo:procedimento_alternar", args=[procedimento.pk])

    response = cliente_gerente.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert "Reativar" in response.content.decode()
    procedimento.refresh_from_db()
    assert not procedimento.ativo

    # sem HTMX, volta para a lista
    response = cliente_gerente.post(url)
    assert response.url == reverse("catalogo:procedimentos")
    procedimento.refresh_from_db()
    assert procedimento.ativo


def test_alternar_exige_post(cliente_gerente):
    procedimento = Procedimento.objects.create(nome="Peeling", duracao_minutos=30, preco=100)
    response = cliente_gerente.get(reverse("catalogo:procedimento_alternar", args=[procedimento.pk]))
    assert response.status_code == 405


def test_lista_de_procedimentos(cliente_gerente, sala):
    procedimento = Procedimento.objects.create(nome="Peeling", duracao_minutos=75, intervalo_minutos=15, preco=1200)
    procedimento.recursos.create(tipo=sala, quantidade=1)
    html = cliente_gerente.get(reverse("catalogo:procedimentos")).content.decode()
    assert "Peeling" in html
    assert "1h15" in html
    assert "R$ 1.200,00" in html
    assert "Sala ×1" in html


def test_cria_tipo_e_unidade(cliente_gerente):
    cliente_gerente.post(reverse("catalogo:tipo_novo"), {"nome": "Maca"})
    tipo = TipoRecurso.objects.get(nome="Maca")

    response = cliente_gerente.get(reverse("catalogo:recurso_novo") + f"?tipo={tipo.pk}")
    assert response.context["form"].initial["tipo"] == str(tipo.pk)

    cliente_gerente.post(reverse("catalogo:recurso_novo"), {"tipo": tipo.pk, "nome": "Maca 1"})
    assert tipo.unidades_ativas() == 1


def test_nome_de_unidade_repetido_no_mesmo_tipo(cliente_gerente, sala):
    response = cliente_gerente.post(reverse("catalogo:recurso_novo"), {"tipo": sala.pk, "nome": "Sala 1"})
    assert response.status_code == 200
    assert Recurso.objects.filter(nome="Sala 1").count() == 1


def test_inativar_recurso(cliente_gerente, laser):
    recurso = laser.recursos.get()
    cliente_gerente.post(reverse("catalogo:recurso_alternar", args=[recurso.pk]), HTTP_HX_REQUEST="true")
    assert laser.unidades_ativas() == 0
