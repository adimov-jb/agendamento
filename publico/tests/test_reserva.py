from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from agenda.models import Agendamento, Cliente
from agenda.tests.conftest import hora
from catalogo.models import Procedimento
from clinica.models import Estabelecimento
from publico.acesso import chave_sessao
from publico.models import TentativaFalha

pytestmark = pytest.mark.django_db

NASCIMENTO = "1990-05-20"
SLUG = "bella"


def dados_reserva(profissional, inicio, **extra):
    dados = {
        "profissional": profissional.pk,
        "data": inicio.date().isoformat(),
        "inicio": inicio.isoformat(),
        "nome": "Fernanda",
        "telefone": "(11) 96666-5555",
        "data_nascimento": NASCIMENTO,
        "consentimento": "on",
    }
    dados.update(extra)
    return dados


def test_inicio_lista_so_procedimentos_agendaveis(client, estabelecimento, ana, limpeza):
    Procedimento.objects.create(estabelecimento=estabelecimento, nome="Peeling sem profissional", duracao_minutos=30, preco=80)
    Procedimento.objects.create(
        estabelecimento=estabelecimento, nome="Massagem inativa", duracao_minutos=30, preco=80, ativo=False
    )
    html = client.get(reverse("publico:inicio", args=[SLUG])).content.decode()
    assert "Limpeza de pele" in html
    assert "Peeling sem profissional" not in html
    assert "Massagem inativa" not in html


def test_procedimento_sem_profissional_nao_abre(client, estabelecimento, clinica_aberta):
    p = Procedimento.objects.create(estabelecimento=estabelecimento, nome="Peeling", duracao_minutos=30, preco=80)
    assert client.get(reverse("publico:reservar", args=[SLUG, p.pk])).status_code == 404


def test_pagina_de_reserva(client, ana, limpeza):
    response = client.get(reverse("publico:reservar", args=[SLUG, limpeza.pk]))
    assert response.status_code == 200
    # Um único profissional já vem escolhido
    assert response.context["profissional_escolhido"] == ana


def test_pagina_de_reserva_ja_escolhe_o_primeiro_dia_livre(client, ana, limpeza):
    response = client.get(reverse("publico:reservar", args=[SLUG, limpeza.pk]))
    dia = response.context["escolhida"]
    assert dia.weekday() == 0  # Ana só atende às segundas
    assert response.context["horarios"]
    assert f'value="{dia.isoformat()}"' in response.content.decode()


def test_calendario_so_oferece_dias_com_horario_livre(client, ana, limpeza, segunda):
    url = reverse("publico:calendario", args=[SLUG, limpeza.pk])
    response = client.get(url, {"profissional": ana.pk, "mes": segunda.isoformat()})
    html = response.content.decode()
    assert f'name="data" value="{segunda.isoformat()}"' in html
    terca = segunda + timedelta(days=1)
    assert f'value="{terca.isoformat()}"' not in html
    # Navegar entre meses não escolhe dia: os horários voltam a pedir um dia
    assert response.context["escolhida"] is None
    assert "Escolha um dia no calendário" in html


def test_calendario_respeita_antecedencia_maxima(client, ana, limpeza):
    Estabelecimento.objects.update(antecedencia_maxima_dias=0)
    hoje = timezone.localdate()
    response = client.get(reverse("publico:calendario", args=[SLUG, limpeza.pk]), {"profissional": ana.pk})
    assert response.context["mes_seguinte"] is None
    assert response.context["mes_anterior"] is None
    assert all(c["dia"] == hoje for semana in response.context["semanas"] for c in semana if c["livre"])


def test_trocar_profissional_escolhe_o_primeiro_dia_livre(client, ana, bia, limpeza):
    response = client.get(reverse("publico:calendario", args=[SLUG, limpeza.pk]), {"profissional": bia.pk})
    assert response.context["escolhida"] is not None
    assert 'id="horarios" hx-swap-oob="true"' in response.content.decode()


def test_horarios_do_cliente_respeitam_antecedencia(client, ana, limpeza, segunda):
    url = reverse("publico:horarios", args=[SLUG, limpeza.pk])
    html = client.get(url, {"profissional": ana.pk, "data": segunda.isoformat()}).content.decode()
    assert ">09:00<" in html

    Estabelecimento.objects.update(antecedencia_maxima_dias=3)
    html = client.get(url, {"profissional": ana.pk, "data": segunda.isoformat()}).content.decode()
    assert "Nenhum horário livre" in html


