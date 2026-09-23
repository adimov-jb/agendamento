from datetime import date, time, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from clinica.models import DiaSemana, HorarioClinica
from core.permissions import eh_gerente

from . import servicos
from .forms import AgendamentoForm, BloqueioForm, HorarioEscolhidoForm, HorarioTrabalhoDiaForm
from .models import Agendamento, Bloqueio, HorarioTrabalho

Status = Agendamento.Status


# Permissões


def profissional_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, "profissional"):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def _origem(user, profissional):
    if getattr(user, "profissional", None) == profissional:
        return Agendamento.Origem.PROFISSIONAL
    return Agendamento.Origem.GERENTE


def _agendamento_acessivel(request, pk):
    """O próprio profissional ou o gerente. Para os demais, o agendamento 'não existe'."""
    agendamento = get_object_or_404(
        Agendamento.objects.select_related("cliente", "procedimento", "profissional"), pk=pk
    )
    if not (eh_gerente(request.user) or getattr(request.user, "profissional", None) == agendamento.profissional):
        raise Http404
    return agendamento


# Auxiliares


def _data_da_url(request):
    try:
        return date.fromisoformat(request.GET.get("data", ""))
    except ValueError:
        return timezone.localdate()


def _itens_do_dia(profissional, data):
    inicio = servicos.momento(data, time.min)
    fim = inicio + timedelta(days=1)
    agendamentos = list(
        profissional.agendamentos.filter(inicio__gte=inicio, inicio__lt=fim).select_related("cliente", "procedimento")
    )
    bloqueios = servicos.bloqueios_de(profissional).filter(inicio__lt=fim, fim__gt=inicio)

    itens = [{"tipo": "agendamento", "inicio": a.inicio, "obj": a} for a in agendamentos if a.status != Status.CANCELADO]
    itens += [{"tipo": "bloqueio", "inicio": max(b.inicio, inicio), "obj": b} for b in bloqueios]
    itens.sort(key=lambda item: item["inicio"])
    cancelados = sum(1 for a in agendamentos if a.status == Status.CANCELADO)
    return itens, cancelados


def _procedimento_de(profissional, valor):
    """Procedimento ativo que o profissional realiza, a partir do valor enviado pelo formulário."""
    if not str(valor or "").isdigit():
        return None
    return profissional.procedimentos.filter(pk=valor, ativo=True).first()


def _horarios_livres(profissional, procedimento, data_texto, ignorar=None):
    """Horários livres para montar a lista de escolha; None se ainda faltam dados."""
    try:
        data = date.fromisoformat(data_texto or "")
    except ValueError:
        return None
    if procedimento is None:
        return None
    return servicos.horarios_disponiveis(
        profissional, procedimento, data, respeitar_antecedencia=False, ignorar=ignorar
    )


# Agenda


@profissional_required
def dia(request):
    profissional = request.user.profissional
    data = _data_da_url(request)
    itens, cancelados = _itens_do_dia(profissional, data)
    return render(
        request,
        "agenda/dia.html",
        {
            "data": data,
            "hoje": timezone.localdate(),
            "anterior": data - timedelta(days=1),
            "proximo": data + timedelta(days=1),
            "itens": itens,
            "cancelados": cancelados,
            "expediente": servicos.expediente(profissional, data),
        },
    )


@profissional_required
def semana(request):
    profissional = request.user.profissional
    data = _data_da_url(request)
    segunda = data - timedelta(days=data.weekday())
    dias = []
    for i in range(7):
        d = segunda + timedelta(days=i)
        itens, _ = _itens_do_dia(profissional, d)
        dias.append({"data": d, "itens": itens, "expediente": servicos.expediente(profissional, d)})
    return render(
        request,
        "agenda/semana.html",
        {
            "dias": dias,
            "hoje": timezone.localdate(),
            "anterior": segunda - timedelta(days=7),
            "proximo": segunda + timedelta(days=7),
        },
    )


# Agendamentos


@profissional_required
def novo(request):
    profissional = request.user.profissional
    form = AgendamentoForm(
        request.POST or None, profissional=profissional, initial={"data": _data_da_url(request)}
    )

    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        try:
            with transaction.atomic():
                cliente = servicos.obter_cliente(dados["nome"], dados["telefone"], dados["data_nascimento"])
                agendamento = servicos.agendar(
                    cliente=cliente,
                    profissional=profissional,
                    procedimento=dados["procedimento"],
                    inicio=dados["inicio"],
                    origem=Agendamento.Origem.PROFISSIONAL,
                    respeitar_antecedencia=False,
                )
        except servicos.AgendamentoInvalido as erro:
            form.add_error(None, str(erro))
        else:
            messages.success(request, f"Agendamento de {cliente.nome} criado.")
            return redirect(f"{reverse('agenda:dia')}?data={timezone.localdate(agendamento.inicio):%Y-%m-%d}")

    procedimento = _procedimento_de(profissional, form.data.get("procedimento"))
    return render(
        request,
        "agenda/novo.html",
        {
            "form": form,
            "horarios": _horarios_livres(profissional, procedimento, form.data.get("data")),
            "escolhido": form.data.get("inicio"),
        },
    )


@login_required
def horarios_livres(request):
    """Fragmento HTMX com os horários livres para o procedimento e a data."""
    ignorar = None
    if request.GET.get("agendamento"):
        if not request.GET["agendamento"].isdigit():
            raise Http404
        ignorar = _agendamento_acessivel(request, request.GET["agendamento"])
        profissional, procedimento = ignorar.profissional, ignorar.procedimento
    elif hasattr(request.user, "profissional"):
        profissional = request.user.profissional
        procedimento = _procedimento_de(profissional, request.GET.get("procedimento"))
    else:
        raise PermissionDenied
    horarios = _horarios_livres(profissional, procedimento, request.GET.get("data"), ignorar=ignorar)
    return render(request, "agenda/_horarios_livres.html", {"horarios": horarios})


