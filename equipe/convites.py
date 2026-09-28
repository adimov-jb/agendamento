"""Envio do convite por e-mail."""

import logging
import smtplib

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def link(request, convite):
    return request.build_absolute_uri(reverse("equipe:convite", args=[convite.token]))


def enviar(request, convite):
    """Envia o convite. Retorna False se o servidor de e-mail falhar (o convite continua valendo)."""
    contexto = {
        "convite": convite,
        "link": link(request, convite),
        "convidou": request.user.get_full_name() or request.user.email or request.user.username,
    }
    try:
        send_mail(
            f"Convite para a equipe de {convite.estabelecimento.nome}",
            render_to_string("equipe/email/convite.txt", contexto),
            None,
            [convite.email],
        )
    except (smtplib.SMTPException, OSError):
        logger.exception("Falha ao enviar o convite %s para %s", convite.pk, convite.email)
        return False
    return True
