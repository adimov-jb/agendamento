from datetime import time

from django import forms

from core.forms import EstiloMixin

from . import fotos
from .models import DiaSemana, Estabelecimento, HorarioFuncionamento, slug_disponivel


class SlugMinusculoMixin:
    """O endereço vai sempre em minúsculas: quem digita /Barbearia/ ou /barbearia/ chega no mesmo lugar."""

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").lower()
        if slug and Estabelecimento.objects.filter(slug__iexact=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este endereço já é de outro estabelecimento.")
        return slug


class FotoMixin(forms.Form):
    """Campo de foto: a imagem é reduzida na validação e gravada junto com o estabelecimento."""

    foto = forms.ImageField(
        label="Foto",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        help_text=(
            "JPG, PNG ou WebP de até 5 MB. É recortada no centro em formato quadrado. "
            "Aparece no topo das telas da equipe e dos clientes."
        ),
    )

    def clean_foto(self):
        arquivo = self.cleaned_data.get("foto")
        self.foto_processada = fotos.processar(arquivo) if arquivo else None
        return arquivo

    def save(self, commit=True):
        estabelecimento = super().save(commit=commit)
        if self.foto_processada:
            fotos.salvar(estabelecimento, self.foto_processada)
        elif self.cleaned_data.get("remover_foto"):
            fotos.remover(estabelecimento)
        return estabelecimento


class EstabelecimentoForm(SlugMinusculoMixin, FotoMixin, EstiloMixin, forms.ModelForm):
    remover_foto = forms.BooleanField(label="Remover a foto atual", required=False)

    class Meta:
        model = Estabelecimento
        fields = ["nome", "tipo", "slug", "grade_minutos", "antecedencia_minima_horas", "antecedencia_maxima_dias"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ClearableFileInput mostraria um link para a foto atual; ela já aparece na página
        self.fields["foto"].widget = forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})
        if self.instance.foto_atualizada_em:
            self.fields["foto"].label = "Trocar a foto"
        else:
            del self.fields["remover_foto"]


class NovoEstabelecimentoForm(SlugMinusculoMixin, FotoMixin, EstiloMixin, forms.ModelForm):
    """Cadastro inicial: nome, tipo e endereço (gerado a partir do nome se ficar em branco)."""

    class Meta:
        model = Estabelecimento
        fields = ["nome", "tipo", "slug", "foto"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [("", "Escolha…"), *Estabelecimento.Tipo.choices]
        self.fields["slug"].required = False
        self.fields["slug"].help_text += " Deixe em branco para gerar a partir do nome."

    def clean(self):
        dados = super().clean()
        if not dados.get("slug") and dados.get("nome") and "slug" not in self.errors:
            dados["slug"] = slug_disponivel(dados["nome"])
            self.instance.slug = dados["slug"]
        return dados


def campo_hora():
    return forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))


class HorarioDiaForm(EstiloMixin, forms.Form):
    aberto = forms.BooleanField(required=False)
    inicio = campo_hora()
    fim = campo_hora()

    def __init__(self, *args, dia, **kwargs):
        super().__init__(*args, **kwargs)
        self.dia = dia
        self.nome_dia = DiaSemana(dia).label

    def clean(self):
        dados = super().clean()
        if dados.get("aberto"):
            inicio, fim = dados.get("inicio"), dados.get("fim")
            if not inicio or not fim:
                raise forms.ValidationError("Informe o horário de abertura e de fechamento.")
            if fim <= inicio:
                raise forms.ValidationError("O fechamento deve ser depois da abertura.")
        return dados


def formularios_horario(estabelecimento, data=None):
    existentes = {h.dia_semana: h for h in estabelecimento.horarios.all()}
    formularios = []
    for dia in DiaSemana.values:
        horario = existentes.get(dia)
        inicial = {
            "aberto": horario is not None,
            "inicio": horario.inicio if horario else time(9),
            "fim": horario.fim if horario else time(18),
        }
        formularios.append(HorarioDiaForm(data, prefix=f"dia{dia}", initial=inicial, dia=dia))
    return formularios


def salvar_horarios(estabelecimento, formularios):
    for form in formularios:
        if form.cleaned_data["aberto"]:
            HorarioFuncionamento.objects.update_or_create(
                estabelecimento=estabelecimento,
                dia_semana=form.dia,
                defaults={"inicio": form.cleaned_data["inicio"], "fim": form.cleaned_data["fim"]},
            )
        else:
            estabelecimento.horarios.filter(dia_semana=form.dia).delete()
