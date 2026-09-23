from django.urls import path

from . import views

app_name = "clinica"

urlpatterns = [
    path("gerente/clinica/", views.configuracoes, name="configuracoes"),
]
