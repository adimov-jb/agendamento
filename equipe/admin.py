from django.contrib import admin

from .models import Profissional


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["nome", "usuario", "ativo"]
    list_filter = ["ativo"]
    filter_horizontal = ["procedimentos"]
