from django.contrib import messages
from django.contrib.auth import login
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, UpdateView

from clinica.models import Estabelecimento
from core.permissions import PERFIL_PROFISSIONAL, GerenteRequiredMixin, escolher_acesso, gerente_required
from core.utils import responder_linha

from . import convites
from .forms import CadastroConviteForm, ConviteForm, ProfissionalForm, usuarios_com_email
from .models import Convite, Profissional


def _lista(estabelecimento):
    eh_gerente = Estabelecimento.gerentes.through.objects.filter(
        estabelecimento=estabelecimento, user=OuterRef("usuario")
    )
    return (
        Profissional.objects.filter(estabelecimento=estabelecimento)
        .select_related("usuario")
        .annotate(total_procedimentos=Count("procedimentos"), eh_gerente=Exists(eh_gerente))
    )


class ProfissionalLista(GerenteRequiredMixin, ListView):
    template_name = "equipe/profissional_lista.html"
    context_object_name = "profissionais"

    def get_queryset(self):
        return _lista(self.request.estabelecimento)

    def get_context_data(self, **kwargs):
        pendentes = self.request.estabelecimento.convites.filter(aceito_em__isnull=True)
        for convite in pendentes:
            convite.link = convites.link(self.request, convite)
        return super().get_context_data(convites=pendentes, **kwargs)


@gerente_required
def profissional_novo(request):
    """Cadastrar um profissional é convidá-lo por e-mail. O gerente que se cadastra entra direto."""
    form = ConviteForm(request.POST or None, estabelecimento=request.estabelecimento, usuario_logado=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            convite = form.save()
            if form.para_si_mesmo:
                convite.aceitar(request.user)
        if form.para_si_mesmo:
            messages.success(request, "Você agora também é profissional deste estabelecimento.")
        elif convites.enviar(request, convite):
            messages.success(request, f"Convite enviado para {convite.email}.")
        else:
            messages.error(
                request,
                f"Não foi possível enviar o e-mail para {convite.email}. "
                "Tente reenviar ou copie o link do convite na lista e mande de outra forma.",
            )
        return redirect("equipe:profissionais")
    return render(
        request,
        "core/form.html",
        {
            "form": form,
            "titulo": "Convidar profissional",
            "descricao": "O profissional recebe um e-mail com o link para entrar na equipe.",
            "rotulo_salvar": "Enviar convite",
            "voltar_url": reverse_lazy("equipe:profissionais"),
        },
    )


class ProfissionalEditar(GerenteRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Profissional
    form_class = ProfissionalForm
    template_name = "core/form.html"
    success_url = reverse_lazy("equipe:profissionais")
    success_message = "Profissional “%(nome)s” salvo."
    extra_context = {"titulo": "Editar profissional", "voltar_url": reverse_lazy("equipe:profissionais")}

    def get_queryset(self):
        return Profissional.objects.filter(estabelecimento=self.request.estabelecimento)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "usuario_logado": self.request.user}


@require_POST
@gerente_required
def profissional_alternar(request, pk):
    """Inativar tira o profissional deste estabelecimento; o login dele continua valendo nos outros."""
    profissional = get_object_or_404(Profissional, pk=pk, estabelecimento=request.estabelecimento)
    profissional.ativo = not profissional.ativo
    profissional.save(update_fields=["ativo"])
    return responder_linha(
        request,
        "equipe/_profissional_linha.html",
        {"profissional": _lista(request.estabelecimento).get(pk=pk)},
        "equipe:profissionais",
    )


# Convites pendentes


def _convite_pendente(request, pk):
    return get_object_or_404(Convite, pk=pk, estabelecimento=request.estabelecimento, aceito_em__isnull=True)


@require_POST
@gerente_required
def convite_reenviar(request, pk):
    convite = _convite_pendente(request, pk)
    convite.renovar()
    if convites.enviar(request, convite):
        messages.success(request, f"Convite reenviado para {convite.email}.")
    else:
        messages.error(request, f"Não foi possível enviar o e-mail para {convite.email}.")
    return redirect("equipe:profissionais")


@require_POST
@gerente_required
def convite_cancelar(request, pk):
    convite = _convite_pendente(request, pk)
    convite.delete()
    messages.success(request, f"Convite para {convite.email} cancelado.")
    return redirect("equipe:profissionais")


# Aceite do convite (pelo convidado)


def convite(request, token):
    convite = Convite.objects.select_related("estabelecimento").filter(token=token).first()
    if convite is None or not convite.valido:
        return render(request, "equipe/convite.html", {"invalido": True}, status=404)
    contexto = {"convite": convite}

    if request.user.is_authenticated:
        if not usuarios_com_email(convite.email).filter(pk=request.user.pk).exists():
            return render(request, "equipe/convite.html", {**contexto, "outro_usuario": True})
        if request.method == "POST":
            convite.aceitar(request.user)
            return _entrar_no_estabelecimento(request, convite)
        return render(request, "equipe/convite.html", {**contexto, "confirmar": True})

    if usuarios_com_email(convite.email).exists():
        return render(request, "equipe/convite.html", {**contexto, "entrar": True})

    form = CadastroConviteForm(request.POST or None, email=convite.email, initial={"nome": convite.nome})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            usuario = form.criar_usuario()
            convite.aceitar(usuario)
        login(request, usuario)
        return _entrar_no_estabelecimento(request, convite)
    return render(request, "equipe/convite.html", {**contexto, "form": form})


def _entrar_no_estabelecimento(request, convite):
    escolher_acesso(request, convite.estabelecimento, PERFIL_PROFISSIONAL)
    messages.success(request, f"Bem-vindo(a) à equipe de {convite.estabelecimento.nome}!")
    return redirect("core:painel")
