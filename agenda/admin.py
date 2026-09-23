from django.contrib import admin

from .models import Agendamento, AgendamentoRecurso, Bloqueio, Cliente, HorarioTrabalho


class AgendamentoRecursoInline(admin.TabularInline):
    model = AgendamentoRecurso
    extra = 0


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ["inicio", "cliente", "profissional", "procedimento", "status"]
    list_filter = ["status", "profissional"]
    date_hierarchy = "inicio"
    inlines = [AgendamentoRecursoInline]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "data_nascimento"]
    search_fields = ["nome", "telefone"]


@admin.register(Bloqueio)
class BloqueioAdmin(admin.ModelAdmin):
    list_display = ["inicio", "fim", "profissional", "motivo"]


admin.site.register(HorarioTrabalho)
