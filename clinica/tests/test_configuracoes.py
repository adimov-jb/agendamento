from datetime import time

import pytest
from django.urls import reverse

from clinica.models import Configuracao, DiaSemana, HorarioClinica

pytestmark = pytest.mark.django_db

URL = reverse("clinica:configuracoes")


def dados_validos(**extra):
    dados = {
        "nome_clinica": "Clínica Bella",
        "grade_minutos": "15",
        "antecedencia_minima_horas": "2",
        "antecedencia_maxima_dias": "60",
    }
    for dia in DiaSemana.values:
        dados[f"dia{dia}-inicio"] = "09:00"
        dados[f"dia{dia}-fim"] = "18:00"
    # segunda a sexta abertas; sábado e domingo fechados
    for dia in range(5):
        dados[f"dia{dia}-aberto"] = "on"
    dados.update(extra)
    return dados


def test_configuracao_e_unica():
    Configuracao.atual()
    Configuracao(nome_clinica="Outra").save()
    assert Configuracao.objects.count() == 1
    assert Configuracao.atual().nome_clinica == "Outra"


def test_pagina_abre(cliente_gerente):
    assert cliente_gerente.get(URL).status_code == 200


def test_salva_regras_e_horarios(cliente_gerente):
    response = cliente_gerente.post(URL, dados_validos())
    assert response.status_code == 302

    config = Configuracao.atual()
    assert config.nome_clinica == "Clínica Bella"
    assert config.grade_minutos == 15
    assert list(HorarioClinica.objects.values_list("dia_semana", flat=True)) == [0, 1, 2, 3, 4]
    assert HorarioClinica.objects.get(dia_semana=0).fim == time(18)


def test_desmarcar_dia_fecha_a_clinica(cliente_gerente):
    cliente_gerente.post(URL, dados_validos())
    dados = dados_validos()
    del dados["dia0-aberto"]
    cliente_gerente.post(URL, dados)
    assert not HorarioClinica.objects.filter(dia_semana=0).exists()


def test_fechamento_antes_da_abertura_e_rejeitado(cliente_gerente):
    response = cliente_gerente.post(URL, dados_validos(**{"dia2-inicio": "18:00", "dia2-fim": "09:00"}))
    assert response.status_code == 200
    assert "O fechamento deve ser depois da abertura." in response.content.decode()
    assert not HorarioClinica.objects.exists()
    assert Configuracao.atual().nome_clinica == "Agendamento"


def test_nome_da_clinica_aparece_no_cabecalho(cliente_gerente):
    cliente_gerente.post(URL, dados_validos())
    assert "Clínica Bella" in cliente_gerente.get(reverse("core:home")).content.decode()
