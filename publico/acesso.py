"""Identificação do cliente (telefone + data de nascimento), sessão e limite de tentativas."""

from datetime import datetime, timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from agenda.models import Cliente

from .models import TentativaFalha

JANELA = timedelta(minutes=15)
LIMITE_POR_TELEFONE = 5
LIMITE_POR_IP = 20
VALIDADE_SESSAO = timedelta(minutes=30)
CHAVE_SESSAO = "cliente_acesso"

MSG_BLOQUEADO = "Muitas tentativas. Aguarde 15 minutos e tente novamente."
MSG_NAO_CONFERE = "Telefone ou data de nascimento não conferem."


class DadosNaoConferem(Exception):
    pass


# Limite de tentativas


def ip_de(request):
    """IP do cliente. Atrás de N proxies confiáveis, é o N-ésimo do fim do X-Forwarded-For.

    Os anteriores podem ter sido inventados pelo próprio cliente; cada proxy confiável acrescenta o
    endereço de quem se conectou a ele.
    """
    proxies = settings.PROXIES_CONFIAVEIS
    encaminhados = [ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if ip.strip()]
    if proxies and len(encaminhados) >= proxies:
        return encaminhados[-proxies]
    return request.META.get("REMOTE_ADDR", "")


def bloqueado(request, telefone=None):
    recentes = TentativaFalha.objects.filter(criado_em__gte=timezone.now() - JANELA)
    if recentes.filter(chave=f"ip:{ip_de(request)}").count() >= LIMITE_POR_IP:
        return True
    return bool(telefone) and recentes.filter(chave=f"tel:{telefone}").count() >= LIMITE_POR_TELEFONE


def registrar_falha(request, telefone=None):
    chaves = [f"ip:{ip_de(request)}"] + ([f"tel:{telefone}"] if telefone else [])
    TentativaFalha.objects.bulk_create(TentativaFalha(chave=c) for c in chaves)
    TentativaFalha.objects.filter(criado_em__lt=timezone.now() - timedelta(days=1)).delete()


# Identificação


def identificar(telefone, data_nascimento):
    """Cliente cujo telefone e nascimento conferem; senão None."""
    return Cliente.objects.filter(telefone=telefone, data_nascimento=data_nascimento).first()


def cliente_para_reserva(nome, telefone, data_nascimento):
    """Cliente para um agendamento online.

    Telefone novo cria o cliente. Telefone existente exige a mesma data de nascimento
    (ou completa, se a equipe cadastrou sem ela). Registra o consentimento LGPD.
    """
    agora = timezone.now()
    cliente = Cliente.objects.filter(telefone=telefone).first()
    if cliente is None:
        return Cliente.objects.create(
            nome=nome, telefone=telefone, data_nascimento=data_nascimento, consentimento_em=agora
        )
    if cliente.data_nascimento and cliente.data_nascimento != data_nascimento:
        raise DadosNaoConferem
    cliente.data_nascimento = data_nascimento
    cliente.consentimento_em = cliente.consentimento_em or agora
    cliente.save(update_fields=["data_nascimento", "consentimento_em"])
    return cliente


# Sessão


def conceder(request, cliente):
    request.session[CHAVE_SESSAO] = {"id": cliente.pk, "ate": (timezone.now() + VALIDADE_SESSAO).isoformat()}


def encerrar(request):
    request.session.pop(CHAVE_SESSAO, None)


def cliente_da_sessao(request):
    """Cliente identificado nesta sessão; renova a validade a cada acesso."""
    dados = request.session.get(CHAVE_SESSAO)
    if not dados or datetime.fromisoformat(dados["ate"]) < timezone.now():
        encerrar(request)
        return None
    cliente = Cliente.objects.filter(pk=dados["id"]).first()
    if cliente:
        conceder(request, cliente)
    return cliente


def cliente_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        cliente = cliente_da_sessao(request)
        if cliente is None:
            messages.error(request, "Informe seus dados para ver seus agendamentos.")
            return redirect("publico:meus")
        return view(request, cliente, *args, **kwargs)

    return wrapper
