"""Multi-estabelecimento (1/3): a configuração única da clínica vira o modelo Estabelecimento."""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0001_initial"),
        ("core", "0001_grupo_gerente"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Estabelecimento
        migrations.RenameModel("Configuracao", "Estabelecimento"),
        migrations.RenameField("estabelecimento", "nome_clinica", "nome"),
        migrations.AlterField(
            model_name="estabelecimento",
            name="nome",
            field=models.CharField(max_length=100, verbose_name="nome"),
        ),
        migrations.AddField(
            model_name="estabelecimento",
            name="tipo",
            field=models.CharField(
                choices=[("clinica", "Clínica"), ("barbearia", "Barbearia"), ("salao", "Salão de Beleza")],
                default="clinica",
                max_length=20,
                verbose_name="tipo",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="estabelecimento",
            name="slug",
            field=models.SlugField(max_length=60, null=True),
        ),
        migrations.AddField(
            model_name="estabelecimento",
            name="gerentes",
            field=models.ManyToManyField(
                blank=True,
                related_name="estabelecimentos_gerenciados",
                to=settings.AUTH_USER_MODEL,
                verbose_name="gerentes",
            ),
        ),
        migrations.AlterModelOptions(
            name="estabelecimento",
            options={"ordering": ["nome"], "verbose_name": "estabelecimento", "verbose_name_plural": "estabelecimentos"},
        ),
        # Horário de funcionamento por estabelecimento
        migrations.RenameModel("HorarioClinica", "HorarioFuncionamento"),
        migrations.AlterModelOptions(
            name="horariofuncionamento",
            options={
                "ordering": ["dia_semana"],
                "verbose_name": "horário de funcionamento",
                "verbose_name_plural": "horários de funcionamento",
            },
        ),
        migrations.AlterField(
            model_name="horariofuncionamento",
            name="dia_semana",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, "Segunda-feira"), (1, "Terça-feira"), (2, "Quarta-feira"), (3, "Quinta-feira"),
                    (4, "Sexta-feira"), (5, "Sábado"), (6, "Domingo"),
                ],
                verbose_name="dia da semana",
            ),
        ),
        migrations.AddField(
            model_name="horariofuncionamento",
            name="estabelecimento",
            field=models.ForeignKey(
                null=True, on_delete=models.CASCADE, related_name="horarios", to="clinica.estabelecimento"
            ),
        ),
    ]
