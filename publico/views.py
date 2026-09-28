import calendar
from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from agenda import servicos
from agenda.forms import HorarioEscolhidoForm
from agenda.models import Agendamento
from catalogo.models import Procedimento
from clinica.models import Estabelecimento, FotoEstabelecimento
from equipe.models import Profissional

from . import acesso
from .forms import AcessoForm, ReservaForm

Status = Agendamento.Status

MENSAGEM_SEM_DIA = "Escolha um dia no calendário para ver os horários livres."


def do_estabelecimento(view):
    """Troca o slug do endereço pelo estabelecimento, que a view recebe como segundo argumento."""

    @wraps(view)
    def wrapper(request, *args, estabelecimento, **kwargs):
        estabelecimento = get_object_or_404(Estabelecimento, slug__iexact=estabelecimento)
        request.estabelecimento_publico = estabelecimento
        return view(request, estabelecimento, *args, **kwargs)

    return wrapper


def _procedimentos_disponiveis(estabelecimento):
    """Procedimentos ativos com pelo menos um profissional ativo que os realize."""
    com_profissional = Profissional.objects.filter(ativo=True, procedimentos=OuterRef("pk"))
    return Procedimento.objects.filter(estabelecimento=estabelecimento, ativo=True).filter(Exists(com_profissional))


def _janela(estabelecimento):
    """Datas que o cliente pode escolher (antecedência máxima do estabelecimento)."""
    hoje = timezone.localdate()
    return hoje, hoje + timedelta(days=estabelecimento.antecedencia_maxima_dias)


def _data(texto):
    try:
        return date.fromisoformat(texto or "")
    except ValueError:
        return None


def _escolhido(queryset, valor):
    if not str(valor or "").isdigit():
        return None
    return queryset.filter(pk=valor).first()


# Escolha do estabelecimento


def estabelecimentos(request):
    """Página inicial: os estabelecimentos com agendamento online. Se só houver um, vai direto para ele."""
    com_procedimento = Procedimento.objects.filter(
        estabelecimento=OuterRef("pk"), ativo=True, profissionais__ativo=True
    )
    disponiveis = Estabelecimento.objects.filter(Exists(com_procedimento))
    if len(disponiveis) == 1:
        return redirect("publico:inicio", disponiveis[0].slug)
    return render(request, "publico/estabelecimentos.html", {"estabelecimentos": disponiveis})


def foto(request, estabelecimento):
    """Foto do estabelecimento. O endereço muda a cada foto nova (?v=...), então pode ficar em cache por um ano."""
    foto = get_object_or_404(FotoEstabelecimento, estabelecimento__slug__iexact=estabelecimento)
    resposta = HttpResponse(bytes(foto.conteudo), content_type=foto.tipo)
    resposta["Cache-Control"] = "public, max-age=31536000, immutable"
    return resposta


def legado_reservar(request, pk):
    """Links antigos (/agendar/<pk>/, de antes dos vários estabelecimentos)."""
    procedimento = get_object_or_404(Procedimento, pk=pk)
    return redirect("publico:reservar", procedimento.estabelecimento.slug, pk)


def legado_meus(request):
    if Estabelecimento.objects.count() == 1:
        return redirect("publico:meus", Estabelecimento.objects.get().slug)
    return redirect("core:home")


# Agendar


@do_estabelecimento
def inicio(request, estabelecimento):
    return render(request, "publico/inicio.html", {"procedimentos": _procedimentos_disponiveis(estabelecimento)})


def _horarios_para_reserva(procedimento, profissional, data):
    if profissional is None or data is None:
        return None
    return servicos.horarios_disponiveis(profissional, procedimento, data, respeitar_antecedencia=True)


def _dias_livres(estabelecimento, procedimento, profissional, inicio, fim):
    """Dias entre `inicio` e `fim` (dentro da janela do cliente) com pelo menos um horário livre."""
    data_minima, data_maxima = _janela(estabelecimento)
    dia, fim = max(inicio, data_minima), min(fim, data_maxima)
    while dia <= fim:
        if _horarios_para_reserva(procedimento, profissional, dia):
            yield dia
        dia += timedelta(days=1)


def _primeiro_dia_livre(estabelecimento, procedimento, profissional):
    if profissional is None:
        return None
    return next(_dias_livres(estabelecimento, procedimento, profissional, *_janela(estabelecimento)), None)


