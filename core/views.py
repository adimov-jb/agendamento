from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .permissions import CHAVE_PERFIL, PERFIL_GERENTE, PERFIL_PROFISSIONAL, perfil_ativo, perfis

INICIO_DO_PERFIL = {PERFIL_GERENTE: "agenda:gerente_dia", PERFIL_PROFISSIONAL: "agenda:dia"}


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


@login_required
def painel(request):
    """Destino após o login: cada perfil vai para a sua área. Quem tem os dois escolhe antes."""
    if not perfis(request.user):
        raise PermissionDenied
    perfil = perfil_ativo(request)
    if perfil is None:
        return redirect("core:perfil")
    return redirect(INICIO_DO_PERFIL[perfil])


@login_required
def perfil(request):
    """Escolha (ou troca) do perfil para quem é gerente e profissional."""
    disponiveis = perfis(request.user)
    if len(disponiveis) < 2:
        return redirect("core:painel")
    if request.method == "POST" and request.POST.get("perfil") in disponiveis:
        request.session[CHAVE_PERFIL] = request.POST["perfil"]
        return redirect(INICIO_DO_PERFIL[request.POST["perfil"]])
    return render(request, "core/perfil.html", {"atual": perfil_ativo(request)})
