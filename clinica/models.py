from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils.text import slugify

# Primeiros trechos de URL já usados pelo sistema: não podem ser o endereço de um estabelecimento.
SLUGS_RESERVADOS = {
    "admin", "agenda", "agendar", "acesso", "convite", "entrar", "estabelecimentos", "gerente",
    "health", "meus-agendamentos", "painel", "sair", "senha", "static",
}


def validar_slug(valor):
    if valor in SLUGS_RESERVADOS:
        raise ValidationError("Este endereço é reservado pelo sistema. Escolha outro.")


def slug_disponivel(nome, excluir_pk=None):
    """Slug livre a partir do nome (ex.: 'Barbearia do Zé' -> 'barbearia-do-ze', 'barbearia-do-ze-2'...)."""
    base = slugify(nome)[:50] or "estabelecimento"
    if base in SLUGS_RESERVADOS:
        base = f"{base}-1"
    existentes = Estabelecimento.objects.exclude(pk=excluir_pk)
    slug, n = base, 2
    while existentes.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


class Estabelecimento(models.Model):
    """Clínica, barbearia ou salão. Tudo no sistema (equipe, cadastros e agenda) pertence a um estabelecimento."""

    class Tipo(models.TextChoices):
        CLINICA = "clinica", "Clínica"
        BARBEARIA = "barbearia", "Barbearia"
        SALAO = "salao", "Salão de Beleza"

    GRADES = [(5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min")]

    nome = models.CharField("nome", max_length=100)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    slug = models.SlugField(
        "endereço da página de agendamento",
        max_length=60,
        unique=True,
        validators=[validar_slug],
        help_text="Aparece no link que os clientes usam para agendar. Use letras minúsculas, números e hífens.",
    )
    gerentes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="estabelecimentos_gerenciados", verbose_name="gerentes"
    )
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
    # Muda a cada foto nova e entra no endereço da imagem, para o navegador não usar a antiga do cache.
    # Vazio = sem foto.
    foto_atualizada_em = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["nome"]
        verbose_name = "estabelecimento"
        verbose_name_plural = "estabelecimentos"

    def __str__(self):
        return self.nome

    @property
    def url_foto(self):
        if not self.foto_atualizada_em:
            return ""
        versao = int(self.foto_atualizada_em.timestamp() * 1_000_000)  # microssegundos: duas trocas seguidas diferem
        return f"{reverse('publico:foto', args=[self.slug])}?v={versao}"


class FotoEstabelecimento(models.Model):
    """Foto do estabelecimento, já reduzida (ver clinica.fotos).

    Fica no banco, e não em disco, porque o disco do servidor de produção (Render) é apagado a cada deploy.
    Separada do Estabelecimento para não carregar a imagem em toda consulta.
    """

    estabelecimento = models.OneToOneField(Estabelecimento, on_delete=models.CASCADE, related_name="foto")
    conteudo = models.BinaryField()
    tipo = models.CharField("tipo de arquivo", max_length=30)

    class Meta:
        verbose_name = "foto do estabelecimento"
        verbose_name_plural = "fotos dos estabelecimentos"

    def __str__(self):
        return f"Foto de {self.estabelecimento}"


class DiaSemana(models.IntegerChoices):
    # Mesma numeração de datetime.weekday()
    SEGUNDA = 0, "Segunda-feira"
    TERCA = 1, "Terça-feira"
    QUARTA = 2, "Quarta-feira"
    QUINTA = 3, "Quinta-feira"
    SEXTA = 4, "Sexta-feira"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class HorarioFuncionamento(models.Model):
    """Horário de funcionamento do estabelecimento. Dia sem registro = fechado."""

    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE, related_name="horarios")
    dia_semana = models.PositiveSmallIntegerField("dia da semana", choices=DiaSemana.choices)
    inicio = models.TimeField("abre às")
    fim = models.TimeField("fecha às")

    class Meta:
        ordering = ["dia_semana"]
        verbose_name = "horário de funcionamento"
        verbose_name_plural = "horários de funcionamento"
        constraints = [
            models.CheckConstraint(condition=Q(fim__gt=F("inicio")), name="horario_clinica_fim_apos_inicio"),
            models.UniqueConstraint(fields=["estabelecimento", "dia_semana"], name="horario_funcionamento_dia_unico"),
        ]

    def __str__(self):
        return f"{self.get_dia_semana_display()}: {self.inicio:%H:%M}–{self.fim:%H:%M}"
