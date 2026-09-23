# Projeto: Agendamento para Clínica de Estética

> Documento de premissas do projeto. Serve como fonte de verdade para o desenvolvimento.
> Itens marcados com **[suposição]** não foram confirmados explicitamente e devem ser revisados.
> Última atualização: 2026-09-22.

---

## 1. Visão geral

Aplicação web para **uma única clínica/estúdio de estética** (um endereço, vários profissionais) gerenciar agendamentos de procedimentos.

- Clientes agendam sozinhos, pelo celular ou pelo computador, **sem criar conta**.
- O gerente também agenda, para quem liga ou manda WhatsApp.
- Cada profissional controla a própria agenda.
- O gerente vê e gerencia a agenda de todos, além de cadastros e relatórios.
- A interface é **responsiva**: funciona bem de telas de celular pequenas até monitores grandes (mobile-first).
- Todo o desenvolvimento roda em **Docker**, sem instalar nada além do Docker na máquina.
- **Nome do app: definir depois.** No código, usar o nome provisório `agendamento`. Nome e identidade visual devem ser fáceis de trocar (configuração, não texto fixo espalhado).

## 2. Glossário

| Termo | Significado |
|---|---|
| **Procedimento** | Serviço oferecido (ex.: limpeza de pele, design de sobrancelha, depilação a laser). Tem duração, intervalo e preço. |
| **Duração** | Tempo do atendimento em si, que é o tempo exibido ao cliente. |
| **Intervalo** | Tempo após o atendimento para higienizar a sala, trocar materiais etc. Bloqueia a agenda, mas não aparece para o cliente. |
| **Tipo de recurso / Recurso** | Categoria de item físico limitado (ex.: tipo *Sala*) e suas unidades (Sala 1, Sala 2, Sala 3). |
| **Horário da clínica** | Horário de funcionamento geral. Limita o horário de trabalho dos profissionais. |
| **Bloqueio** | Período sem atendimento. Pode ser **do profissional** (folga, férias) ou **geral da clínica** (feriado, reforma). |
| **Grade de horários** | Espaçamento entre os horários oferecidos (ex.: 9:00, 9:15, 9:30 com uma grade de 15 min). |
| **Anamnese** | Ficha de saúde do cliente. **Fora do escopo da v1.** |

## 3. Perfis de usuário

### 3.1 Cliente (sem login)
- Agenda um procedimento **sempre escolhendo um profissional específico**. Não existe a opção "qualquer profissional".
- Informa **nome, telefone e data de nascimento**.
- Consulta, reagenda e cancela os próprios agendamentos informando **telefone + data de nascimento**.
- Pode cancelar ou reagendar **a qualquer momento**, sem antecedência mínima.
- Ao reagendar, pode escolher **qualquer horário livre**, mesmo fora da janela de antecedência mínima/máxima. As demais regras de disponibilidade continuam valendo.
- Não recebe notificações na v1: a confirmação aparece apenas na tela.

### 3.2 Profissional (com login)
- Define o **horário de trabalho semanal** (por dia da semana, com pausas como almoço), sempre dentro do horário da clínica.
- Cria **bloqueios** pontuais (folgas, férias, compromissos).
- **Cria, move e cancela** agendamentos na própria agenda.
- Marca o status do atendimento: **atendido** ou **faltou**.
- **Vê apenas a própria agenda.** Não vê a agenda dos colegas.

### 3.3 Gerente (com login)
- **Cadastros** (criar, alterar, inativar):
  - Profissionais, com os procedimentos que cada um realiza (definidos pelo gerente). Ao cadastrar, o gerente define o e-mail de login e uma senha inicial. Inativar o profissional bloqueia o login.
  - Procedimentos: nome, duração, intervalo, preço e recursos necessários
  - Tipos de recurso e recursos (salas e equipamentos)
- **Age em qualquer agenda**: cria, move e cancela agendamentos de qualquer profissional. Também faz o papel de recepção; **não existe perfil de recepcionista**.
- **Visualização**: agenda do dia com todos os profissionais, navegação por data e visão semanal.
- **Relatórios simples**:
  - Atendimentos por período e por profissional
  - Faturamento previsto
  - Taxa de faltas por cliente e por profissional
- **Configurações da clínica**:
  - Horário de funcionamento da clínica (por dia da semana)
  - Bloqueios gerais (feriados, reformas), que valem para todos os profissionais
  - Grade de horários (5, 10, 15 ou 30 min)
  - Antecedência mínima para agendar (ex.: 2h)
  - Antecedência máxima para agendar (ex.: 60 dias)

