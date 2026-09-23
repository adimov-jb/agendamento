from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("gerente/procedimentos/", views.ProcedimentoLista.as_view(), name="procedimentos"),
    path("gerente/procedimentos/novo/", views.ProcedimentoNovo.as_view(), name="procedimento_novo"),
    path("gerente/procedimentos/<int:pk>/", views.ProcedimentoEditar.as_view(), name="procedimento_editar"),
    path("gerente/procedimentos/<int:pk>/alternar-ativo/", views.procedimento_alternar, name="procedimento_alternar"),
    path("gerente/recursos/", views.RecursoLista.as_view(), name="recursos"),
    path("gerente/recursos/novo/", views.RecursoNovo.as_view(), name="recurso_novo"),
    path("gerente/recursos/<int:pk>/", views.RecursoEditar.as_view(), name="recurso_editar"),
    path("gerente/recursos/<int:pk>/alternar-ativo/", views.recurso_alternar, name="recurso_alternar"),
    path("gerente/recursos/tipos/novo/", views.TipoRecursoNovo.as_view(), name="tipo_novo"),
    path("gerente/recursos/tipos/<int:pk>/", views.TipoRecursoEditar.as_view(), name="tipo_editar"),
]
