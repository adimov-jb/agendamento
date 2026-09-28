from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .permissions import PERFIL_GERENTE, PERFIL_PROFISSIONAL, acesso_atual, escolher_acesso, opcoes_de_acesso

INICIO_DO_PERFIL = {PERFIL_GERENTE: "agenda:gerente_dia", PERFIL_PROFISSIONAL: "agenda:dia"}


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


@login_required
def painel(request):
    """Destino após o login: cada perfil vai para a sua área. Quem tem mais de uma opção escolhe antes."""
    perfil = acesso_atual(request)[1]
    if perfil is None:
        return redirect("core:acesso")
    return redirect(INICIO_DO_PERFIL[perfil])


@login_required
def acesso(request):
    """Escolha (ou troca) do estabelecimento e do perfil com que o colaborador vai atuar."""
    opcoes = opcoes_de_acesso(request)
    if request.method == "POST":
        escolhida = next(
            (
                (e, p)
                for e, p in opcoes
                if str(e.pk) == request.POST.get("estabelecimento") and p == request.POST.get("perfil")
            ),
            None,
        )
        if escolhida is None:
            return redirect("core:painel")
        escolher_acesso(request, *escolhida)
        return redirect(INICIO_DO_PERFIL[escolhida[1]])

    estabelecimentos = {}
    for estabelecimento, perfil in opcoes:
        estabelecimentos.setdefault(estabelecimento, []).append(perfil)
    return render(
        request,
        "core/acesso.html",
        {"estabelecimentos": estabelecimentos.items(), "atual": acesso_atual(request)},
    )
