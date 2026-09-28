"""Multi-estabelecimento (1/3): procedimentos e tipos de recurso passam a pertencer a um estabelecimento."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0001_initial"),
        ("clinica", "0004_estabelecimento_obrigatorio"),
    ]

    operations = [
        migrations.AddField(
            model_name="tiporecurso",
            name="estabelecimento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tipos_recurso",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AddField(
            model_name="procedimento",
            name="estabelecimento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="procedimentos",
                to="clinica.estabelecimento",
            ),
        ),
        # O nome passa a ser único dentro do estabelecimento
        migrations.AlterField(
            model_name="tiporecurso",
            name="nome",
            field=models.CharField(max_length=60, verbose_name="nome"),
        ),
        migrations.AlterField(
            model_name="procedimento",
            name="nome",
            field=models.CharField(max_length=100, verbose_name="nome"),
        ),
    ]
