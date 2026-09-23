from datetime import date, timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from agenda import servicos
from agenda.forms import HorarioEscolhidoForm
from agenda.models import Agendamento
from catalogo.models import Procedimento
from clinica.models import Configuracao
from equipe.models import Profissional

from . import acesso
from .forms import AcessoForm, ReservaForm

Status = Agendamento.Status


def _procedimentos_disponiveis():
    """Procedimentos ativos com pelo menos um profissional ativo que os realize."""
    com_profissional = Profissional.objects.filter(ativo=True, procedimentos=OuterRef("pk"))
    return Procedimento.objects.filter(ativo=True).filter(Exists(com_profissional))


def _janela():
    """Datas que o cliente pode escolher (antecedência máxima da configuração)."""
    hoje = timezone.localdate()
    return hoje, hoje + timedelta(days=Configuracao.atual().antecedencia_maxima_dias)


def _data(texto):
    try:
        return date.fromisoformat(texto or "")
    except ValueError:
        return None


def _escolhido(queryset, valor):
    if not str(valor or "").isdigit():
        return None
    return queryset.filter(pk=valor).first()


# Agendar


def inicio(request):
    return render(request, "publico/inicio.html", {"procedimentos": _procedimentos_disponiveis()})


def _horarios_para_reserva(procedimento, profissional, data):
    if profissional is None or data is None:
        return None
    return servicos.horarios_disponiveis(profissional, procedimento, data, respeitar_antecedencia=True)


def reservar(request, pk):
    procedimento = get_object_or_404(_procedimentos_disponiveis(), pk=pk)
    profissionais = procedimento.profissionais.filter(ativo=True)
    data_minima, data_maxima = _janela()

    form = ReservaForm(
        request.POST or None,
        profissionais=profissionais,
        data_minima=data_minima,
        data_maxima=data_maxima,
        initial={"data": data_minima, "profissional": profissionais.first() if profissionais.count() == 1 else None},
    )
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        if acesso.bloqueado(request, dados["telefone"]):
            form.add_error(None, acesso.MSG_BLOQUEADO)
        else:
            try:
                with transaction.atomic():
                    cliente = acesso.cliente_para_reserva(dados["nome"], dados["telefone"], dados["data_nascimento"])
                    agendamento = servicos.agendar(
                        cliente=cliente,
                        profissional=dados["profissional"],
                        procedimento=procedimento,
                        inicio=dados["inicio"],
                        origem=Agendamento.Origem.CLIENTE,
                        respeitar_antecedencia=True,
                    )
            except acesso.DadosNaoConferem:
                acesso.registrar_falha(request, dados["telefone"])
                form.add_error(
                    None,
                    "Este telefone já está cadastrado com outra data de nascimento. "
                    "Confira os dados ou fale com a clínica.",
                )
            except servicos.AgendamentoInvalido as erro:
                form.add_error(None, str(erro))
            else:
                acesso.conceder(request, cliente)
                request.session["ultimo_agendamento"] = agendamento.pk
                return redirect("publico:confirmado")

    if form.is_bound:
        profissional = _escolhido(profissionais, form.data.get("profissional"))
        data = _data(form.data.get("data"))
    else:
        profissional, data = form.initial["profissional"], data_minima
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
        },
    )


def horarios(request, pk):
    """Fragmento HTMX com os horários livres para o cliente (respeita a antecedência)."""
    procedimento = get_object_or_404(_procedimentos_disponiveis(), pk=pk)
    profissional = _escolhido(procedimento.profissionais.filter(ativo=True), request.GET.get("profissional"))
    horarios = _horarios_para_reserva(procedimento, profissional, _data(request.GET.get("data")))
    return render(
        request,
        "agenda/_horarios_livres.html",
        {"horarios": horarios, "mensagem_vazia": "Escolha o profissional e a data para ver os horários livres."},
    )


def confirmado(request):
    cliente = acesso.cliente_da_sessao(request)
    agendamento_id = request.session.get("ultimo_agendamento")
    if cliente is None or agendamento_id is None:
        return redirect("publico:meus")
    agendamento = get_object_or_404(
        Agendamento.objects.select_related("procedimento", "profissional"), pk=agendamento_id, cliente=cliente
    )
    return render(request, "publico/confirmado.html", {"agendamento": agendamento})


# Meus agendamentos


def meus(request):
    cliente = acesso.cliente_da_sessao(request)
    if cliente is None:
        return _entrar(request)

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


def _entrar(request):
    form = AcessoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        telefone, nascimento = form.cleaned_data["telefone"], form.cleaned_data["data_nascimento"]
        if acesso.bloqueado(request, telefone):
            form.add_error(None, acesso.MSG_BLOQUEADO)
        else:
            cliente = acesso.identificar(telefone, nascimento)
            if cliente is None:
                acesso.registrar_falha(request, telefone)
                form.add_error(None, acesso.MSG_NAO_CONFERE)
            else:
                acesso.conceder(request, cliente)
                return redirect("publico:meus")
    return render(request, "publico/entrar.html", {"form": form})


@require_POST
def sair(request):
    acesso.encerrar(request)
    request.session.pop("ultimo_agendamento", None)
    return redirect("publico:meus")


def _agendamento_do_cliente(cliente, pk):
    """Agendamento em aberto e futuro do cliente; os demais não podem ser alterados por ele."""
    agendamento = get_object_or_404(
        Agendamento.objects.select_related("procedimento", "profissional"), pk=pk, cliente=cliente
    )
    if not agendamento.em_aberto or agendamento.inicio <= timezone.now():
        raise Http404
    return agendamento


@require_POST
@acesso.cliente_required
def cancelar(request, cliente, pk):
    agendamento = _agendamento_do_cliente(cliente, pk)
    servicos.cancelar(agendamento, por=Agendamento.Origem.CLIENTE)
    messages.success(request, "Agendamento cancelado.")
    return redirect("publico:meus")


@acesso.cliente_required
def remarcar(request, cliente, pk):
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
            return redirect("publico:meus")

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


@acesso.cliente_required
def horarios_remarcacao(request, cliente, pk):
    agendamento = _agendamento_do_cliente(cliente, pk)
    return render(
        request,
        "agenda/_horarios_livres.html",
        {"horarios": _horarios_remarcacao(agendamento, _data(request.GET.get("data")))},
    )
