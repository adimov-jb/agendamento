import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Cria o superusuário (gerente) a partir de GERENTE_EMAIL e GERENTE_SENHA, se ainda não existir. "
        "Serve para o primeiro deploy em servidores sem acesso ao terminal."
    )

    def handle(self, *args, **options):
        email = os.environ.get("GERENTE_EMAIL", "").strip().lower()
        senha = os.environ.get("GERENTE_SENHA", "")
        if not email or not senha:
            self.stdout.write("GERENTE_EMAIL/GERENTE_SENHA não definidos: nenhum gerente criado.")
            return

        User = get_user_model()
        if User.objects.filter(username__iexact=email).exists():
            self.stdout.write(f"Gerente {email} já existe.")
            return

        usuario = User(username=email, email=email)
        try:
            validate_password(senha, usuario)
        except ValidationError as erro:
            raise CommandError(f"GERENTE_SENHA fraca: {' '.join(erro.messages)}")
        User.objects.create_superuser(email, email, senha)
        self.stdout.write(self.style.SUCCESS(f"Gerente {email} criado."))
