"""Regras de disponibilidade e operações sobre agendamentos (PROJETO.md, seção 4)."""

from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from catalogo.models import Recurso
from clinica.models import Configuracao, HorarioClinica
from equipe.models import Profissional

from .models import Agendamento, AgendamentoRecurso, Bloqueio, Cliente

Status = Agendamento.Status

MSG_OCUPADO = "Este horário não está mais disponível. Escolha outro."


class AgendamentoInvalido(Exception):
    pass


def momento(data, hora):
    return timezone.make_aware(datetime.combine(data, hora))


def _sobrepoe(inicio_a, fim_a, inicio_b, fim_b):
    return inicio_a < fim_b and inicio_b < fim_a


def _alinhar(instante, grade_minutos):
    """Avança até o próximo múltiplo da grade (contado a partir da meia-noite)."""
    local = timezone.localtime(instante)
    resto = (local.hour * 60 + local.minute) % grade_minutos
    return instante + timedelta(minutes=(grade_minutos - resto) % grade_minutos)


def expediente(profissional, data):
    """Períodos em que o profissional atende na data: horário de trabalho ∩ horário da clínica."""
    clinica = HorarioClinica.objects.filter(dia_semana=data.weekday()).first()
    if clinica is None:
        return []
    periodos = []
    for horario in profissional.horarios.filter(dia_semana=data.weekday()):
        inicio, fim = max(horario.inicio, clinica.inicio), min(horario.fim, clinica.fim)
        if inicio < fim:
            periodos.append((momento(data, inicio), momento(data, fim)))
    return periodos


def dentro_do_expediente(profissional, inicio, fim):
    data = timezone.localdate(inicio)
    return any(a <= inicio and fim <= b for a, b in expediente(profissional, data))


def bloqueios_de(profissional):
    """Bloqueios do profissional mais os bloqueios gerais da clínica."""
    return Bloqueio.objects.filter(Q(profissional=profissional) | Q(profissional__isnull=True))


def horarios_disponiveis(profissional, procedimento, data, *, respeitar_antecedencia=True, ignorar=None, agora=None):
    """Lista os inícios livres na data, na grade configurada.

    `ignorar` é o agendamento sendo remarcado: não conta como ocupado e mantém sua duração original.
    `respeitar_antecedencia` aplica a antecedência mínima/máxima (só para agendamentos do cliente).
    """
    agora = agora or timezone.now()
    config = Configuracao.atual()

    limite = agora
    if respeitar_antecedencia:
        limite = agora + timedelta(hours=config.antecedencia_minima_horas)
        if data > timezone.localdate(agora) + timedelta(days=config.antecedencia_maxima_dias):
            return []

    periodos = expediente(profissional, data)
    if not periodos:
        return []

    inicio_dia = momento(data, time.min)
    no_dia = Q(inicio__lt=inicio_dia + timedelta(days=1), fim__gt=inicio_dia)

    agendamentos = profissional.agendamentos.filter(no_dia, status__in=Agendamento.OCUPAM_AGENDA)
    if ignorar:
        agendamentos = agendamentos.exclude(pk=ignorar.pk)
    ocupados = list(agendamentos.values_list("inicio", "fim"))
    ocupados += list(bloqueios_de(profissional).filter(no_dia).values_list("inicio", "fim"))

    necessidades = list(procedimento.recursos.values_list("tipo_id", "quantidade"))
    unidades, usos = {}, []
    if necessidades:
        tipos = [tipo for tipo, _ in necessidades]
        for recurso_id, tipo_id in Recurso.objects.filter(tipo_id__in=tipos, ativo=True).values_list("id", "tipo_id"):
            unidades.setdefault(tipo_id, set()).add(recurso_id)
        alocacoes = AgendamentoRecurso.objects.filter(no_dia, recurso__tipo_id__in=tipos)
        if ignorar:
            alocacoes = alocacoes.exclude(agendamento=ignorar)
        usos = list(alocacoes.values_list("recurso_id", "inicio", "fim"))

    def recursos_livres(inicio, fim):
        em_uso = {recurso for recurso, a, b in usos if _sobrepoe(inicio, fim, a, b)}
        return all(len(unidades.get(tipo, set()) - em_uso) >= qtd for tipo, qtd in necessidades)

    if ignorar:
        total = timedelta(minutes=ignorar.duracao_minutos + ignorar.intervalo_minutos)
    else:
        total = timedelta(minutes=procedimento.tempo_total_minutos)
    passo = timedelta(minutes=config.grade_minutos)

    livres = []
    for inicio_periodo, fim_periodo in periodos:
        inicio = _alinhar(inicio_periodo, config.grade_minutos)
        while inicio + total <= fim_periodo:
            fim = inicio + total
            if (
                inicio >= limite
                and not any(_sobrepoe(inicio, fim, a, b) for a, b in ocupados)
                and recursos_livres(inicio, fim)
            ):
                livres.append(inicio)
            inicio += passo
    return livres


def obter_cliente(nome, telefone, data_nascimento=None):
    """O telefone identifica o cliente. Completa a data de nascimento se ainda não houver."""
    cliente, criado = Cliente.objects.get_or_create(
        telefone=telefone, defaults={"nome": nome, "data_nascimento": data_nascimento}
    )
    if not criado and data_nascimento and not cliente.data_nascimento:
        cliente.data_nascimento = data_nascimento
        cliente.save(update_fields=["data_nascimento"])
    return cliente


def _travar(profissional):
    """Serializa alterações na agenda do mesmo profissional."""
    Profissional.objects.select_for_update().filter(pk=profissional.pk).first()


