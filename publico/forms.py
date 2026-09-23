from datetime import date

from django import forms
from django.utils import timezone

from agenda.forms import HorarioEscolhidoForm, campo_data
from agenda.telefone import normalizar_telefone
from core.forms import EstiloMixin


def campo_telefone():
    return forms.CharField(
        label="Telefone (com DDD)",
        widget=forms.TextInput(
            attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel", "placeholder": "(11) 99999-8888"}
        ),
    )


def campo_nascimento():
    return campo_data(label="Data de nascimento")


def validar_nascimento(valor):
    if not date(1900, 1, 1) <= valor < timezone.localdate():
        raise forms.ValidationError("Informe uma data de nascimento válida.")
    return valor


class IdentificacaoMixin:
    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data["telefone"])

    def clean_data_nascimento(self):
        return validar_nascimento(self.cleaned_data["data_nascimento"])


class ReservaForm(IdentificacaoMixin, HorarioEscolhidoForm):
    profissional = forms.ModelChoiceField(
        label="Profissional", queryset=None, error_messages={"required": "Escolha o profissional."}
    )
    nome = forms.CharField(label="Seu nome", max_length=100, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    telefone = campo_telefone()
    data_nascimento = campo_nascimento()
    consentimento = forms.BooleanField(
        label="Autorizo o uso do meu nome, telefone e data de nascimento para gerenciar meus agendamentos (LGPD).",
        error_messages={"required": "É preciso autorizar o uso dos dados para agendar."},
    )

    def __init__(self, *args, profissionais, data_minima, data_maxima, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profissional"].queryset = profissionais
        self.fields["data"].widget.attrs.update(min=data_minima.isoformat(), max=data_maxima.isoformat())


class AcessoForm(IdentificacaoMixin, EstiloMixin, forms.Form):
    telefone = campo_telefone()
    data_nascimento = campo_nascimento()
