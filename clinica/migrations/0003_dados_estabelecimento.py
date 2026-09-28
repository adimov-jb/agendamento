"""Multi-estabelecimento (2/3): a configuração única da clínica vira o primeiro Estabelecimento.

Os dados existentes continuam valendo: a linha da configuração (pk=1) passa a ser o estabelecimento
"clínica", os horários de funcionamento ficam ligados a ele e quem era gerente (grupo "Gerente" ou
superusuário) passa a ser gerente dele. O grupo "Gerente" deixa de ser usado e é removido.
"""

from django.conf import settings
from django.db import migrations
from django.db.models import Q
from django.utils.text import slugify

import clinica.models

GRUPO_GERENTE = "Gerente"


def _slug(nome, usados):
    base = slugify(nome)[:50] or "estabelecimento"
    if base in clinica.models.SLUGS_RESERVADOS:
        base = f"{base}-1"
    slug, n = base, 2
    while slug in usados:
        slug, n = f"{base}-{n}", n + 1
    usados.add(slug)
    return slug


def migrar_dados(apps, schema_editor):
    Estabelecimento = apps.get_model("clinica", "Estabelecimento")
    Horario = apps.get_model("clinica", "HorarioFuncionamento")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Group = apps.get_model("auth", "Group")

    if Horario.objects.exists() and not Estabelecimento.objects.exists():
        Estabelecimento.objects.create(pk=1, nome="Minha clínica", tipo="clinica")

    usados = set()
    for estabelecimento in Estabelecimento.objects.order_by("pk"):
        estabelecimento.slug = _slug(estabelecimento.nome, usados)
        estabelecimento.save(update_fields=["slug"])

    primeiro = Estabelecimento.objects.order_by("pk").first()
    if primeiro is not None:
        Horario.objects.update(estabelecimento=primeiro)
        gerentes = User.objects.filter(Q(is_superuser=True) | Q(groups__name=GRUPO_GERENTE)).distinct()
        primeiro.gerentes.add(*gerentes)
    Group.objects.filter(name=GRUPO_GERENTE).delete()


def reverter_dados(apps, schema_editor):
    Estabelecimento = apps.get_model("clinica", "Estabelecimento")
    Group = apps.get_model("auth", "Group")
    grupo, _ = Group.objects.get_or_create(name=GRUPO_GERENTE)
    primeiro = Estabelecimento.objects.order_by("pk").first()
    if primeiro is not None:
        grupo.user_set.add(*primeiro.gerentes.filter(is_superuser=False))


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0002_estabelecimento"),
        ("core", "0001_grupo_gerente"),
    ]

    operations = [
        migrations.RunPython(migrar_dados, reverter_dados),
    ]
