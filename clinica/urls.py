from django.urls import path

from . import views

app_name = "clinica"

urlpatterns = [
    path("estabelecimentos/novo/", views.novo, name="novo"),
    path("gerente/estabelecimento/", views.configuracoes, name="configuracoes"),
]
