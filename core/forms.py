from django import forms

CLASSE_CAMPO = (
    "block w-full rounded-lg border-slate-300 shadow-sm focus:border-rose-500 focus:ring-rose-500"
)
CLASSE_CHECKBOX = "rounded border-slate-300 text-rose-600 focus:ring-rose-500"


class EstiloMixin:
    """Aplica as classes Tailwind padrão aos widgets do formulário."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            caixa = isinstance(campo.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple))
            campo.widget.attrs.setdefault("class", CLASSE_CHECKBOX if caixa else CLASSE_CAMPO)
