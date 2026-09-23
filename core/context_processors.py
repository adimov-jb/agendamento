from agenda.models import Agendamento
from clinica.models import Configuracao

from .permissions import PERFIL_GERENTE, PERFIL_PROFISSIONAL, perfil_ativo, perfis


def app(request):
    perfil = perfil_ativo(request)
    gerente = perfil == PERFIL_GERENTE
    return {
        "APP_NAME": Configuracao.atual().nome_clinica,
        "eh_gerente": gerente,
        "eh_profissional": perfil == PERFIL_PROFISSIONAL,
        "perfil_ativo": perfil,
        "pode_trocar_perfil": len(perfis(request.user)) > 1,
        "pendencias": (
            Agendamento.objects.filter(status=Agendamento.Status.PRECISA_REAGENDAR).count() if gerente else 0
        ),
    }
