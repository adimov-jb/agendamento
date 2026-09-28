"""Quem pode entrar onde.

Cada colaborador atua em um ou mais estabelecimentos, como gerente e/ou profissional. Ao entrar, escolhe
o estabelecimento e o perfil (se só tiver uma opção, ela é usada direto). A escolha fica na sessão e
define `request.estabelecimento`, com o qual todas as telas da equipe filtram os dados.

O Super Admin (um único usuário, ver settings.SUPER_ADMIN_LOGIN) cadastra os estabelecimentos e pode
entrar em qualquer um deles como gerente.
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

PERFIL_GERENTE = "gerente"
PERFIL_PROFISSIONAL = "profissional"
PERFIS = [PERFIL_GERENTE, PERFIL_PROFISSIONAL]
CHAVE_ACESSO = "acesso"


def eh_super_admin(user):
    # Pelo login (username), que é único; o campo e-mail não é e poderia ser repetido em outro usuário
    return user.is_authenticated and user.get_username().lower() == settings.SUPER_ADMIN_LOGIN.lower()


def super_admin_required(view):
    """Anônimo vai para o login; qualquer outro usuário recebe 403."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not eh_super_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def opcoes_de_acesso(request):
    """Pares (estabelecimento, perfil) que o usuário pode usar, na ordem em que aparecem na escolha."""
    from clinica.models import Estabelecimento

    if not hasattr(request, "_opcoes"):
        user, opcoes = request.user, set()
        if user.is_authenticated:
            gerencia = Estabelecimento.objects.all()
            if not eh_super_admin(user):
                gerencia = gerencia.filter(gerentes=user)
            atende = Estabelecimento.objects.filter(profissionais__usuario=user, profissionais__ativo=True)
            opcoes = {(e, PERFIL_GERENTE) for e in gerencia} | {(e, PERFIL_PROFISSIONAL) for e in atende}
        request._opcoes = sorted(opcoes, key=lambda o: (o[0].nome.lower(), o[0].pk, PERFIS.index(o[1])))
    return request._opcoes


def acesso_atual(request):
    """(estabelecimento, perfil) em uso: o escolhido na sessão ou a única opção. (None, None) se precisa escolher."""
    if not hasattr(request, "_acesso"):
        opcoes = opcoes_de_acesso(request)
        escolhido = request.session.get(CHAVE_ACESSO)
        atual = next(((e, p) for e, p in opcoes if [e.pk, p] == escolhido), None)
        if atual is None and len(opcoes) == 1:
            atual = opcoes[0]
        request._acesso = atual or (None, None)
    return request._acesso


def escolher_acesso(request, estabelecimento, perfil):
    request.session[CHAVE_ACESSO] = [estabelecimento.pk, perfil]
    for cache in ("_opcoes", "_acesso", "_profissional"):
        request.__dict__.pop(cache, None)


def atua_como_gerente(request):
    return acesso_atual(request)[1] == PERFIL_GERENTE


def profissional_atual(request):
    """Cadastro de profissional do usuário no estabelecimento em uso (mesmo atuando como gerente), ou None."""
    if not hasattr(request, "_profissional"):
        estabelecimento = acesso_atual(request)[0]
        request._profissional = (
            request.user.profissionais.filter(estabelecimento=estabelecimento, ativo=True).first()
            if estabelecimento
            else None
        )
    return request._profissional


def _verificar_perfil(request, aceitos):
    """None se pode seguir (e preenche `request.estabelecimento`); senão a resposta (escolha ou 403)."""
    estabelecimento, perfil = acesso_atual(request)
    if perfil in aceitos:
        request.estabelecimento = estabelecimento
        return None
    if not any(p in aceitos for _, p in opcoes_de_acesso(request)):
        raise PermissionDenied
    return redirect("core:acesso")


def perfil_required(*aceitos):
    def decorador(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            return _verificar_perfil(request, aceitos) or view(request, *args, **kwargs)

        return wrapper

    return decorador


gerente_required = perfil_required(PERFIL_GERENTE)
profissional_required = perfil_required(PERFIL_PROFISSIONAL)
colaborador_required = perfil_required(PERFIL_GERENTE, PERFIL_PROFISSIONAL)


class GerenteRequiredMixin(LoginRequiredMixin):
    """Anônimo vai para o login; usuário logado sem permissão recebe 403."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            resposta = _verificar_perfil(request, [PERFIL_GERENTE])
            if resposta:
                return resposta
        return super().dispatch(request, *args, **kwargs)
