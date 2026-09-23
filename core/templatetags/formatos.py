from django import template

register = template.Library()


@register.filter
def duracao(minutos):
    """75 -> '1h15', 60 -> '1h', 45 -> '45 min'."""
    horas, resto = divmod(int(minutos), 60)
    if horas and resto:
        return f"{horas}h{resto:02d}"
    if horas:
        return f"{horas}h"
    return f"{resto} min"
