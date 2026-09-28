"""Multi-estabelecimento (2/3): os profissionais existentes ficam no estabelecimento que veio da clínica."""

from django.db import migrations


def _padrao(apps):
    """Estabelecimento que recebe os dados existentes (o que veio da configuração da clínica)."""
    Estabelecimento = apps.get_model("clinica", "Estabelecimento")
    return Estabelecimento.objects.order_by("pk").first() or Estabelecimento.objects.create(
        nome="Minha clínica", tipo="clinica", slug="minha-clinica"
    )


def migrar(apps, schema_editor):
    sem_estabelecimento = apps.get_model("equipe", "Profissional").objects.filter(estabelecimento__isnull=True)
    if sem_estabelecimento.exists():
        sem_estabelecimento.update(estabelecimento=_padrao(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("equipe", "0002_estabelecimento_convite"),
    ]

    operations = [
        migrations.RunPython(migrar, migrations.RunPython.noop),
    ]
