"""Foto do estabelecimento: validação, redução e gravação."""

import io

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps

TAMANHO_MAXIMO_ARQUIVO = 5 * 1024 * 1024
# Todas as fotos ficam quadradas e do mesmo tamanho, para não quebrar o layout
LADO = 400


def processar(arquivo):
    """Imagem enviada -> WebP quadrado de 400px (recorte central), na orientação certa e sem metadados (EXIF, GPS)."""
    if arquivo.size > TAMANHO_MAXIMO_ARQUIVO:
        raise ValidationError("A foto deve ter no máximo 5 MB.")
    try:
        arquivo.seek(0)
        with Image.open(arquivo) as imagem:
            imagem = ImageOps.exif_transpose(imagem)
            transparente = imagem.mode in ("RGBA", "LA") or "transparency" in imagem.info
            imagem = imagem.convert("RGBA" if transparente else "RGB")
            saida = io.BytesIO()
            padronizar(imagem).save(saida, "WEBP", quality=85)
    except (OSError, Image.DecompressionBombError):
        raise ValidationError("Não foi possível ler esta imagem. Envie um arquivo JPG, PNG ou WebP.")
    return saida.getvalue()


def padronizar(imagem):
    """Recorta o centro da imagem num quadrado e redimensiona para LADO x LADO."""
    return ImageOps.fit(imagem, (LADO, LADO), Image.Resampling.LANCZOS)


def salvar(estabelecimento, conteudo):
    from .models import FotoEstabelecimento

    with transaction.atomic():
        FotoEstabelecimento.objects.update_or_create(
            estabelecimento=estabelecimento, defaults={"conteudo": conteudo, "tipo": "image/webp"}
        )
        estabelecimento.foto_atualizada_em = timezone.now()
        estabelecimento.save(update_fields=["foto_atualizada_em"])


def remover(estabelecimento):
    from .models import FotoEstabelecimento

    with transaction.atomic():
        FotoEstabelecimento.objects.filter(estabelecimento=estabelecimento).delete()
        estabelecimento.foto_atualizada_em = None
        estabelecimento.save(update_fields=["foto_atualizada_em"])
