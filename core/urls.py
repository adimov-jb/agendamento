from django.urls import path

from publico.views import inicio

from . import views

app_name = "core"

urlpatterns = [
    path("", inicio, name="home"),
    path("health/", views.health, name="health"),
    path("painel/", views.painel, name="painel"),
]
