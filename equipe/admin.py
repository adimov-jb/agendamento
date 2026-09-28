from django.contrib import admin

from .models import Convite, Profissional


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["nome", "usuario", "estabelecimento", "ativo"]
    list_filter = ["estabelecimento", "ativo"]
    filter_horizontal = ["procedimentos"]


@admin.register(Convite)
class ConviteAdmin(admin.ModelAdmin):
    list_display = ["email", "estabelecimento", "gerente", "enviado_em", "aceito_em"]
    list_filter = ["estabelecimento"]
    search_fields = ["email", "nome"]
