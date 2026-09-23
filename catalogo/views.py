from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from core.permissions import GerenteRequiredMixin, gerente_required
from core.utils import responder_linha

from .forms import ProcedimentoForm, RecursoForm, RecursosFormSet, TipoRecursoForm
from .models import Procedimento, Recurso, TipoRecurso

# Procedimentos


class ProcedimentoLista(GerenteRequiredMixin, ListView):
    template_name = "catalogo/procedimento_lista.html"
    context_object_name = "procedimentos"
    queryset = Procedimento.objects.prefetch_related("recursos__tipo")


class ProcedimentoFormMixin(GerenteRequiredMixin):
    """Salva o procedimento e seus recursos necessários na mesma transação."""

    model = Procedimento
    form_class = ProcedimentoForm
    template_name = "catalogo/procedimento_form.html"
    success_url = reverse_lazy("catalogo:procedimentos")

    def get_context_data(self, **kwargs):
        kwargs.setdefault("formset", RecursosFormSet(instance=self.object))
        kwargs["voltar_url"] = self.success_url
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if "pk" in kwargs else None
        form = self.get_form()
        formset = RecursosFormSet(request.POST, instance=form.instance)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                formset.save()
            messages.success(request, f"Procedimento “{self.object}” salvo.")
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form, formset=formset))


class ProcedimentoNovo(ProcedimentoFormMixin, CreateView):
    extra_context = {"titulo": "Novo procedimento"}


class ProcedimentoEditar(ProcedimentoFormMixin, UpdateView):
    extra_context = {"titulo": "Editar procedimento"}


@require_POST
@gerente_required
def procedimento_alternar(request, pk):
    procedimento = get_object_or_404(Procedimento, pk=pk)
    procedimento.ativo = not procedimento.ativo
    procedimento.save(update_fields=["ativo"])
    return responder_linha(
        request, "catalogo/_procedimento_linha.html", {"procedimento": procedimento}, "catalogo:procedimentos"
    )


# Salas e equipamentos


class RecursoLista(GerenteRequiredMixin, ListView):
    template_name = "catalogo/recurso_lista.html"
    context_object_name = "tipos"
    queryset = TipoRecurso.objects.prefetch_related("recursos")


class CadastroSimplesMixin(GerenteRequiredMixin, SuccessMessageMixin):
    template_name = "core/form.html"
    success_url = reverse_lazy("catalogo:recursos")
    extra_context = {"voltar_url": reverse_lazy("catalogo:recursos")}


class TipoRecursoNovo(CadastroSimplesMixin, CreateView):
    model = TipoRecurso
    form_class = TipoRecursoForm
    success_message = "Tipo “%(nome)s” criado."
    extra_context = {**CadastroSimplesMixin.extra_context, "titulo": "Novo tipo de recurso"}


class TipoRecursoEditar(CadastroSimplesMixin, UpdateView):
    model = TipoRecurso
    form_class = TipoRecursoForm
    success_message = "Tipo “%(nome)s” salvo."
    extra_context = {**CadastroSimplesMixin.extra_context, "titulo": "Editar tipo de recurso"}


class RecursoNovo(CadastroSimplesMixin, CreateView):
    model = Recurso
    form_class = RecursoForm
    success_message = "“%(nome)s” criado."
    extra_context = {**CadastroSimplesMixin.extra_context, "titulo": "Nova sala ou equipamento"}

    def get_initial(self):
        return {"tipo": self.request.GET.get("tipo")}


class RecursoEditar(CadastroSimplesMixin, UpdateView):
    model = Recurso
    form_class = RecursoForm
    success_message = "“%(nome)s” salvo."
    extra_context = {**CadastroSimplesMixin.extra_context, "titulo": "Editar sala ou equipamento"}


@require_POST
@gerente_required
def recurso_alternar(request, pk):
    recurso = get_object_or_404(Recurso, pk=pk)
    recurso.ativo = not recurso.ativo
    recurso.save(update_fields=["ativo"])
    return responder_linha(request, "catalogo/_recurso_linha.html", {"recurso": recurso}, "catalogo:recursos")
