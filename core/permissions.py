from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

GRUPO_GERENTE = "Gerente"


def eh_gerente(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=GRUPO_GERENTE).exists()
    )


class GerenteRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Anônimo vai para o login; usuário logado sem permissão recebe 403."""

    def test_func(self):
        return eh_gerente(self.request.user)


def gerente_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not eh_gerente(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
