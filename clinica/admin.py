from django.contrib import admin

from .models import Estabelecimento, HorarioFuncionamento


class HorarioFuncionamentoInline(admin.TabularInline):
    model = HorarioFuncionamento
    extra = 0


@admin.register(Estabelecimento)
class EstabelecimentoAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "slug"]
    list_filter = ["tipo"]
    search_fields = ["nome", "slug"]
    prepopulated_fields = {"slug": ["nome"]}
    filter_horizontal = ["gerentes"]
    inlines = [HorarioFuncionamentoInline]
