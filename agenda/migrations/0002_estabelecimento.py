"""Multi-estabelecimento (1/3): clientes, bloqueios e agendamentos passam a pertencer a um estabelecimento."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0001_initial"),
        ("clinica", "0004_estabelecimento_obrigatorio"),
        ("equipe", "0004_estabelecimento_obrigatorio"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="estabelecimento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clientes",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AddField(
            model_name="bloqueio",
            name="estabelecimento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bloqueios",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.AddField(
            model_name="agendamento",
            name="estabelecimento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendamentos",
                to="clinica.estabelecimento",
            ),
        ),
        # O telefone passa a ser único dentro do estabelecimento
        migrations.AlterField(
            model_name="cliente",
            name="telefone",
            field=models.CharField(help_text="Formato +5511999999999.", max_length=20, verbose_name="telefone"),
        ),
        migrations.AlterField(
            model_name="bloqueio",
            name="profissional",
            field=models.ForeignKey(
                blank=True,
                help_text="Vazio = bloqueio geral do estabelecimento (vale para todos).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bloqueios",
                to="equipe.profissional",
            ),
        ),
    ]
