from datetime import time, timedelta

from django import forms

from core.forms import CLASSE_CAMPO, EstiloMixin

from .servicos import momento
from .telefone import normalizar_telefone


def campo_data(**kwargs):
    return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), **kwargs)


def campo_hora(**kwargs):
    return forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"), **kwargs)


class HorarioEscolhidoForm(EstiloMixin, forms.Form):
    """Data + horário escolhido na lista de horários livres."""

    data = campo_data(label="Data")
    inicio = forms.DateTimeField(label="Horário", error_messages={"required": "Escolha um horário."})


class RemarcarForm(HorarioEscolhidoForm):
    """Com `profissionais`, permite também trocar o profissional (uso do gerente)."""

    def __init__(self, *args, profissionais=None, **kwargs):
        super().__init__(*args, **kwargs)
        if profissionais is not None:
            self.fields["profissional"] = forms.ModelChoiceField(
                label="Profissional", queryset=profissionais, empty_label=None
            )
            self.fields["profissional"].widget.attrs["class"] = CLASSE_CAMPO


class AgendamentoForm(HorarioEscolhidoForm):
    procedimento = forms.ModelChoiceField(label="Procedimento", queryset=None, empty_label="Escolha…")
    nome = forms.CharField(label="Nome do cliente", max_length=100)
    telefone = forms.CharField(
        label="Telefone (com DDD)",
        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "placeholder": "(11) 99999-8888"}),
    )
    data_nascimento = campo_data(
        label="Data de nascimento",
        required=False,
        help_text="Opcional. O cliente usa para consultar os próprios agendamentos.",
    )

    field_order = ["procedimento", "data", "inicio", "nome", "telefone", "data_nascimento"]

    def __init__(self, *args, profissional, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["procedimento"].queryset = profissional.procedimentos.filter(ativo=True)

    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data["telefone"])


class HorarioTrabalhoDiaForm(EstiloMixin, forms.Form):
    """Um dia da semana com até dois períodos (ex.: manhã e tarde)."""

    trabalha = forms.BooleanField(required=False)
    inicio1 = campo_hora(required=False)
    fim1 = campo_hora(required=False)
    inicio2 = campo_hora(required=False)
    fim2 = campo_hora(required=False)

    def __init__(self, *args, dia, nome_dia, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        self.dia, self.nome_dia, self.clinica = dia, nome_dia, clinica

    def clean(self):
        dados = super().clean()
        if not dados.get("trabalha"):
            return dados
        if self.clinica is None:
            raise forms.ValidationError("A clínica não abre neste dia.")

        inicio1, fim1 = dados.get("inicio1"), dados.get("fim1")
        inicio2, fim2 = dados.get("inicio2"), dados.get("fim2")
        if not inicio1 or not fim1:
            raise forms.ValidationError("Informe o início e o fim do expediente.")
        periodos = [(inicio1, fim1)]
        if inicio2 or fim2:
            if not inicio2 or not fim2:
                raise forms.ValidationError("Informe o início e o fim do segundo período.")
            if inicio2 < fim1:
                raise forms.ValidationError("O segundo período deve começar depois do fim do primeiro.")
            periodos.append((inicio2, fim2))

        for inicio, fim in periodos:
            if fim <= inicio:
                raise forms.ValidationError("O fim deve ser depois do início.")
            if inicio < self.clinica.inicio or fim > self.clinica.fim:
                raise forms.ValidationError(
                    f"Fora do horário da clínica ({self.clinica.inicio:%H:%M}–{self.clinica.fim:%H:%M})."
                )
        dados["periodos"] = periodos
        return dados


class BloqueioForm(EstiloMixin, forms.Form):
    data_inicio = campo_data(label="De")
    hora_inicio = campo_hora(label="Hora inicial", required=False)
    data_fim = campo_data(label="Até", required=False, help_text="Vazio = mesmo dia.")
    hora_fim = campo_hora(label="Hora final", required=False)
    motivo = forms.CharField(label="Motivo", max_length=100, required=False)

    def clean(self):
        dados = super().clean()
        data_inicio = dados.get("data_inicio")
        if not data_inicio:
            return dados
        data_fim = dados.get("data_fim") or data_inicio
        hora_inicio, hora_fim = dados.get("hora_inicio"), dados.get("hora_fim")

        inicio = momento(data_inicio, hora_inicio or time.min)
        # Sem hora final, bloqueia até o fim do dia
        fim = momento(data_fim, hora_fim) if hora_fim else momento(data_fim + timedelta(days=1), time.min)
        if fim <= inicio:
            raise forms.ValidationError("O fim do bloqueio deve ser depois do início.")
        dados["inicio"], dados["fim"] = inicio, fim
        return dados