def test_reserva_completa(client, ana, limpeza, segunda):
    inicio = hora(segunda, "13:00")
    response = client.post(reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados_reserva(ana, inicio))
    assert response.url == reverse("publico:confirmado", args=[SLUG])

    agendamento = Agendamento.objects.get()
    assert agendamento.origem == Agendamento.Origem.CLIENTE
    assert agendamento.inicio == inicio
    cliente = agendamento.cliente
    assert cliente.telefone == "+5511966665555"
    assert cliente.data_nascimento == date(1990, 5, 20)
    assert cliente.consentimento_em is not None

    html = client.get(reverse("publico:confirmado", args=[SLUG])).content.decode()
    assert "Agendamento confirmado!" in html and "13:00" in html
    # Já fica identificado para ver "meus agendamentos"
    assert "Olá, Fernanda" in client.get(reverse("publico:meus", args=[SLUG])).content.decode()


def test_reserva_exige_consentimento(client, ana, limpeza, segunda):
    dados = dados_reserva(ana, hora(segunda, "13:00"))
    del dados["consentimento"]
    response = client.post(reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados)
    assert "É preciso autorizar o uso dos dados" in response.content.decode()
    assert not Agendamento.objects.exists()


def test_reserva_fora_da_antecedencia(client, ana, limpeza, segunda):
    Estabelecimento.objects.update(antecedencia_maxima_dias=3)
    response = client.post(reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados_reserva(ana, hora(segunda, "13:00")))
    assert "não está mais disponível" in response.content.decode()
    assert not Agendamento.objects.exists()


def test_reserva_com_profissional_que_nao_faz_o_procedimento(client, ana, bia, limpeza, segunda):
    bia.procedimentos.remove(limpeza)
    response = client.post(reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados_reserva(bia, hora(segunda, "13:00")))
    assert response.status_code == 200
    assert not Agendamento.objects.exists()


def test_telefone_existente_com_outro_nascimento(client, ana, limpeza, segunda):
    Cliente.objects.create(
        estabelecimento=ana.estabelecimento, nome="Fernanda", telefone="+5511966665555", data_nascimento=date(1985, 1, 1)
    )
    response = client.post(reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados_reserva(ana, hora(segunda, "13:00")))
    assert "já está cadastrado com outra data de nascimento" in response.content.decode()
    assert not Agendamento.objects.exists()
    assert TentativaFalha.objects.filter(chave=f"tel:{ana.estabelecimento_id}:+5511966665555").exists()


def test_telefone_cadastrado_pela_equipe_sem_nascimento(client, ana, limpeza, segunda):
    existente = Cliente.objects.create(estabelecimento=ana.estabelecimento, nome="Fê", telefone="+5511966665555")
    client.post(reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados_reserva(ana, hora(segunda, "13:00")))
    existente.refresh_from_db()
    assert existente.data_nascimento == date(1990, 5, 20)
    assert existente.nome == "Fê"  # nome mantido
    assert Agendamento.objects.get().cliente == existente


def test_nascimento_no_futuro(client, ana, limpeza, segunda):
    amanha = (timezone.localdate() + timedelta(days=1)).isoformat()
    response = client.post(
        reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados_reserva(ana, hora(segunda, "13:00"), data_nascimento=amanha)
    )
    assert "Informe uma data de nascimento válida." in response.content.decode()


def test_confirmado_sem_sessao_vai_para_meus(client, estabelecimento):
    assert client.get(reverse("publico:confirmado", args=[SLUG])).url == reverse("publico:meus", args=[SLUG])


def test_sessao_expira(client, ana, limpeza, segunda):
    client.post(reverse("publico:reservar", args=[SLUG, limpeza.pk]), dados_reserva(ana, hora(segunda, "13:00")))
    sessao = client.session
    sessao[chave_sessao(ana.estabelecimento_id)]["ate"] = (timezone.now() - timedelta(minutes=1)).isoformat()
    sessao.save()
    assert "Informe o telefone" in client.get(reverse("publico:meus", args=[SLUG])).content.decode()
