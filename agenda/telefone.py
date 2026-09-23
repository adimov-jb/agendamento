import re

from django.core.exceptions import ValidationError


def normalizar_telefone(valor):
    """'(11) 99999-8888' -> '+5511999998888'. Aceita números brasileiros com DDD."""
    valor = (valor or "").strip()
    digitos = re.sub(r"\D", "", valor)
    # Com "+", o código do país é explícito; sem ele, é um número nacional com DDD
    if not valor.startswith("+") and len(digitos) in (10, 11):
        digitos = "55" + digitos
    if not (digitos.startswith("55") and len(digitos) in (12, 13)):
        raise ValidationError("Informe o telefone com DDD, por exemplo (11) 99999-8888.")
    return "+" + digitos
