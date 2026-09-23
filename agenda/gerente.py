"""Telas do gerente: agenda de todos, pendências e bloqueios gerais."""

from datetime import timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import gerente_required
from equipe.models import Profissional

from . import servicos
from .models import Agendamento, Bloqueio
from .views import contexto_semana, data_da_url, escolhido, itens_do_dia, pagina_bloqueios, pagina_novo_agendamento


def _profissionais_ativos():
    return Profissional.objects.filter(ativo=True)


@gerente_required
def dia(request):
    data = data_da_url(request)
    colunas = []
    for profissional in _profissionais_ativos():
        itens, _ = itens_do_dia(profissional, data)
        colunas.append(
            {"profissional": profissional, "itens": itens, "expediente": servicos.expediente(profissional, data)}
        )
    return render(
        request,
        "agenda/gerente/dia.html",
        {
            "data": data,
            "hoje": timezone.localdate(),
            "anterior": data - timedelta(days=1),
            "proximo": data + timedelta(days=1),
            "colunas": colunas,
            "total": sum(1 for c in colunas for i in c["itens"] if i["tipo"] == "agendamento"),
        },
    )


@gerente_required
def semana(request):
    profissionais = _profissionais_ativos()
    profissional = escolhido(profissionais, request.GET.get("profissional")) or profissionais.first()
    contexto = {"profissionais": profissionais, "profissional_atual": profissional}
    if profissional:
        contexto.update(contexto_semana(profissional, data_da_url(request)))
        contexto["filtro"] = f"&profissional={profissional.pk}"
    contexto["url_dia"] = reverse("agenda:gerente_dia")
    return render(request, "agenda/semana.html", contexto)


@gerente_required
def novo(request):
    profissionais = _profissionais_ativos()
    valor = request.POST.get("profissional") or request.GET.get("profissional")
    return pagina_novo_agendamento(
        request,
        escolhido(profissionais, valor),
        origem=Agendamento.Origem.GERENTE,
        url_retorno=reverse("agenda:gerente_dia"),
        profissionais=profissionais,
    )


@gerente_required
def pendencias(request):
    agendamentos = (
        Agendamento.objects.filter(status=Agendamento.Status.PRECISA_REAGENDAR)
        .select_related("cliente", "profissional", "procedimento")
        .order_by("inicio")
    )
    return render(request, "agenda/gerente/pendencias.html", {"agendamentos": agendamentos})


@gerente_required
def bloqueios(request):
    return pagina_bloqueios(
        request,
        None,
        url_lista=reverse("agenda:gerente_bloqueios"),
        url_excluir="agenda:gerente_excluir_bloqueio",
        titulo="Feriados e fechamentos",
        descricao="Dias ou períodos em que a clínica inteira fica fechada. Vale para todos os profissionais.",
    )


@require_POST
@gerente_required
def excluir_bloqueio(request, pk):
    get_object_or_404(Bloqueio, pk=pk, profissional__isnull=True).delete()
    messages.success(request, "Fechamento removido.")
    return redirect("agenda:gerente_bloqueios")
