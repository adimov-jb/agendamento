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


class DoEstabelecimentoMixin:
    """ModelForm de um cadastro do estabelecimento: vincula o registro novo a ele e valida o nome único nele."""

    def __init__(self, *args, estabelecimento, **kwargs):
        super().__init__(*args, **kwargs)
        self.estabelecimento = estabelecimento
        if self.instance.pk is None:
            self.instance.estabelecimento = estabelecimento

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        modelo = type(self.instance)
        repetidos = modelo.objects.filter(estabelecimento=self.estabelecimento, nome__iexact=nome)
        if repetidos.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"Já existe um(a) {modelo._meta.verbose_name} com este nome.")
        return nome
