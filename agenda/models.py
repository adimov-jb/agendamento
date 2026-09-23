from datetime import time, timedelta

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import F, Func, Q
from django.utils import timezone

from catalogo.models import Procedimento, Recurso
from clinica.models import DiaSemana
from equipe.models import Profissional


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


def sobreposicao_de_periodo():
    """Expressão das exclusion constraints: períodos [inicio, fim) que se sobrepõem."""
    return (TsTzRange("inicio", "fim", RangeBoundary()), RangeOperators.OVERLAPS)


class Cliente(models.Model):
    nome = models.CharField("nome", max_length=100)
    telefone = models.CharField("telefone", max_length=20, unique=True, help_text="Formato +5511999999999.")
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    consentimento_em = models.DateTimeField("consentimento LGPD em", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.nome


class HorarioTrabalho(models.Model):
    """Período de trabalho semanal. Vários por dia permitem pausas (ex.: almoço)."""

    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE, related_name="horarios")
    dia_semana = models.PositiveSmallIntegerField("dia da semana", choices=DiaSemana.choices)
    inicio = models.TimeField("início")
    fim = models.TimeField("fim")

    class Meta:
        ordering = ["dia_semana", "inicio"]
        verbose_name = "horário de trabalho"
        verbose_name_plural = "horários de trabalho"
        constraints = [
            models.CheckConstraint(condition=Q(fim__gt=F("inicio")), name="horario_trabalho_fim_apos_inicio"),
        ]

    def __str__(self):
        return f"{self.profissional} · {self.get_dia_semana_display()} {self.inicio:%H:%M}–{self.fim:%H:%M}"


class Bloqueio(models.Model):
    profissional = models.ForeignKey(
        Profissional,
        on_delete=models.CASCADE,
        related_name="bloqueios",
        null=True,
        blank=True,
        help_text="Vazio = bloqueio geral da clínica (vale para todos).",
    )
    inicio = models.DateTimeField("início")
    fim = models.DateTimeField("fim")
    motivo = models.CharField("motivo", max_length=100, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["inicio"]
        verbose_name = "bloqueio"
        verbose_name_plural = "bloqueios"
        constraints = [
            models.CheckConstraint(condition=Q(fim__gt=F("inicio")), name="bloqueio_fim_apos_inicio"),
        ]

    def __str__(self):
        return f"{self.profissional or 'Clínica'} · {self.periodo_legivel()}"

    @property
    def geral(self):
        return self.profissional_id is None

    def periodo_legivel(self):
        inicio, fim = timezone.localtime(self.inicio), timezone.localtime(self.fim)
        if inicio.time() == time.min and fim.time() == time.min:
            ultimo_dia = (fim - timedelta(days=1)).date()
            if ultimo_dia == inicio.date():
                return f"{inicio:%d/%m} (dia inteiro)"
            return f"{inicio:%d/%m} a {ultimo_dia:%d/%m} (dias inteiros)"
        if inicio.date() == fim.date():
            return f"{inicio:%d/%m} das {inicio:%H:%M} às {fim:%H:%M}"
        return f"{inicio:%d/%m %H:%M} a {fim:%d/%m %H:%M}"


class Agendamento(models.Model):
    class Status(models.TextChoices):
        AGENDADO = "agendado", "Agendado"
        ATENDIDO = "atendido", "Atendido"
        FALTOU = "faltou", "Faltou"
        CANCELADO = "cancelado", "Cancelado"
        PRECISA_REAGENDAR = "precisa_reagendar", "Precisa reagendar"

    class Origem(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        PROFISSIONAL = "profissional", "Profissional"
        GERENTE = "gerente", "Gerente"

    # Status que ocupam o horário do profissional
    OCUPAM_AGENDA = [Status.AGENDADO, Status.ATENDIDO, Status.FALTOU]
    # Status que ainda podem ser remarcados ou cancelados
    EM_ABERTO = [Status.AGENDADO, Status.PRECISA_REAGENDAR]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="agendamentos")
    profissional = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name="agendamentos")
    procedimento = models.ForeignKey(Procedimento, on_delete=models.PROTECT, related_name="agendamentos")
    inicio = models.DateTimeField("início")
    fim = models.DateTimeField("fim", help_text="Fim do intervalo de higienização (início + duração + intervalo).")
    # Cópias do procedimento no momento do agendamento
    duracao_minutos = models.PositiveSmallIntegerField("duração (minutos)")
    intervalo_minutos = models.PositiveSmallIntegerField("intervalo (minutos)")
    preco = models.DecimalField("preço (R$)", max_digits=8, decimal_places=2)

    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.AGENDADO)
    origem = models.CharField("criado por", max_length=20, choices=Origem.choices)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    cancelado_em = models.DateTimeField("cancelado em", null=True, blank=True)
    cancelado_por = models.CharField("cancelado por", max_length=20, choices=Origem.choices, blank=True)

    recursos = models.ManyToManyField(Recurso, through="AgendamentoRecurso", blank=True)

    class Meta:
        ordering = ["inicio"]
        verbose_name = "agendamento"
        verbose_name_plural = "agendamentos"
        constraints = [
            models.CheckConstraint(condition=Q(fim__gt=F("inicio")), name="agendamento_fim_apos_inicio"),
            ExclusionConstraint(
                name="agendamento_sem_sobreposicao_profissional",
                expressions=[sobreposicao_de_periodo(), ("profissional", RangeOperators.EQUAL)],
                condition=Q(status__in=["agendado", "atendido", "faltou"]),
            ),
        ]

    def __str__(self):
        return f"{self.cliente} · {self.procedimento} · {timezone.localtime(self.inicio):%d/%m %H:%M}"

    @property
    def fim_atendimento(self):
        return self.inicio + timedelta(minutes=self.duracao_minutos)

    @property
    def em_aberto(self):
        return self.status in self.EM_ABERTO


class AgendamentoRecurso(models.Model):
    """Unidade de recurso alocada. Só existe enquanto o agendamento ocupa a agenda."""

    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, related_name="alocacoes")
    recurso = models.ForeignKey(Recurso, on_delete=models.PROTECT, related_name="alocacoes")
    inicio = models.DateTimeField()
    fim = models.DateTimeField()

    class Meta:
        verbose_name = "recurso alocado"
        verbose_name_plural = "recursos alocados"
        constraints = [
            ExclusionConstraint(
                name="recurso_sem_sobreposicao",
                expressions=[sobreposicao_de_periodo(), ("recurso", RangeOperators.EQUAL)],
            ),
        ]

    def __str__(self):
        return f"{self.recurso} · {self.agendamento}"
