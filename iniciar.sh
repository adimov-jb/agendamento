#!/bin/sh
# Inicialização em produção: aplica as migrações, cria o primeiro gerente (se configurado) e sobe o servidor.
set -e

python manage.py migrate --noinput
python manage.py criar_gerente_inicial
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --access-logfile -
