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
from .forms import RelatorioForm
from .models import Agendamento, Bloqueio
from .relatorios import gerar as gerar_relatorio
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


def _atalhos_de_periodo(hoje):
    inicio_mes = hoje.replace(day=1)
    fim_mes_passado = inicio_mes - timedelta(days=1)
    proximo_mes = (inicio_mes + timedelta(days=32)).replace(day=1)
    segunda = hoje - timedelta(days=hoje.weekday())
    return [
        ("Esta semana", segunda, segunda + timedelta(days=6)),
        ("Este mês", inicio_mes, proximo_mes - timedelta(days=1)),
        ("Mês passado", fim_mes_passado.replace(day=1), fim_mes_passado),
        ("Últimos 30 dias", hoje - timedelta(days=29), hoje),
    ]


@gerente_required
def relatorios(request):
    hoje = timezone.localdate()
    atalhos = _atalhos_de_periodo(hoje)
    _, inicio_padrao, fim_padrao = atalhos[1]  # este mês

    profissionais = Profissional.objects.all()  # inclui inativos: o histórico continua valendo
    dados = request.GET if "inicio" in request.GET else None
    form = RelatorioForm(dados, profissionais=profissionais, initial={"inicio": inicio_padrao, "fim": fim_padrao})

    contexto = {"form": form, "atalhos": atalhos}
    if dados is None or form.is_valid():
        filtros = form.cleaned_data if dados is not None else {"inicio": inicio_padrao, "fim": fim_padrao}
        contexto.update(
            relatorio=gerar_relatorio(filtros["inicio"], filtros["fim"], filtros.get("profissional")),
            periodo=(filtros["inicio"], filtros["fim"]),
            profissional=filtros.get("profissional"),
        )
    return render(request, "agenda/gerente/relatorios.html", contexto)


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
