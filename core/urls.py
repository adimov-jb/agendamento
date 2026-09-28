from django.urls import path

from publico.views import estabelecimentos

from . import views

app_name = "core"

urlpatterns = [
    path("", estabelecimentos, name="home"),
    path("health/", views.health, name="health"),
    path("painel/", views.painel, name="painel"),
    path("acesso/", views.acesso, name="acesso"),
]
