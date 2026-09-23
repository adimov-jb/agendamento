from django.contrib import admin

from .models import Procedimento, ProcedimentoRecurso, Recurso, TipoRecurso


class ProcedimentoRecursoInline(admin.TabularInline):
    model = ProcedimentoRecurso
    extra = 0


@admin.register(Procedimento)
class ProcedimentoAdmin(admin.ModelAdmin):
    list_display = ["nome", "duracao_minutos", "intervalo_minutos", "preco", "ativo"]
    list_filter = ["ativo"]
    inlines = [ProcedimentoRecursoInline]


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "ativo"]
    list_filter = ["tipo", "ativo"]


admin.site.register(TipoRecurso)
