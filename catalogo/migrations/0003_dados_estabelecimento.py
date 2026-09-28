"""Multi-estabelecimento (2/3): o catálogo existente fica com o estabelecimento que veio da clínica."""

from django.db import migrations


def _padrao(apps):
    """Estabelecimento que recebe os dados existentes (o que veio da configuração da clínica)."""
    Estabelecimento = apps.get_model("clinica", "Estabelecimento")
    return Estabelecimento.objects.order_by("pk").first() or Estabelecimento.objects.create(
        nome="Minha clínica", tipo="clinica", slug="minha-clinica"
    )


def migrar(apps, schema_editor):
    sem_estabelecimento = [
        apps.get_model("catalogo", nome).objects.filter(estabelecimento__isnull=True)
        for nome in ("TipoRecurso", "Procedimento")
    ]
    if any(q.exists() for q in sem_estabelecimento):
        estabelecimento = _padrao(apps)
        for q in sem_estabelecimento:
            q.update(estabelecimento=estabelecimento)


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0002_estabelecimento"),
    ]

    operations = [
        migrations.RunPython(migrar, migrations.RunPython.noop),
    ]
