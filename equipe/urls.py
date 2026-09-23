from django.urls import path

from . import views

app_name = "equipe"

urlpatterns = [
    path("gerente/profissionais/", views.ProfissionalLista.as_view(), name="profissionais"),
    path("gerente/profissionais/novo/", views.ProfissionalNovo.as_view(), name="profissional_novo"),
    path("gerente/profissionais/<int:pk>/", views.ProfissionalEditar.as_view(), name="profissional_editar"),
    path("gerente/profissionais/<int:pk>/alternar-ativo/", views.profissional_alternar, name="profissional_alternar"),
]