@login_required
def detalhe(request, pk):
    agendamento = _agendamento_acessivel(request, pk)
    return render(
        request,
        "agenda/detalhe.html",
        {
            "agendamento": agendamento,
            "recursos": agendamento.recursos.order_by("nome"),
            "pode_registrar_presenca": agendamento.status in Agendamento.OCUPAM_AGENDA
            and agendamento.inicio <= timezone.now(),
        },
    )


@login_required
def remarcar(request, pk):
    agendamento = _agendamento_acessivel(request, pk)
    if not agendamento.em_aberto:
        messages.error(request, "Este agendamento não pode mais ser remarcado.")
        return redirect("agenda:detalhe", pk=pk)

    form = HorarioEscolhidoForm(request.POST or None, initial={"data": timezone.localdate(agendamento.inicio)})
    if request.method == "POST" and form.is_valid():
        try:
            servicos.reagendar(agendamento, form.cleaned_data["inicio"])
        except servicos.AgendamentoInvalido as erro:
            form.add_error(None, str(erro))
        else:
            messages.success(request, "Agendamento remarcado.")
            return redirect("agenda:detalhe", pk=pk)

    data_texto = form.data.get("data") if form.is_bound else f"{timezone.localdate(agendamento.inicio):%Y-%m-%d}"
    return render(
        request,
        "agenda/remarcar.html",
        {
            "agendamento": agendamento,
            "form": form,
            "horarios": _horarios_livres(
                agendamento.profissional, agendamento.procedimento, data_texto, ignorar=agendamento
            ),
            "escolhido": form.data.get("inicio"),
        },
    )


@require_POST
@login_required
def cancelar(request, pk):
    agendamento = _agendamento_acessivel(request, pk)
    try:
        servicos.cancelar(agendamento, por=_origem(request.user, agendamento.profissional))
    except servicos.AgendamentoInvalido as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Agendamento cancelado.")
    return redirect("agenda:detalhe", pk=pk)


@require_POST
@login_required
def presenca(request, pk):
    agendamento = _agendamento_acessivel(request, pk)
    try:
        servicos.registrar_presenca(agendamento, compareceu=request.POST.get("compareceu") == "1")
    except servicos.AgendamentoInvalido as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Marcado como “{agendamento.get_status_display()}”.")
    return redirect("agenda:detalhe", pk=pk)


# Horários de trabalho e bloqueios


def _formularios_horario(profissional, dados=None):
    clinica = {h.dia_semana: h for h in HorarioClinica.objects.all()}
    atuais = {}
    for h in profissional.horarios.all():
        atuais.setdefault(h.dia_semana, []).append(h)

    formularios = []
    for dia_semana, nome in DiaSemana.choices:
        periodos = atuais.get(dia_semana, [])
        horario_clinica = clinica.get(dia_semana)
        inicial = {"trabalha": bool(periodos)}
        if periodos:
            inicial.update(inicio1=periodos[0].inicio, fim1=periodos[0].fim)
            if len(periodos) > 1:
                inicial.update(inicio2=periodos[1].inicio, fim2=periodos[1].fim)
        elif horario_clinica:
            inicial.update(inicio1=horario_clinica.inicio, fim1=horario_clinica.fim)
        formularios.append(
            HorarioTrabalhoDiaForm(
                dados, prefix=f"dia{dia_semana}", initial=inicial, dia=dia_semana, nome_dia=nome, clinica=horario_clinica
            )
        )
    return formularios


@profissional_required
def horarios(request):
    profissional = request.user.profissional
    dados = request.POST if request.method == "POST" else None
    formularios = _formularios_horario(profissional, dados)

    if dados is not None and all([f.is_valid() for f in formularios]):
        with transaction.atomic():
            profissional.horarios.all().delete()
            HorarioTrabalho.objects.bulk_create(
                HorarioTrabalho(profissional=profissional, dia_semana=f.dia, inicio=inicio, fim=fim)
                for f in formularios
                if f.cleaned_data["trabalha"]
                for inicio, fim in f.cleaned_data["periodos"]
            )
            afetados = servicos.sinalizar_fora_do_expediente(profissional)
        messages.success(request, "Horários de trabalho salvos.")
        if afetados:
            messages.error(request, f"{afetados} agendamento(s) ficaram fora do expediente e precisam ser reagendados.")
        return redirect("agenda:horarios")

    return render(request, "agenda/horarios.html", {"formularios": formularios})


@profissional_required
def bloqueios(request):
    profissional = request.user.profissional
    form = BloqueioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            bloqueio = Bloqueio.objects.create(
                profissional=profissional,
                inicio=form.cleaned_data["inicio"],
                fim=form.cleaned_data["fim"],
                motivo=form.cleaned_data["motivo"],
            )
            afetados = servicos.aplicar_bloqueio(bloqueio)
        messages.success(request, f"Bloqueio criado: {bloqueio.periodo_legivel()}.")
        if afetados:
            messages.error(request, f"{afetados} agendamento(s) no período precisam ser reagendados.")
        return redirect("agenda:bloqueios")

    proximos = servicos.bloqueios_de(profissional).filter(fim__gt=timezone.now())
    return render(request, "agenda/bloqueios.html", {"form": form, "bloqueios": proximos})


@require_POST
@profissional_required
def excluir_bloqueio(request, pk):
    bloqueio = get_object_or_404(Bloqueio, pk=pk, profissional=request.user.profissional)
    bloqueio.delete()
    messages.success(request, "Bloqueio removido.")
    return redirect("agenda:bloqueios")
