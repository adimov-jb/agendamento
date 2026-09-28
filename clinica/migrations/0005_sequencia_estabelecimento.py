"""Alinha o gerador de ids dos estabelecimentos ao maior id existente.

A antiga configuração da clínica era sempre salva com id=1 fixo, então o gerador de ids da tabela
nunca avançou. Sem este ajuste, o primeiro estabelecimento cadastrado tentaria usar o id 1 de novo.
"""

from django.db import migrations

ALINHAR = """
SELECT setval(
    pg_get_serial_sequence('clinica_estabelecimento', 'id'),
    COALESCE(MAX(id), 1),
    MAX(id) IS NOT NULL
) FROM clinica_estabelecimento;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0004_estabelecimento_obrigatorio"),
    ]

    operations = [
        migrations.RunSQL(ALINHAR, migrations.RunSQL.noop),
    ]
