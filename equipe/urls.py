from django.urls import path

from . import views

app_name = "equipe"

urlpatterns = [
    path("gerente/profissionais/", views.ProfissionalLista.as_view(), name="profissionais"),
    path("gerente/profissionais/novo/", views.profissional_novo, name="profissional_novo"),
    path("gerente/profissionais/<int:pk>/", views.ProfissionalEditar.as_view(), name="profissional_editar"),
    path("gerente/profissionais/<int:pk>/alternar-ativo/", views.profissional_alternar, name="profissional_alternar"),
    path("gerente/convites/<int:pk>/reenviar/", views.convite_reenviar, name="convite_reenviar"),
    path("gerente/convites/<int:pk>/cancelar/", views.convite_cancelar, name="convite_cancelar"),
    path("convite/<str:token>/", views.convite, name="convite"),
]
