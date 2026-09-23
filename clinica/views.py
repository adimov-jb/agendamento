from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from agenda.servicos import sinalizar_fora_do_expediente
from core.permissions import gerente_required
from equipe.models import Profissional

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
                afetados = sum(
                    sinalizar_fora_do_expediente(p) for p in Profissional.objects.filter(ativo=True)
                )
            messages.success(request, "Configurações da clínica salvas.")
            if afetados:
                messages.error(
                    request, f"{afetados} agendamento(s) ficaram fora do horário da clínica e precisam ser reagendados."
                )
            return redirect("clinica:configuracoes")

    return render(request, "clinica/configuracoes.html", {"form": form, "horarios": horarios})