def _calendario(estabelecimento, procedimento, profissional, mes, escolhida):
    """Contexto do calendário do mês de `mes`: só os dias com horário livre podem ser escolhidos."""
    mes = mes.replace(day=1)
    ultimo = mes.replace(day=calendar.monthrange(mes.year, mes.month)[1])
    livres = set(_dias_livres(estabelecimento, procedimento, profissional, mes, ultimo)) if profissional else set()
    data_minima, data_maxima = _janela(estabelecimento)
    anterior, seguinte = (mes - timedelta(days=1)).replace(day=1), ultimo + timedelta(days=1)
    return {
        "mes": mes,
        "semanas": [
            [{"dia": dia, "no_mes": dia.month == mes.month, "livre": dia in livres} for dia in semana]
            for semana in calendar.Calendar(firstweekday=calendar.SUNDAY).monthdatescalendar(mes.year, mes.month)
        ],
        "tem_dia_livre": bool(livres),
        "escolhida": escolhida,
        "mes_anterior": anterior if anterior >= data_minima.replace(day=1) else None,
        "mes_seguinte": seguinte if seguinte <= data_maxima else None,
    }


@do_estabelecimento
def reservar(request, estabelecimento, pk):
    procedimento = get_object_or_404(_procedimentos_disponiveis(estabelecimento), pk=pk)
    profissionais = procedimento.profissionais.filter(ativo=True)

    form = ReservaForm(
        request.POST or None,
        profissionais=profissionais,
        initial={"profissional": profissionais.first() if profissionais.count() == 1 else None},
    )
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        if acesso.bloqueado(request, estabelecimento, dados["telefone"]):
            form.add_error(None, acesso.MSG_BLOQUEADO)
        else:
            try:
                with transaction.atomic():
                    cliente = acesso.cliente_para_reserva(
                        estabelecimento, dados["nome"], dados["telefone"], dados["data_nascimento"]
                    )
                    agendamento = servicos.agendar(
                        cliente=cliente,
                        profissional=dados["profissional"],
                        procedimento=procedimento,
                        inicio=dados["inicio"],
                        origem=Agendamento.Origem.CLIENTE,
                        respeitar_antecedencia=True,
                    )
            except acesso.DadosNaoConferem:
                acesso.registrar_falha(request, estabelecimento, dados["telefone"])
                form.add_error(
                    None,
                    "Este telefone já está cadastrado com outra data de nascimento. "
                    "Confira os dados ou fale com o estabelecimento.",
                )
            except servicos.AgendamentoInvalido as erro:
                form.add_error(None, str(erro))
            else:
                acesso.conceder(request, cliente)
                request.session["ultimo_agendamento"] = agendamento.pk
                return redirect("publico:confirmado", estabelecimento.slug)

    if form.is_bound:
        profissional = _escolhido(profissionais, form.data.get("profissional"))
        data = _data(form.data.get("data"))
    else:
        profissional = form.initial["profissional"]
        data = _primeiro_dia_livre(estabelecimento, procedimento, profissional)
    return render(
        request,
        "publico/reservar.html",
        {
            "procedimento": procedimento,
            "profissionais": profissionais,
            "form": form,
            "profissional_escolhido": profissional,
            "horarios": _horarios_para_reserva(procedimento, profissional, data),
            "escolhido": form.data.get("inicio"),
            **_calendario(estabelecimento, procedimento, profissional, data or _janela(estabelecimento)[0], data),
        },
    )


@do_estabelecimento
def calendario(request, estabelecimento, pk):
    """Fragmento HTMX com o calendário e, fora da banda, os horários livres.

    Sem `mes` (troca de profissional), já escolhe o primeiro dia livre.
    Com `mes` (navegação entre meses), nenhum dia fica escolhido.
    """
    procedimento = get_object_or_404(_procedimentos_disponiveis(estabelecimento), pk=pk)
    profissional = _escolhido(procedimento.profissionais.filter(ativo=True), request.GET.get("profissional"))
    mes = _data(request.GET.get("mes"))
    data = None if mes else _primeiro_dia_livre(estabelecimento, procedimento, profissional)
    return render(
        request,
        "publico/_calendario.html",
        {
            "procedimento": procedimento,
            "profissional_escolhido": profissional,
            "horarios": _horarios_para_reserva(procedimento, profissional, data),
            "atualizar_horarios": True,
            **_calendario(estabelecimento, procedimento, profissional, mes or data or _janela(estabelecimento)[0], data),
        },
    )


@do_estabelecimento
def horarios(request, estabelecimento, pk):
    """Fragmento HTMX com os horários livres para o cliente (respeita a antecedência)."""
    procedimento = get_object_or_404(_procedimentos_disponiveis(estabelecimento), pk=pk)
    profissional = _escolhido(procedimento.profissionais.filter(ativo=True), request.GET.get("profissional"))
    horarios = _horarios_para_reserva(procedimento, profissional, _data(request.GET.get("data")))
    return render(
        request,
        "agenda/_horarios_livres.html",
        {"horarios": horarios, "mensagem_vazia": MENSAGEM_SEM_DIA},
    )


