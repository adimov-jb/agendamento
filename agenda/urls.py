from django.urls import path

from . import gerente, views

app_name = "agenda"

urlpatterns = [
    # Profissional
    path("agenda/", views.dia, name="dia"),
    path("agenda/semana/", views.semana, name="semana"),
    path("agenda/novo/", views.novo, name="novo"),
    path("agenda/horarios/", views.horarios, name="horarios"),
    path("agenda/bloqueios/", views.bloqueios, name="bloqueios"),
    path("agenda/relatorio/", views.relatorio, name="relatorio"),
    path("agenda/bloqueios/<int:pk>/excluir/", views.excluir_bloqueio, name="excluir_bloqueio"),
    # Profissional ou gerente
    path("agenda/horarios-livres/", views.horarios_livres, name="horarios_livres"),
    path("agenda/agendamentos/<int:pk>/", views.detalhe, name="detalhe"),
    path("agenda/agendamentos/<int:pk>/remarcar/", views.remarcar, name="remarcar"),
    path("agenda/agendamentos/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("agenda/agendamentos/<int:pk>/presenca/", views.presenca, name="presenca"),
    # Gerente
    path("gerente/", gerente.dia, name="gerente_dia"),
    path("gerente/agenda/semana/", gerente.semana, name="gerente_semana"),
    path("gerente/agenda/novo/", gerente.novo, name="gerente_novo"),
    path("gerente/pendencias/", gerente.pendencias, name="gerente_pendencias"),
    path("gerente/relatorios/", gerente.relatorios, name="gerente_relatorios"),
    path("gerente/fechamentos/", gerente.bloqueios, name="gerente_bloqueios"),
    path("gerente/fechamentos/<int:pk>/excluir/", gerente.excluir_bloqueio, name="gerente_excluir_bloqueio"),
]
