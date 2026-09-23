from django.contrib.auth.models import Group
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import BooleanField, Count, Exists, ExpressionWrapper, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from core.permissions import GRUPO_GERENTE, GerenteRequiredMixin, gerente_required
from core.utils import responder_linha

from .forms import ProfissionalForm
from .models import Profissional


def _lista():
    no_grupo_gerente = Group.objects.filter(name=GRUPO_GERENTE, user=OuterRef("usuario"))
    return Profissional.objects.select_related("usuario").annotate(
        total_procedimentos=Count("procedimentos"),
        eh_gerente=ExpressionWrapper(
            Q(usuario__is_superuser=True) | Exists(no_grupo_gerente), output_field=BooleanField()
        ),
    )


class ProfissionalLista(GerenteRequiredMixin, ListView):
    template_name = "equipe/profissional_lista.html"
    context_object_name = "profissionais"

    def get_queryset(self):
        return _lista()


class ProfissionalFormMixin(GerenteRequiredMixin, SuccessMessageMixin):
    model = Profissional
    form_class = ProfissionalForm
    template_name = "core/form.html"
    success_url = reverse_lazy("equipe:profissionais")
    success_message = "Profissional “%(nome)s” salvo."

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "usuario_logado": self.request.user}


class ProfissionalNovo(ProfissionalFormMixin, CreateView):
    extra_context = {"titulo": "Novo profissional", "voltar_url": reverse_lazy("equipe:profissionais")}


class ProfissionalEditar(ProfissionalFormMixin, UpdateView):
    extra_context = {"titulo": "Editar profissional", "voltar_url": reverse_lazy("equipe:profissionais")}


@require_POST
@gerente_required
def profissional_alternar(request, pk):
    profissional = get_object_or_404(Profissional.objects.select_related("usuario"), pk=pk)
    profissional.definir_ativo(not profissional.ativo)
    return responder_linha(
        request,
        "equipe/_profissional_linha.html",
        {"profissional": _lista().get(pk=pk)},
        "equipe:profissionais",
    )
