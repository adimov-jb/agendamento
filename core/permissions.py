from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

GRUPO_GERENTE = "Gerente"

# Quem é gerente e profissional ao mesmo tempo escolhe, ao entrar, com qual perfil vai atuar.
PERFIL_GERENTE = "gerente"
PERFIL_PROFISSIONAL = "profissional"
CHAVE_PERFIL = "perfil"


def eh_gerente(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=GRUPO_GERENTE).exists()
    )


def eh_profissional(user):
    return user.is_authenticated and getattr(getattr(user, "profissional", None), "ativo", False)


def perfis(user):
    """Perfis que o usuário pode usar, na ordem em que aparecem na escolha."""
    return [
        perfil
        for perfil, tem in ((PERFIL_GERENTE, eh_gerente(user)), (PERFIL_PROFISSIONAL, eh_profissional(user)))
        if tem
    ]


def perfil_ativo(request):
    """O único perfil do usuário ou o escolhido na sessão. None se ainda precisa escolher."""
    disponiveis = perfis(request.user)
    if len(disponiveis) == 1:
        return disponiveis[0]
    escolhido = request.session.get(CHAVE_PERFIL)
    return escolhido if escolhido in disponiveis else None


def atua_como_gerente(request):
    return perfil_ativo(request) == PERFIL_GERENTE


def _verificar_perfil(request, perfil):
    """None se pode seguir; senão a resposta (escolha de perfil ou 403)."""
    if perfil not in perfis(request.user):
        raise PermissionDenied
    if perfil_ativo(request) != perfil:
        return redirect("core:perfil")
    return None


def perfil_required(perfil):
    def decorador(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            return _verificar_perfil(request, perfil) or view(request, *args, **kwargs)

        return wrapper

    return decorador


gerente_required = perfil_required(PERFIL_GERENTE)


class GerenteRequiredMixin(LoginRequiredMixin):
    """Anônimo vai para o login; usuário logado sem permissão recebe 403."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            resposta = _verificar_perfil(request, PERFIL_GERENTE)
            if resposta:
                return resposta
        return super().dispatch(request, *args, **kwargs)
