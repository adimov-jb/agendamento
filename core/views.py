from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .permissions import eh_gerente


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
        return redirect("agenda:gerente_dia")
    if hasattr(request.user, "profissional"):
        return redirect("agenda:dia")
    raise PermissionDenied
