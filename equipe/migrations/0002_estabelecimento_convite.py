"""Multi-estabelecimento (1/3): o mesmo usuário pode ser profissional em vários estabelecimentos; convites."""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import equipe.models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0004_estabelecimento_obrigatorio"),
        ("clinica", "0004_estabelecimento_obrigatorio"),
        ("equipe", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="profissional",
            name="usuario",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="profissionais", to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name="profissional",
            name="estabelecimento",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="profissionais",
                to="clinica.estabelecimento",
            ),
        ),
        migrations.CreateModel(
            name="Convite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, verbose_name="e-mail")),
                ("nome", models.CharField(max_length=100, verbose_name="nome")),
                ("gerente", models.BooleanField(default=False, verbose_name="também será gerente")),
                (
                    "token",
                    models.CharField(default=equipe.models.gerar_token, editable=False, max_length=64, unique=True),
                ),
                ("enviado_em", models.DateTimeField(default=django.utils.timezone.now, verbose_name="enviado em")),
                ("aceito_em", models.DateTimeField(blank=True, null=True, verbose_name="aceito em")),
                (
                    "criado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "estabelecimento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="convites",
                        to="clinica.estabelecimento",
                    ),
                ),
                (
                    "procedimentos",
                    models.ManyToManyField(
                        blank=True, to="catalogo.procedimento", verbose_name="procedimentos que realiza"
                    ),
                ),
            ],
            options={
                "verbose_name": "convite",
                "verbose_name_plural": "convites",
                "ordering": ["-enviado_em"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("aceito_em__isnull", True)),
                        fields=("estabelecimento", "email"),
                        name="convite_pendente_unico",
                    )
                ],
            },
        ),
    ]
