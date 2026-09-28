from django.contrib import admin

from .models import Agendamento, AgendamentoRecurso, Bloqueio, Cliente, HorarioTrabalho


class AgendamentoRecursoInline(admin.TabularInline):
    model = AgendamentoRecurso
    extra = 0


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ["inicio", "estabelecimento", "cliente", "profissional", "procedimento", "status"]
    list_filter = ["estabelecimento", "status"]
    date_hierarchy = "inicio"
    inlines = [AgendamentoRecursoInline]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "data_nascimento", "estabelecimento"]
    list_filter = ["estabelecimento"]
    search_fields = ["nome", "telefone"]


@admin.register(Bloqueio)
class BloqueioAdmin(admin.ModelAdmin):
    list_display = ["inicio", "fim", "estabelecimento", "profissional", "motivo"]
    list_filter = ["estabelecimento"]


admin.site.register(HorarioTrabalho)
