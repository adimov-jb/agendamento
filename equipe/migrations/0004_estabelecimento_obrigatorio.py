"""Multi-estabelecimento (3/3): estabelecimento obrigatório; um cadastro por usuário em cada estabelecimento."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("equipe", "0003_dados_estabelecimento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profissional",
            name="estabelecimento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="profissionais",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AddConstraint(
            model_name="profissional",
            constraint=models.UniqueConstraint(
                fields=("usuario", "estabelecimento"), name="profissional_unico_por_estabelecimento"
            ),
        ),
    ]
