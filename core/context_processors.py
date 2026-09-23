from agenda.models import Agendamento
from clinica.models import Configuracao

from .permissions import eh_gerente


def app(request):
    gerente = eh_gerente(request.user)
    return {
        "APP_NAME": Configuracao.atual().nome_clinica,
        "eh_gerente": gerente,
        "eh_profissional": request.user.is_authenticated and hasattr(request.user, "profissional"),
        "pendencias": (
            Agendamento.objects.filter(status=Agendamento.Status.PRECISA_REAGENDAR).count() if gerente else 0
        ),
    }
