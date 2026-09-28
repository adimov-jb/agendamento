"""Multi-estabelecimento (3/3): estabelecimento obrigatório; telefone único por estabelecimento."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0003_dados_estabelecimento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cliente",
            name="estabelecimento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clientes",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AlterField(
            model_name="bloqueio",
            name="estabelecimento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bloqueios",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AlterField(
            model_name="agendamento",
            name="estabelecimento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendamentos",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AddConstraint(
            model_name="cliente",
            constraint=models.UniqueConstraint(fields=("estabelecimento", "telefone"), name="cliente_telefone_unico"),
        ),
    ]
