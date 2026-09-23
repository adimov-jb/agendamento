from clinica.models import Configuracao

from .permissions import eh_gerente


def app(request):
    return {
        "APP_NAME": Configuracao.atual().nome_clinica,
        "eh_gerente": eh_gerente(request.user),
        "eh_profissional": request.user.is_authenticated and hasattr(request.user, "profissional"),
    }