> Inativar em vez de excluir: profissionais, procedimentos e recursos inativos somem das opções de agendamento, mas continuam no histórico e nos relatórios.

## 4. Regras de negócio

### 4.1 Procedimentos
- Cada procedimento tem **duração**, **intervalo** e **preço fixos**, que não variam por profissional.
- O cliente vê só a duração. A agenda bloqueia **duração + intervalo**.
- Um procedimento pode exigir recursos por **tipo + quantidade** (ex.: "Depilação a laser" exige 1 *Sala* + 1 *Laser*). O sistema **aloca automaticamente** uma unidade livre de cada tipo.
- Cada agendamento tem **um procedimento e um profissional**. Não há combos nem atendimento por vários profissionais na v1.
- Não há pacotes ou sessões na v1: cada agendamento é independente.

### 4.2 Disponibilidade

Um horário está disponível quando, durante **todo o período (duração + intervalo)**:
1. A clínica está aberta e não há bloqueio geral.
2. O profissional está dentro do horário de trabalho.
3. O profissional não tem bloqueio nem outro agendamento.
4. Há unidades livres de cada tipo de recurso exigido **[suposição: o intervalo também ocupa o recurso, já que é tempo de higienização da sala]**.
5. O horário cai na grade configurada.
6. O horário respeita a antecedência mínima e máxima. **Exceção:** não se aplica ao reagendamento pelo cliente nem a agendamentos feitos por profissional ou gerente **[suposição para profissional/gerente]**.

### 4.3 Criação e confirmação
- Agendamentos feitos pelo cliente são **confirmados automaticamente**.
- **Não pode haver agendamento duplo** do profissional nem do recurso. A verificação é garantida no banco de dados, com transação ou lock, para evitar que dois clientes peguem o mesmo horário ao mesmo tempo.
- O agendamento guarda uma **cópia do preço, da duração e do intervalo** no momento da criação. Alterar o procedimento depois não muda agendamentos já feitos nem os relatórios.
- Profissional e gerente nunca podem criar conflitos.

### 4.4 Status do agendamento

```
agendado ──► atendido
   │    └──► faltou
   ├──► cancelado  (por cliente, profissional ou gerente)
   └──► precisa_reagendar  (horário atingido por um bloqueio)
            ├──► agendado (reagendado)
            └──► cancelado
```

- Registrar **quem** cancelou e **quando**.
- Bloqueios (do profissional ou gerais) sobre horários já agendados são **permitidos**. Os agendamentos afetados viram **precisa reagendar** e aparecem em destaque para o gerente resolver.

### 4.5 Cliente
- O cliente é identificado pelo **telefone**, normalizado (ex.: +5511999999999). O mesmo telefone corresponde ao mesmo cliente.
- Para acessar os agendamentos, o cliente informa **telefone + data de nascimento**; os dois precisam bater.
- Tentativas de acesso têm **limite (rate limiting)** para impedir que alguém teste datas até acertar.
- **LGPD:** mostrar um aviso ou checkbox de consentimento no primeiro agendamento e coletar só os dados necessários.

### 4.6 Decisões da implementação da agenda
- **Horário de trabalho:** até **dois períodos por dia** (ex.: 09:00–12:00 e 13:00–18:00), sempre dentro do horário da clínica.
- **Mudanças de horário:** se o profissional muda os horários de trabalho, ou o gerente muda o horário da clínica, os agendamentos futuros que ficam fora do expediente viram **precisa reagendar**, igual aos bloqueios.
- **Agendamento pela equipe:** a data de nascimento do cliente é **opcional**. Se o cliente agendar online depois, com o mesmo telefone, a data é completada.
- **Mesmo telefone, mesmo cliente:** um telefone já cadastrado mantém o nome existente.
- **Horário e recursos liberados:** um agendamento em **precisa reagendar** ou **cancelado** deixa de ocupar o horário e as salas e equipamentos.
- **Registro de presença:** atendido ou faltou só pode ser marcado **depois do horário do agendamento**. É possível corrigir de um para o outro.
- **Troca de profissional:** ao remarcar, o **gerente** pode passar o agendamento para outro profissional que realize o procedimento (útil para resolver pendências, como férias). O profissional só remarca dentro da própria agenda.
- **Tela inicial do gerente:** é a agenda do dia com uma coluna por profissional ativo, com aviso de pendências.
- **Relatórios:**
  - **Faturamento realizado** é a soma dos atendidos.
  - **Faturamento previsto** soma atendidos e agendados. Cancelados, faltas e "precisa reagendar" ficam de fora.
  - **Taxa de faltas** é faltas ÷ (atendidos + faltas). Agendamentos já passados sem registro de presença não entram na conta, e o relatório avisa quando existem.
  - Os valores usam o preço do momento do agendamento e incluem profissionais inativos.
  - O período padrão é o mês atual, com limite de um ano.