@do_estabelecimento
def confirmado(request, estabelecimento):
    cliente = acesso.cliente_da_sessao(request, estabelecimento)
    agendamento_id = request.session.get("ultimo_agendamento")
    if cliente is None or agendamento_id is None:
        return redirect("publico:meus", estabelecimento.slug)
    agendamento = get_object_or_404(
        Agendamento.objects.select_related("procedimento", "profissional"), pk=agendamento_id, cliente=cliente
    )
    return render(request, "publico/confirmado.html", {"agendamento": agendamento})


# Meus agendamentos


@do_estabelecimento
def meus(request, estabelecimento):
    cliente = acesso.cliente_da_sessao(request, estabelecimento)
    if cliente is None:
        return _entrar(request, estabelecimento)

    agora = timezone.now()
    agendamentos = cliente.agendamentos.select_related("procedimento", "profissional")
    return render(
        request,
        "publico/meus.html",
        {
            "cliente": cliente,
            "proximos": agendamentos.filter(status__in=Agendamento.EM_ABERTO, inicio__gte=agora),
            "historico": agendamentos.exclude(status__in=Agendamento.EM_ABERTO, inicio__gte=agora).order_by("-inicio")[:10],
        },
    )


def _entrar(request, estabelecimento):
    form = AcessoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        telefone, nascimento = form.cleaned_data["telefone"], form.cleaned_data["data_nascimento"]
        if acesso.bloqueado(request, estabelecimento, telefone):
            form.add_error(None, acesso.MSG_BLOQUEADO)
        else:
            cliente = acesso.identificar(estabelecimento, telefone, nascimento)
            if cliente is None:
                acesso.registrar_falha(request, estabelecimento, telefone)
                form.add_error(None, acesso.MSG_NAO_CONFERE)
            else:
                acesso.conceder(request, cliente)
                return redirect("publico:meus", estabelecimento.slug)
    return render(request, "publico/entrar.html", {"form": form})


@require_POST
@do_estabelecimento
def sair(request, estabelecimento):
    acesso.encerrar(request, estabelecimento)
    request.session.pop("ultimo_agendamento", None)
    return redirect("publico:meus", estabelecimento.slug)


def _agendamento_do_cliente(cliente, pk):
    """Agendamento em aberto e futuro do cliente; os demais não podem ser alterados por ele."""
    agendamento = get_object_or_404(
        Agendamento.objects.select_related("procedimento", "profissional"), pk=pk, cliente=cliente
    )
    if not agendamento.em_aberto or agendamento.inicio <= timezone.now():
        raise Http404
    return agendamento


@require_POST
@do_estabelecimento
@acesso.cliente_required
def cancelar(request, estabelecimento, cliente, pk):
    agendamento = _agendamento_do_cliente(cliente, pk)
    servicos.cancelar(agendamento, por=Agendamento.Origem.CLIENTE)
    messages.success(request, "Agendamento cancelado.")
    return redirect("publico:meus", estabelecimento.slug)


@do_estabelecimento
@acesso.cliente_required
def remarcar(request, estabelecimento, cliente, pk):
    agendamento = _agendamento_do_cliente(cliente, pk)
    form = HorarioEscolhidoForm(request.POST or None, initial={"data": timezone.localdate(agendamento.inicio)})
    if request.method == "POST" and form.is_valid():
        try:
            # Remarcação do cliente é livre: qualquer horário livre futuro (PROJETO.md 3.1)
            servicos.reagendar(agendamento, form.cleaned_data["inicio"], respeitar_antecedencia=False)
        except servicos.AgendamentoInvalido as erro:
            form.add_error(None, str(erro))
        else:
            messages.success(request, "Agendamento remarcado.")
            return redirect("publico:meus", estabelecimento.slug)

    data = _data(form.data.get("data")) if form.is_bound else timezone.localdate(agendamento.inicio)
    return render(
        request,
        "publico/remarcar.html",
        {
            "agendamento": agendamento,
            "form": form,
            "horarios": _horarios_remarcacao(agendamento, data),
            "escolhido": form.data.get("inicio"),
        },
    )


def _horarios_remarcacao(agendamento, data):
    if data is None:
        return None
    return servicos.horarios_disponiveis(
        agendamento.profissional, agendamento.procedimento, data, respeitar_antecedencia=False, ignorar=agendamento
    )


@do_estabelecimento
@acesso.cliente_required
def horarios_remarcacao(request, estabelecimento, cliente, pk):
    agendamento = _agendamento_do_cliente(cliente, pk)
    return render(
        request,
        "agenda/_horarios_livres.html",
        {"horarios": _horarios_remarcacao(agendamento, _data(request.GET.get("data")))},
    )