def _verificar_horario(profissional, procedimento, inicio, respeitar_antecedencia, ignorar=None):
    livres = horarios_disponiveis(
        profissional,
        procedimento,
        timezone.localdate(inicio),
        respeitar_antecedencia=respeitar_antecedencia,
        ignorar=ignorar,
    )
    if inicio not in livres:
        raise AgendamentoInvalido(MSG_OCUPADO)


def _alocar_recursos(agendamento):
    for tipo_id, quantidade in agendamento.procedimento.recursos.values_list("tipo_id", "quantidade"):
        em_uso = AgendamentoRecurso.objects.filter(inicio__lt=agendamento.fim, fim__gt=agendamento.inicio)
        livres = list(
            Recurso.objects.filter(tipo_id=tipo_id, ativo=True)
            .exclude(pk__in=em_uso.values("recurso_id"))
            .order_by("nome")[:quantidade]
        )
        if len(livres) < quantidade:
            raise AgendamentoInvalido(MSG_OCUPADO)
        AgendamentoRecurso.objects.bulk_create(
            AgendamentoRecurso(agendamento=agendamento, recurso=r, inicio=agendamento.inicio, fim=agendamento.fim)
            for r in livres
        )


def agendar(*, cliente, profissional, procedimento, inicio, origem, respeitar_antecedencia=True):
    if not profissional.ativo or not profissional.procedimentos.filter(pk=procedimento.pk, ativo=True).exists():
        raise AgendamentoInvalido("Este profissional não realiza este procedimento.")
    try:
        with transaction.atomic():
            _travar(profissional)
            _verificar_horario(profissional, procedimento, inicio, respeitar_antecedencia)
            agendamento = Agendamento.objects.create(
                cliente=cliente,
                profissional=profissional,
                procedimento=procedimento,
                inicio=inicio,
                fim=inicio + timedelta(minutes=procedimento.tempo_total_minutos),
                duracao_minutos=procedimento.duracao_minutos,
                intervalo_minutos=procedimento.intervalo_minutos,
                preco=procedimento.preco,
                origem=origem,
            )
            _alocar_recursos(agendamento)
    except IntegrityError:
        # Outra requisição ocupou o horário ou o recurso ao mesmo tempo
        raise AgendamentoInvalido(MSG_OCUPADO)
    return agendamento


def reagendar(agendamento, inicio, *, respeitar_antecedencia=False):
    if not agendamento.em_aberto:
        raise AgendamentoInvalido("Só é possível remarcar agendamentos em aberto.")
    try:
        with transaction.atomic():
            _travar(agendamento.profissional)
            _verificar_horario(
                agendamento.profissional, agendamento.procedimento, inicio, respeitar_antecedencia, ignorar=agendamento
            )
            agendamento.alocacoes.all().delete()
            agendamento.inicio = inicio
            agendamento.fim = inicio + timedelta(minutes=agendamento.duracao_minutos + agendamento.intervalo_minutos)
            agendamento.status = Status.AGENDADO
            agendamento.save(update_fields=["inicio", "fim", "status"])
            _alocar_recursos(agendamento)
    except IntegrityError:
        raise AgendamentoInvalido(MSG_OCUPADO)
    return agendamento


def cancelar(agendamento, por):
    if not agendamento.em_aberto:
        raise AgendamentoInvalido("Só é possível cancelar agendamentos em aberto.")
    with transaction.atomic():
        agendamento.alocacoes.all().delete()
        agendamento.status = Status.CANCELADO
        agendamento.cancelado_em = timezone.now()
        agendamento.cancelado_por = por
        agendamento.save(update_fields=["status", "cancelado_em", "cancelado_por"])


def registrar_presenca(agendamento, compareceu, agora=None):
    if agendamento.status not in Agendamento.OCUPAM_AGENDA:
        raise AgendamentoInvalido("Este agendamento não está ativo.")
    if agendamento.inicio > (agora or timezone.now()):
        raise AgendamentoInvalido("A presença só pode ser registrada depois do horário marcado.")
    agendamento.status = Status.ATENDIDO if compareceu else Status.FALTOU
    agendamento.save(update_fields=["status"])


def _sinalizar_reagendamento(agendamentos):
    """Marca como 'precisa reagendar' e libera os recursos. Retorna quantos foram afetados."""
    ids = list(agendamentos.values_list("pk", flat=True))
    if ids:
        AgendamentoRecurso.objects.filter(agendamento_id__in=ids).delete()
        Agendamento.objects.filter(pk__in=ids).update(status=Status.PRECISA_REAGENDAR)
    return len(ids)


def aplicar_bloqueio(bloqueio):
    # Só o que ainda não terminou: agendamentos passados não são remarcados
    afetados = Agendamento.objects.filter(
        status=Status.AGENDADO, inicio__lt=bloqueio.fim, fim__gt=max(bloqueio.inicio, timezone.now())
    )
    if not bloqueio.geral:
        afetados = afetados.filter(profissional_id=bloqueio.profissional_id)
    return _sinalizar_reagendamento(afetados)


def sinalizar_fora_do_expediente(profissional):
    """Após mudar horários, marca agendamentos futuros que ficaram fora do expediente."""
    futuros = profissional.agendamentos.filter(status=Status.AGENDADO, inicio__gte=timezone.now())
    fora = [a.pk for a in futuros if not dentro_do_expediente(profissional, a.inicio, a.fim)]
    return _sinalizar_reagendamento(Agendamento.objects.filter(pk__in=fora))
