"""Multi-estabelecimento (3/3): slug e estabelecimento passam a ser obrigatórios."""

from django.db import migrations, models

import clinica.models


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0003_dados_estabelecimento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="estabelecimento",
            name="slug",
            field=models.SlugField(
                help_text="Aparece no link que os clientes usam para agendar. Use letras minúsculas, números e hífens.",
                max_length=60,
                unique=True,
                validators=[clinica.models.validar_slug],
                verbose_name="endereço da página de agendamento",
            ),
        ),
        migrations.AlterField(
            model_name="horariofuncionamento",
            name="estabelecimento",
            field=models.ForeignKey(
                on_delete=models.CASCADE, related_name="horarios", to="clinica.estabelecimento"
            ),
        ),
        migrations.AddConstraint(
            model_name="horariofuncionamento",
            constraint=models.UniqueConstraint(
                fields=("estabelecimento", "dia_semana"), name="horario_funcionamento_dia_unico"
            ),
        ),
    ]