- **Agendamento duplo:** o banco de dados (PostgreSQL, *exclusion constraints*) impede sobreposição para o mesmo profissional ou recurso, mesmo com duas requisições simultâneas.

### 4.7 Fuso horário
- Um único fuso: **America/Sao_Paulo** **[suposição]**.

## 5. Fora do escopo da v1

- Notificações ao cliente (WhatsApp, SMS, e-mail)
- Pagamento online, sinal ou Pix (o pagamento é feito na clínica)
- Pacotes e sessões
- Anamnese e ficha de saúde
- Opção "qualquer profissional"
- Múltiplas unidades ou modelo SaaS
- Duração ou preço diferentes por profissional
- Vários procedimentos ou profissionais em uma única visita
- Perfil de recepcionista
- App nativo

## 6. Tecnologia

| Camada | Escolha |
|---|---|
| Back-end | **Python + Django** |
| Front-end | Templates Django + **HTMX** (interatividade sem SPA) + **Tailwind CSS** (responsivo) |
| Banco de dados | **PostgreSQL** |
| Autenticação | Auth nativa do Django para profissionais e gerente (grupos/permissões) |
| Ambiente | **Docker + Docker Compose** |
| Testes | pytest + pytest-django **[suposição]** |

### 6.1 Docker
- `docker compose up` sobe tudo: app Django e PostgreSQL. O build do Tailwind roda em container ou via standalone CLI.
- Nenhuma dependência instalada na máquina host além do Docker.
- Comandos de desenvolvimento rodam dentro do container, por exemplo:
  - `docker compose run --rm web python manage.py migrate`
  - `docker compose run --rm web python manage.py createsuperuser`
  - `docker compose run --rm web pytest`
- O código é montado como volume para recarregar automaticamente durante o desenvolvimento.
- Configuração via variáveis de ambiente (`.env`, com `.env.example` versionado).
- **Hospedagem de produção: definir depois.** A imagem deve ser pronta para qualquer servidor com Docker.

## 7. Modelo de dados inicial (rascunho)

- **Profissional**: usuário, nome, ativo, procedimentos que realiza
- **HorarioClinica**: dia da semana, início, fim
- **HorarioTrabalho**: profissional, dia da semana, início, fim (várias linhas por dia para permitir pausas)
- **Bloqueio**: profissional (vazio = bloqueio geral da clínica), início, fim, motivo
- **Procedimento**: nome, descrição, duração (min), intervalo (min), preço, ativo
- **TipoRecurso**: nome (Sala, Laser...)
- **Recurso**: tipo, nome, ativo
- **ProcedimentoRecurso**: procedimento, tipo de recurso, quantidade
- **Cliente**: nome, telefone (único), data de nascimento, data do consentimento LGPD
- **Agendamento**: cliente, profissional, procedimento, início, fim (duração + intervalo), preço/duração/intervalo copiados, status, origem (cliente/profissional/gerente), cancelado por, cancelado em
- **AgendamentoRecurso**: agendamento, recurso alocado
- **Configuracao**: nome da clínica/app, grade (min), antecedência mínima, antecedência máxima

## 8. Telas principais

**Cliente (público):**
1. Escolher o procedimento
2. Escolher o profissional
3. Escolher dia e horário
4. Informar dados e confirmar
5. Ver a confirmação
6. "Meus agendamentos": telefone + data de nascimento, com lista, cancelamento e reagendamento

**Profissional:**
- Minha agenda (dia/semana)
- Meus horários de trabalho
- Meus bloqueios
- Novo agendamento

**Gerente:**
- Agenda do dia, com uma coluna por profissional
- Visão semanal e navegação por data
- Pendências ("precisa reagendar")
- Cadastros
- Relatórios
- Configurações (horário da clínica, bloqueios gerais, regras de agendamento)

## 9. Pontos em aberto

- [ ] Nome e identidade visual do app.
- [ ] Hospedagem de produção e domínio.
