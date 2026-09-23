import re

from django import template

register = template.Library()


@register.filter
def telefone(valor):
    """'+5511999998888' -> '(11) 99999-8888'."""
    digitos = re.sub(r"\D", "", valor or "")
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return valor


@register.filter
def percentual(fracao):
    """0.125 -> '12,5%'; None -> '—' (sem base para calcular)."""
    if fracao is None:
        return "—"
    texto = f"{fracao * 100:.1f}".replace(".", ",").removesuffix(",0")
    return f"{texto}%"


@register.filter
def duracao(minutos):
    """75 -> '1h15', 60 -> '1h', 45 -> '45 min'."""
    horas, resto = divmod(int(minutos), 60)
    if horas and resto:
        return f"{horas}h{resto:02d}"
    if horas:
        return f"{horas}h"
    return f"{resto} min"
