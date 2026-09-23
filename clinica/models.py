from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Configuracao(models.Model):
    """Configuração única da clínica (sempre pk=1)."""

    GRADES = [(5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min")]

    nome_clinica = models.CharField("nome da clínica", max_length=100, default="Agendamento")
    grade_minutos = models.PositiveSmallIntegerField(
        "grade de horários",
        choices=GRADES,
        default=15,
        help_text="Espaçamento entre os horários oferecidos ao cliente.",
    )
    antecedencia_minima_horas = models.PositiveSmallIntegerField(
        "antecedência mínima (horas)",
        default=2,
        help_text="Com quantas horas de antecedência, no mínimo, o cliente pode agendar.",
    )
    antecedencia_maxima_dias = models.PositiveSmallIntegerField(
        "antecedência máxima (dias)",
        default=60,
        validators=[MinValueValidator(1)],
        help_text="Até quantos dias à frente o cliente pode agendar.",
    )

    class Meta:
        verbose_name = "configuração"
        verbose_name_plural = "configuração"

    def __str__(self):
        return self.nome_clinica

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def atual(cls):
        return cls.objects.get_or_create(pk=1)[0]


class DiaSemana(models.IntegerChoices):
    # Mesma numeração de datetime.weekday()
    SEGUNDA = 0, "Segunda-feira"
    TERCA = 1, "Terça-feira"
    QUARTA = 2, "Quarta-feira"
    QUINTA = 3, "Quinta-feira"
    SEXTA = 4, "Sexta-feira"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class HorarioClinica(models.Model):
    """Horário de funcionamento. Dia sem registro = clínica fechada."""

    dia_semana = models.PositiveSmallIntegerField("dia da semana", choices=DiaSemana.choices, unique=True)
    inicio = models.TimeField("abre às")
    fim = models.TimeField("fecha às")

    class Meta:
        ordering = ["dia_semana"]
        verbose_name = "horário da clínica"
        verbose_name_plural = "horários da clínica"
        constraints = [
            models.CheckConstraint(condition=Q(fim__gt=F("inicio")), name="horario_clinica_fim_apos_inicio"),
        ]

    def __str__(self):
        return f"{self.get_dia_semana_display()}: {self.inicio:%H:%M}–{self.fim:%H:%M}"
