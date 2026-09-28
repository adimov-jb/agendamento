"""Multi-estabelecimento (2/3): a agenda existente fica no estabelecimento do profissional (o que veio da clínica)."""

from django.db import migrations
from django.db.models import OuterRef, Subquery


def _padrao(apps):
    """Estabelecimento que recebe os dados existentes (o que veio da configuração da clínica)."""
    Estabelecimento = apps.get_model("clinica", "Estabelecimento")
    return Estabelecimento.objects.order_by("pk").first() or Estabelecimento.objects.create(
        nome="Minha clínica", tipo="clinica", slug="minha-clinica"
    )


def migrar(apps, schema_editor):
    Profissional = apps.get_model("equipe", "Profissional")
    Cliente = apps.get_model("agenda", "Cliente")
    Bloqueio = apps.get_model("agenda", "Bloqueio")
    Agendamento = apps.get_model("agenda", "Agendamento")

    do_profissional = Subquery(Profissional.objects.filter(pk=OuterRef("profissional_id")).values("estabelecimento_id"))
    Agendamento.objects.filter(estabelecimento__isnull=True).update(estabelecimento_id=do_profissional)
    Bloqueio.objects.filter(estabelecimento__isnull=True, profissional__isnull=False).update(
        estabelecimento_id=do_profissional
    )
    # Bloqueios gerais e clientes: até aqui só existia um estabelecimento
    restantes = [
        Bloqueio.objects.filter(estabelecimento__isnull=True),
        Cliente.objects.filter(estabelecimento__isnull=True),
    ]
    if any(q.exists() for q in restantes):
        estabelecimento = _padrao(apps)
        for q in restantes:
            q.update(estabelecimento=estabelecimento)


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0002_estabelecimento"),
    ]

    operations = [
        migrations.RunPython(migrar, migrations.RunPython.noop),
    ]
