import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from catalogo.models import Procedimento
from clinica.models import Estabelecimento


class Profissional(models.Model):
    """Colaborador que atende em um estabelecimento. O mesmo usuário pode atender em vários."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="profissionais")
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.PROTECT, related_name="profissionais")
    nome = models.CharField("nome", max_length=100)
    ativo = models.BooleanField("ativo", default=True)
    procedimentos = models.ManyToManyField(
        Procedimento, blank=True, related_name="profissionais", verbose_name="procedimentos que realiza"
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "profissional"
        verbose_name_plural = "profissionais"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "estabelecimento"], name="profissional_unico_por_estabelecimento"),
        ]

    def __str__(self):
        return self.nome


def gerar_token():
    return secrets.token_urlsafe(32)


class Convite(models.Model):
    """Convite por e-mail para alguém se tornar profissional (e, opcionalmente, gerente) de um estabelecimento."""

    VALIDADE = timedelta(days=7)

    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE, related_name="convites")
    email = models.EmailField("e-mail")
    nome = models.CharField("nome", max_length=100)
    gerente = models.BooleanField("também será gerente", default=False)
    procedimentos = models.ManyToManyField(Procedimento, blank=True, verbose_name="procedimentos que realiza")
    token = models.CharField(max_length=64, unique=True, default=gerar_token, editable=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    enviado_em = models.DateTimeField("enviado em", default=timezone.now)
    aceito_em = models.DateTimeField("aceito em", null=True, blank=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "convite"
        verbose_name_plural = "convites"
        constraints = [
            models.UniqueConstraint(
                fields=["estabelecimento", "email"],
                condition=Q(aceito_em__isnull=True),
                name="convite_pendente_unico",
            ),
        ]

    def __str__(self):
        return f"{self.email} · {self.estabelecimento}"

    @property
    def expira_em(self):
        return self.enviado_em + self.VALIDADE

    @property
    def valido(self):
        return self.aceito_em is None and timezone.now() < self.expira_em

    def renovar(self):
        """Novo link e novo prazo (o link anterior deixa de funcionar)."""
        self.token = gerar_token()
        self.enviado_em = timezone.now()
        self.save(update_fields=["token", "enviado_em"])

    def aceitar(self, usuario):
        """Vincula o usuário ao estabelecimento como profissional (e gerente, se for o caso)."""
        with transaction.atomic():
            profissional, _ = Profissional.objects.get_or_create(
                usuario=usuario, estabelecimento=self.estabelecimento, defaults={"nome": self.nome}
            )
            if not profissional.ativo:
                profissional.ativo = True
                profissional.save(update_fields=["ativo"])
            profissional.procedimentos.add(*self.procedimentos.all())
            if self.gerente:
                self.estabelecimento.gerentes.add(usuario)
            self.aceito_em = timezone.now()
            self.save(update_fields=["aceito_em"])
        return profissional
