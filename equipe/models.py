from django.conf import settings
from django.db import models, transaction

from catalogo.models import Procedimento


class Profissional(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="profissional")
    nome = models.CharField("nome", max_length=100)
    ativo = models.BooleanField("ativo", default=True)
    procedimentos = models.ManyToManyField(
        Procedimento, blank=True, related_name="profissionais", verbose_name="procedimentos que realiza"
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "profissional"
        verbose_name_plural = "profissionais"

    def __str__(self):
        return self.nome

    def definir_ativo(self, ativo):
        """Inativar o profissional também bloqueia o login dele."""
        with transaction.atomic():
            self.ativo = ativo
            self.save(update_fields=["ativo"])
            self.usuario.is_active = ativo
            self.usuario.save(update_fields=["is_active"])
