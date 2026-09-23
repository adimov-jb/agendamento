from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("agenda/", views.dia, name="dia"),
    path("agenda/semana/", views.semana, name="semana"),
    path("agenda/novo/", views.novo, name="novo"),
    path("agenda/horarios-livres/", views.horarios_livres, name="horarios_livres"),
    path("agenda/agendamentos/<int:pk>/", views.detalhe, name="detalhe"),
    path("agenda/agendamentos/<int:pk>/remarcar/", views.remarcar, name="remarcar"),
    path("agenda/agendamentos/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("agenda/agendamentos/<int:pk>/presenca/", views.presenca, name="presenca"),
    path("agenda/horarios/", views.horarios, name="horarios"),
    path("agenda/bloqueios/", views.bloqueios, name="bloqueios"),
    path("agenda/bloqueios/<int:pk>/excluir/", views.excluir_bloqueio, name="excluir_bloqueio"),
]
