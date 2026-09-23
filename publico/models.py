from django.db import models


class TentativaFalha(models.Model):
    """Tentativa de identificação que falhou, para limitar quem tenta adivinhar datas de nascimento.

    Fica no banco (e não em cache de memória) para valer entre processos do servidor.
    """

    chave = models.CharField(max_length=64, db_index=True, help_text="'ip:<endereço>' ou 'tel:<telefone>'.")
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "tentativa falha"
        verbose_name_plural = "tentativas falhas"

    def __str__(self):
        return self.chave
