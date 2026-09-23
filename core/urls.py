from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("painel/", views.painel, name="painel"),
    path("gerente/", views.gerente_inicio, name="gerente"),
]
