from django.conf import settings

from agenda.models import Agendamento

from .permissions import PERFIL_GERENTE, PERFIL_PROFISSIONAL, acesso_atual, eh_super_admin, opcoes_de_acesso


def app(request):
    estabelecimento, perfil = acesso_atual(request)
    # Nas páginas do cliente, o estabelecimento vem do endereço (ver publico.views.do_estabelecimento)
    publico = getattr(request, "estabelecimento_publico", None)
    gerente = perfil == PERFIL_GERENTE
    opcoes = opcoes_de_acesso(request)
    exibido = publico or estabelecimento
    return {
        "APP_NAME": exibido.nome if exibido else settings.APP_NAME,
        "estabelecimento_atual": estabelecimento,
        "estabelecimento_publico": publico,
        # O que aparece no topo da página (nome e foto)
        "estabelecimento_exibido": exibido,
        "eh_super_admin": eh_super_admin(request.user),
        "eh_gerente": gerente,
        "eh_profissional": perfil == PERFIL_PROFISSIONAL,
        "perfil_ativo": perfil,
        # Outro perfil no mesmo estabelecimento (troca rápida pelo topo da página)
        "outro_perfil": next((p for e, p in opcoes if e == estabelecimento and p != perfil), None),
        "pode_trocar_estabelecimento": len({e for e, _ in opcoes}) > 1,
        "pendencias": (
            Agendamento.objects.filter(
                estabelecimento=estabelecimento, status=Agendamento.Status.PRECISA_REAGENDAR
            ).count()
            if gerente
            else 0
        ),
    }
