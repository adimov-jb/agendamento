"""Números dos relatórios do gerente (PROJETO.md, seção 3.3)."""

from datetime import time, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Agendamento
from .servicos import momento

Status = Agendamento.Status

LIMITE_CLIENTES = 10


def _metricas(agora):
    """Contagens e somas por status. Faturamento previsto = atendidos + ainda agendados."""
    return {
        "total": Count("pk"),
        "atendidos": Count("pk", filter=Q(status=Status.ATENDIDO)),
        "faltas": Count("pk", filter=Q(status=Status.FALTOU)),
        "cancelados": Count("pk", filter=Q(status=Status.CANCELADO)),
        "a_realizar": Count("pk", filter=Q(status=Status.AGENDADO, inicio__gte=agora)),
        "sem_registro": Count("pk", filter=Q(status=Status.AGENDADO, inicio__lt=agora)),
        "reagendar": Count("pk", filter=Q(status=Status.PRECISA_REAGENDAR)),
        "realizado": Sum("preco", filter=Q(status=Status.ATENDIDO), default=0),
        "previsto": Sum("preco", filter=Q(status__in=[Status.ATENDIDO, Status.AGENDADO]), default=0),
    }


def _com_taxa(linha):
    """Taxa de faltas entre os atendimentos com presença registrada (None se não houver)."""
    registrados = linha["atendidos"] + linha["faltas"]
    linha["registrados"] = registrados
    linha["taxa_faltas"] = linha["faltas"] / registrados if registrados else None
    return linha


def gerar(data_inicio, data_fim, profissional=None, agora=None):
    """Relatório dos agendamentos com início entre as datas (inclusive)."""
    agora = agora or timezone.now()
    agendamentos = Agendamento.objects.filter(
        inicio__gte=momento(data_inicio, time.min),
        inicio__lt=momento(data_fim + timedelta(days=1), time.min),
    )
    if profissional:
        agendamentos = agendamentos.filter(profissional=profissional)

    metricas = _metricas(agora)
    totais = _com_taxa(agendamentos.aggregate(**metricas))
    # order_by explícito substitui a ordenação padrão (inicio), que entraria no GROUP BY
    por_profissional = [
        _com_taxa(linha)
        for linha in agendamentos.values("profissional_id", "profissional__nome")
        .annotate(**metricas)
        .order_by("profissional__nome")
    ]
    clientes_faltosos = [
        _com_taxa(linha)
        for linha in agendamentos.filter(status__in=[Status.ATENDIDO, Status.FALTOU])
        .values("cliente_id", "cliente__nome", "cliente__telefone")
        .annotate(
            faltas=Count("pk", filter=Q(status=Status.FALTOU)),
            atendidos=Count("pk", filter=Q(status=Status.ATENDIDO)),
        )
        .filter(faltas__gt=0)
        .order_by("-faltas", "cliente__nome")[:LIMITE_CLIENTES]
    ]
    return {"totais": totais, "por_profissional": por_profissional, "clientes_faltosos": clientes_faltosos}
