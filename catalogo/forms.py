from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from core.forms import EstiloMixin

from .models import Procedimento, ProcedimentoRecurso, Recurso, TipoRecurso


class ProcedimentoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Procedimento
        fields = ["nome", "descricao", "duracao_minutos", "intervalo_minutos", "preco"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}


class ProcedimentoRecursoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = ProcedimentoRecurso
        fields = ["tipo", "quantidade"]

    def has_changed(self):
        # Linha nova sem tipo escolhido fica vazia, mesmo que a quantidade tenha sido mexida.
        if not self.instance.pk and not self.data.get(self.add_prefix("tipo")):
            return False
        return super().has_changed()

    def clean(self):
        dados = super().clean()
        tipo, quantidade = dados.get("tipo"), dados.get("quantidade")
        if tipo and quantidade and not dados.get("DELETE"):
            disponiveis = tipo.unidades_ativas()
            if quantidade > disponiveis:
                self.add_error("quantidade", f"Há apenas {disponiveis} unidade(s) ativa(s) de “{tipo}”.")
        return dados


class BaseRecursosFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        vistos = set()
        for form in self.forms:
            dados = getattr(form, "cleaned_data", None)
            if not dados or dados.get("DELETE") or not dados.get("tipo"):
                continue
            if dados["tipo"] in vistos:
                raise forms.ValidationError("Cada tipo de recurso só pode aparecer uma vez.")
            vistos.add(dados["tipo"])


RecursosFormSet = inlineformset_factory(
    Procedimento,
    ProcedimentoRecurso,
    form=ProcedimentoRecursoForm,
    formset=BaseRecursosFormSet,
    extra=2,
    can_delete=True,
)


class TipoRecursoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = TipoRecurso
        fields = ["nome"]
        help_texts = {"nome": "Ex.: Sala, Máquina de laser, Maca."}


class RecursoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Recurso
        fields = ["tipo", "nome"]
        help_texts = {"nome": "Ex.: Sala 1, Laser Soprano."}
