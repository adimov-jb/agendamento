from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from agenda.servicos import sinalizar_fora_do_expediente
from core.permissions import PERFIL_GERENTE, escolher_acesso, gerente_required, super_admin_required

from .forms import EstabelecimentoForm, NovoEstabelecimentoForm, formularios_horario, salvar_horarios


@gerente_required
def configuracoes(request):
    estabelecimento = request.estabelecimento
    dados = request.POST if request.method == "POST" else None
    form = EstabelecimentoForm(dados, request.FILES if dados is not None else None, instance=estabelecimento)
    horarios = formularios_horario(estabelecimento, dados)

    if dados is not None:
        validos = [form.is_valid()] + [h.is_valid() for h in horarios]
        if all(validos):
            with transaction.atomic():
                form.save()
                salvar_horarios(estabelecimento, horarios)
                afetados = sum(
                    sinalizar_fora_do_expediente(p) for p in estabelecimento.profissionais.filter(ativo=True)
                )
            messages.success(request, "Configurações do estabelecimento salvas.")
            if afetados:
                messages.error(
                    request,
                    f"{afetados} agendamento(s) ficaram fora do horário do estabelecimento e precisam ser reagendados.",
                )
            return redirect("clinica:configuracoes")

    return render(request, "clinica/configuracoes.html", {"form": form, "horarios": horarios})


@super_admin_required
def novo(request):
    """Só o Super Admin cadastra estabelecimentos. Em seguida entra nele como gerente para configurá-lo."""
    form = NovoEstabelecimentoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        estabelecimento = form.save()
        escolher_acesso(request, estabelecimento, PERFIL_GERENTE)
        messages.success(
            request,
            f"“{estabelecimento.nome}” cadastrado. Defina o horário de funcionamento e convide a equipe "
            "(marque “Também será gerente” para quem vai administrar o estabelecimento).",
        )
        return redirect("clinica:configuracoes")
    return render(request, "clinica/novo.html", {"form": form})
