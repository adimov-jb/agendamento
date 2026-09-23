from django.contrib import admin

from .models import TentativaFalha


@admin.register(TentativaFalha)
class TentativaFalhaAdmin(admin.ModelAdmin):
    list_display = ["chave", "criado_em"]
    search_fields = ["chave"]
