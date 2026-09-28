from datetime import time, timedelta

import pytest
from django.utils import timezone

from agenda.models import Agendamento, HorarioTrabalho
from agenda.servicos import agendar, momento, obter_cliente
from catalogo.models import Procedimento, Recurso, TipoRecurso
from clinica.models import HorarioFuncionamento
from equipe.models import Profissional


def hora(data, texto):
    h, m = map(int, texto.split(":"))
    return momento(data, time(h, m))


@pytest.fixture
def segunda():
    """Uma segunda-feira pelo menos 7 dias à frente (longe do 'agora')."""
    hoje = timezone.localdate()
    return hoje + timedelta(days=(7 - hoje.weekday()) % 7 + 7)


@pytest.fixture
def sala(estabelecimento):
    tipo = TipoRecurso.objects.create(estabelecimento=estabelecimento, nome="Sala")
    Recurso.objects.create(tipo=tipo, nome="Sala 1")
    return tipo


@pytest.fixture
def limpeza(estabelecimento, sala):
    """60 min + 15 de intervalo, ocupa 1 sala (a clínica só tem uma)."""
    procedimento = Procedimento.objects.create(
        estabelecimento=estabelecimento, nome="Limpeza de pele", duracao_minutos=60, intervalo_minutos=15, preco=150
    )
    procedimento.recursos.create(tipo=sala, quantidade=1)
    return procedimento


@pytest.fixture
def clinica_aberta(estabelecimento):
    estabelecimento.grade_minutos = 15
    estabelecimento.antecedencia_minima_horas = 2
    estabelecimento.antecedencia_maxima_dias = 60
    estabelecimento.save()
    for dia in range(5):
        HorarioFuncionamento.objects.create(estabelecimento=estabelecimento, dia_semana=dia, inicio=time(8), fim=time(20))


def dar_expediente(profissional, *periodos, dia=0):
    for inicio, fim in periodos:
        HorarioTrabalho.objects.create(profissional=profissional, dia_semana=dia, inicio=inicio, fim=fim)


@pytest.fixture
def ana(profissional, limpeza, clinica_aberta):
    """Ana atende às segundas, 09–12 e 13–18."""
    profissional.procedimentos.add(limpeza)
    dar_expediente(profissional, (time(9), time(12)), (time(13), time(18)))
    return profissional


@pytest.fixture
def bia(django_user_model, estabelecimento, limpeza, clinica_aberta):
    usuario = django_user_model.objects.create_user("bia@clinica.com", "bia@clinica.com", "x")
    bia = Profissional.objects.create(usuario=usuario, estabelecimento=estabelecimento, nome="Bia")
    bia.procedimentos.add(limpeza)
    dar_expediente(bia, (time(9), time(18)))
    return bia


@pytest.fixture
def cliente(estabelecimento):
    return obter_cliente(estabelecimento, "Carla", "+5511999998888")


@pytest.fixture
def marcar(cliente, limpeza):
    def _marcar(profissional, inicio):
        return agendar(
            cliente=cliente,
            profissional=profissional,
            procedimento=limpeza,
            inicio=inicio,
            origem=Agendamento.Origem.PROFISSIONAL,
            respeitar_antecedencia=False,
        )

    return _marcar
