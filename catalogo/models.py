from django.core.validators import MinValueValidator
from django.db import models


class TipoRecurso(models.Model):
    """Categoria de recurso físico limitado (ex.: Sala, Laser)."""

    nome = models.CharField("nome", max_length=60, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "tipo de recurso"
        verbose_name_plural = "tipos de recurso"

    def __str__(self):
        return self.nome

    def unidades_ativas(self):
        return self.recursos.filter(ativo=True).count()


class Recurso(models.Model):
    """Unidade física de um tipo de recurso (ex.: Sala 1)."""

    tipo = models.ForeignKey(TipoRecurso, on_delete=models.PROTECT, related_name="recursos", verbose_name="tipo")
    nome = models.CharField("nome", max_length=60)
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["tipo__nome", "nome"]
        verbose_name = "recurso"
        verbose_name_plural = "recursos"
        constraints = [
            models.UniqueConstraint(fields=["tipo", "nome"], name="recurso_nome_unico_por_tipo"),
        ]

    def __str__(self):
        return self.nome


class Procedimento(models.Model):
    nome = models.CharField("nome", max_length=100, unique=True)
    descricao = models.TextField("descrição", blank=True)
    duracao_minutos = models.PositiveSmallIntegerField(
        "duração (minutos)",
        validators=[MinValueValidator(5)],
        help_text="Tempo do atendimento. É o tempo que o cliente vê.",
    )
    intervalo_minutos = models.PositiveSmallIntegerField(
        "intervalo (minutos)",
        default=0,
        help_text="Tempo após o atendimento para higienização. Bloqueia a agenda, mas não aparece para o cliente.",
    )
    preco = models.DecimalField("preço (R$)", max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "procedimento"
        verbose_name_plural = "procedimentos"

    def __str__(self):
        return self.nome

    @property
    def tempo_total_minutos(self):
        return self.duracao_minutos + self.intervalo_minutos


class ProcedimentoRecurso(models.Model):
    """Quantos recursos de cada tipo o procedimento ocupa."""

    procedimento = models.ForeignKey(Procedimento, on_delete=models.CASCADE, related_name="recursos")
    tipo = models.ForeignKey(TipoRecurso, on_delete=models.PROTECT, verbose_name="tipo de recurso")
    quantidade = models.PositiveSmallIntegerField("quantidade", default=1, validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "recurso necessário"
        verbose_name_plural = "recursos necessários"
        constraints = [
            models.UniqueConstraint(fields=["procedimento", "tipo"], name="procedimento_tipo_recurso_unico"),
        ]

    def __str__(self):
        return f"{self.tipo} ×{self.quantidade}"
