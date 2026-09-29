from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Navegadores pedem /favicon.ico direto, mesmo em páginas sem o <link rel="icon">
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico", permanent=True)),
    path("entrar/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    # Cada colaborador cuida da própria senha (o login vale em todos os estabelecimentos dele)
    path("senha/recuperar/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("senha/recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "senha/redefinir/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("senha/redefinida/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("", include("core.urls")),
    path("", include("clinica.urls")),
    path("", include("catalogo.urls")),
    path("", include("equipe.urls")),
    path("", include("agenda.urls")),
    # Por último: /<slug do estabelecimento>/ aceita qualquer primeiro trecho de URL
    path("", include("publico.urls")),
]
