"""Multi-estabelecimento (3/3): estabelecimento obrigatório e nomes únicos por estabelecimento."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0003_dados_estabelecimento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tiporecurso",
            name="estabelecimento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tipos_recurso",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AlterField(
            model_name="procedimento",
            name="estabelecimento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="procedimentos",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AddConstraint(
            model_name="tiporecurso",
            constraint=models.UniqueConstraint(fields=("estabelecimento", "nome"), name="tipo_recurso_nome_unico"),
        ),
        migrations.AddConstraint(
            model_name="procedimento",
            constraint=models.UniqueConstraint(fields=("estabelecimento", "nome"), name="procedimento_nome_unico"),
        ),
    ]
