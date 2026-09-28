import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from clinica.models import DiaSemana, Estabelecimento, FotoEstabelecimento

pytestmark = pytest.mark.django_db

URL_CONFIG = reverse("clinica:configuracoes")


def imagem(largura=1600, altura=1200, formato="JPEG", modo="RGB", nome="foto.jpg", cor="red"):
    saida = io.BytesIO()
    Image.new(modo, (largura, altura), cor).save(saida, formato)
    return SimpleUploadedFile(nome, saida.getvalue(), content_type=f"image/{formato.lower()}")


def dados_config(**extra):
    dados = {
        "nome": "Clínica Bella",
        "tipo": "clinica",
        "slug": "bella",
        "grade_minutos": "15",
        "antecedencia_minima_horas": "2",
        "antecedencia_maxima_dias": "60",
    }
    for dia in DiaSemana.values:
        dados[f"dia{dia}-inicio"] = "09:00"
        dados[f"dia{dia}-fim"] = "18:00"
    dados.update(extra)
    return dados


def foto_salva(estabelecimento):
    return Image.open(io.BytesIO(bytes(FotoEstabelecimento.objects.get(estabelecimento=estabelecimento).conteudo)))


def test_cadastro_com_foto(cliente_super_admin):
    response = cliente_super_admin.post(
        reverse("clinica:novo"), {"nome": "Barbearia do Zé", "tipo": "barbearia", "slug": "", "foto": imagem()}
    )
    assert response.status_code == 302

    estabelecimento = Estabelecimento.objects.get()
    salva = foto_salva(estabelecimento)
    assert salva.format == "WEBP"
    assert salva.size == (400, 400)  # tamanho padrão: quadrado com recorte central
    assert estabelecimento.url_foto.startswith("/barbearia-do-ze/foto/?v=")


@pytest.mark.parametrize("largura,altura", [(600, 1100), (3000, 500), (120, 90)])
def test_qualquer_formato_vira_o_quadrado_padrao(cliente_gerente, estabelecimento, largura, altura):
    """Fotos em pé (como fachadas tiradas no celular), panorâmicas ou pequenas: todas com o mesmo tamanho."""
    cliente_gerente.post(URL_CONFIG, dados_config(foto=imagem(largura, altura)))
    assert foto_salva(estabelecimento).size == (400, 400)


def test_imagens_tem_tamanho_fixo_no_html(cliente_gerente, com_foto):
    """Mesmo sem o CSS carregado, a foto não passa do tamanho previsto."""
    html = cliente_gerente.get(reverse("agenda:gerente_dia")).content.decode()
    assert f'<img src="{com_foto.url_foto}" alt="" width="48" height="48"' in html


def test_cadastro_sem_foto(cliente_super_admin):
    cliente_super_admin.post(reverse("clinica:novo"), {"nome": "Salão", "tipo": "salao", "slug": ""})
    estabelecimento = Estabelecimento.objects.get()
    assert estabelecimento.url_foto == ""
    assert not FotoEstabelecimento.objects.exists()


def test_arquivo_que_nao_e_imagem(cliente_super_admin):
    arquivo = SimpleUploadedFile("foto.jpg", b"nao sou uma imagem", content_type="image/jpeg")
    response = cliente_super_admin.post(
        reverse("clinica:novo"), {"nome": "Salão", "tipo": "salao", "slug": "", "foto": arquivo}
    )
    assert response.status_code == 200
    assert response.context["form"].errors["foto"]
    assert not Estabelecimento.objects.exists()


def test_foto_grande_demais(cliente_super_admin, monkeypatch):
    monkeypatch.setattr("clinica.fotos.TAMANHO_MAXIMO_ARQUIVO", 100)
    response = cliente_super_admin.post(
        reverse("clinica:novo"), {"nome": "Salão", "tipo": "salao", "slug": "", "foto": imagem()}
    )
    assert "A foto deve ter no máximo 5 MB." in response.content.decode()


def test_png_transparente_continua_transparente(cliente_gerente, estabelecimento):
    png = imagem(200, 200, "PNG", "RGBA", "logo.png", cor=(255, 0, 0, 128))  # vermelho semitransparente
    cliente_gerente.post(URL_CONFIG, dados_config(foto=png))
    assert foto_salva(estabelecimento).mode == "RGBA"


def test_trocar_e_remover_foto_nas_configuracoes(cliente_gerente, estabelecimento):
    assert "remover_foto" not in cliente_gerente.get(URL_CONFIG).context["form"].fields

    cliente_gerente.post(URL_CONFIG, dados_config(foto=imagem()))
    estabelecimento.refresh_from_db()
    primeira = estabelecimento.url_foto
    assert primeira

    html = cliente_gerente.get(URL_CONFIG).content.decode()
    assert "Remover a foto atual" in html and primeira in html

    cliente_gerente.post(URL_CONFIG, dados_config(foto=imagem(300, 300)))
    estabelecimento.refresh_from_db()
    assert estabelecimento.url_foto != primeira  # endereço novo: o navegador não usa a antiga do cache
    assert foto_salva(estabelecimento).size == (400, 400)

    cliente_gerente.post(URL_CONFIG, dados_config(remover_foto="on"))
    estabelecimento.refresh_from_db()
    assert estabelecimento.url_foto == ""
    assert not FotoEstabelecimento.objects.exists()


def test_salvar_configuracoes_sem_enviar_foto_mantem_a_atual(cliente_gerente, estabelecimento):
    cliente_gerente.post(URL_CONFIG, dados_config(foto=imagem()))
    cliente_gerente.post(URL_CONFIG, dados_config(nome="Clínica Bella Vista"))
    assert FotoEstabelecimento.objects.filter(estabelecimento=estabelecimento).exists()


def test_endereco_da_foto(client, cliente_gerente, estabelecimento):
    assert client.get(reverse("publico:foto", args=["bella"])).status_code == 404
    cliente_gerente.post(URL_CONFIG, dados_config(foto=imagem()))
    estabelecimento.refresh_from_db()

    client.logout()
    response = client.get(estabelecimento.url_foto)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert "immutable" in response["Cache-Control"]
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.fixture
def com_foto(estabelecimento):
    from clinica import fotos

    fotos.salvar(estabelecimento, fotos.processar(imagem()))
    return estabelecimento


def test_foto_nas_telas_da_equipe(cliente_gerente, profissional, com_foto, client):
    for rota in ("agenda:gerente_dia", "equipe:profissionais", "catalogo:procedimentos", "clinica:configuracoes"):
        assert com_foto.url_foto in cliente_gerente.get(reverse(rota)).content.decode(), rota

    client.force_login(profissional.usuario)
    for rota in ("agenda:dia", "agenda:horarios", "agenda:bloqueios"):
        assert com_foto.url_foto in client.get(reverse(rota)).content.decode(), rota


def test_foto_nas_telas_do_cliente(client, ana, limpeza, com_foto):
    for url in (
        reverse("publico:inicio", args=["bella"]),
        reverse("publico:reservar", args=["bella", limpeza.pk]),
        reverse("publico:meus", args=["bella"]),
    ):
        assert com_foto.url_foto in client.get(url).content.decode(), url


def test_sem_foto_nao_mostra_imagem(cliente_gerente):
    assert "/foto/?v=" not in cliente_gerente.get(reverse("agenda:gerente_dia")).content.decode()
