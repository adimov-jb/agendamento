from django.urls import path

from . import views

app_name = "publico"

urlpatterns = [
    path("agendar/<int:pk>/", views.reservar, name="reservar"),
    path("agendar/<int:pk>/horarios/", views.horarios, name="horarios"),
    path("agendar/confirmado/", views.confirmado, name="confirmado"),
    path("meus-agendamentos/", views.meus, name="meus"),
    path("meus-agendamentos/sair/", views.sair, name="sair"),
    path("meus-agendamentos/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("meus-agendamentos/<int:pk>/remarcar/", views.remarcar, name="remarcar"),
    path("meus-agendamentos/<int:pk>/horarios/", views.horarios_remarcacao, name="horarios_remarcacao"),
]
