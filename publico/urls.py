from django.urls import include, path

from . import views

app_name = "publico"

# Páginas do cliente, no endereço do estabelecimento: /<slug>/...
do_estabelecimento = [
    path("", views.inicio, name="inicio"),
    path("foto/", views.foto, name="foto"),
    path("agendar/<int:pk>/", views.reservar, name="reservar"),
    path("agendar/<int:pk>/horarios/", views.horarios, name="horarios"),
    path("agendar/<int:pk>/calendario/", views.calendario, name="calendario"),
    path("agendar/confirmado/", views.confirmado, name="confirmado"),
    path("meus-agendamentos/", views.meus, name="meus"),
    path("meus-agendamentos/sair/", views.sair, name="sair"),
    path("meus-agendamentos/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("meus-agendamentos/<int:pk>/remarcar/", views.remarcar, name="remarcar"),
    path("meus-agendamentos/<int:pk>/horarios/", views.horarios_remarcacao, name="horarios_remarcacao"),
]

urlpatterns = [
    # Links de antes dos vários estabelecimentos
    path("agendar/<int:pk>/", views.legado_reservar),
    path("meus-agendamentos/", views.legado_meus),
    path("<slug:estabelecimento>/", include(do_estabelecimento)),
]
