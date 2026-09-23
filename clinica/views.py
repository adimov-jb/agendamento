from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from core.permissions import gerente_required

from .forms import ConfiguracaoForm, formularios_horario, salvar_horarios
from .models import Configuracao


@gerente_required
def configuracoes(request):
    dados = request.POST if request.method == "POST" else None
    form = ConfiguracaoForm(dados, instance=Configuracao.atual())
    horarios = formularios_horario(dados)

    if dados is not None:
        validos = [form.is_valid()] + [h.is_valid() for h in horarios]
        if all(validos):
            with transaction.atomic():
                form.save()
                salvar_horarios(horarios)
            messages.success(request, "Configurações da clínica salvas.")
            return redirect("clinica:configuracoes")

    return render(request, "clinica/configuracoes.html", {"form": form, "horarios": horarios})
