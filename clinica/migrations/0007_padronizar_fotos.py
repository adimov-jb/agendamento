"""Padroniza as fotos já enviadas: quadrado de 400px com recorte central (o mesmo de clinica.fotos)."""

import io

from django.db import migrations
from django.utils import timezone
from PIL import Image, ImageOps

LADO = 400


def padronizar(apps, schema_editor):
    Foto = apps.get_model("clinica", "FotoEstabelecimento")
    for foto in Foto.objects.select_related("estabelecimento"):
        with Image.open(io.BytesIO(bytes(foto.conteudo))) as imagem:
            imagem.load()
            if imagem.size == (LADO, LADO):
                continue
            saida = io.BytesIO()
            ImageOps.fit(imagem, (LADO, LADO), Image.Resampling.LANCZOS).save(saida, "WEBP", quality=85)
        foto.conteudo = saida.getvalue()
        foto.save(update_fields=["conteudo"])
        # Endereço novo da foto, para o navegador não mostrar a antiga do cache
        foto.estabelecimento.foto_atualizada_em = timezone.now()
        foto.estabelecimento.save(update_fields=["foto_atualizada_em"])


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0006_foto"),
    ]

    operations = [
        migrations.RunPython(padronizar, migrations.RunPython.noop),
    ]
