from datetime import time

from django import forms

from core.forms import EstiloMixin

from .models import Configuracao, DiaSemana, HorarioClinica


class ConfiguracaoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Configuracao
        fields = ["nome_clinica", "grade_minutos", "antecedencia_minima_horas", "antecedencia_maxima_dias"]


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


def formularios_horario(data=None):
    existentes = {h.dia_semana: h for h in HorarioClinica.objects.all()}
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


def salvar_horarios(formularios):
    for form in formularios:
        if form.cleaned_data["aberto"]:
            HorarioClinica.objects.update_or_create(
                dia_semana=form.dia,
                defaults={"inicio": form.cleaned_data["inicio"], "fim": form.cleaned_data["fim"]},
            )
        else:
            HorarioClinica.objects.filter(dia_semana=form.dia).delete()
