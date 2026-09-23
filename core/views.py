from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from catalogo.models import Procedimento, Recurso
from equipe.models import Profissional

from .permissions import eh_gerente, gerente_required


def home(request):
    return render(request, "core/home.html")


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


@login_required
def painel(request):
    """Destino após o login: cada perfil vai para a sua área."""
    if eh_gerente(request.user):
        return redirect("core:gerente")
    if hasattr(request.user, "profissional"):
        return redirect("agenda:dia")
    raise PermissionDenied


@gerente_required
def gerente_inicio(request):
    contagens = {
        "profissionais": Profissional.objects.filter(ativo=True).count(),
        "procedimentos": Procedimento.objects.filter(ativo=True).count(),
        "recursos": Recurso.objects.filter(ativo=True).count(),
    }
    return render(request, "core/gerente_inicio.html", {"contagens": contagens})
