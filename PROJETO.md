# Projeto: Agendamento para Clínicas, Barbearias e Salões de Beleza

> Documento de premissas do projeto. Serve como fonte de verdade para o desenvolvimento.
> Itens marcados com **[suposição]** não foram confirmados explicitamente e devem ser revisados.
> Última atualização: 2026-09-28.

---

## 1. Visão geral

Aplicação web para **vários estabelecimentos** gerenciarem agendamentos. Cada estabelecimento é de um tipo: **Clínica**, **Barbearia** ou **Salão de Beleza**. Tudo (equipe, procedimentos, recursos, clientes, bloqueios e agendamentos) pertence a um estabelecimento, e cada tela mostra só os dados do estabelecimento em uso.

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
| **Estabelecimento** | Clínica, barbearia ou salão. Tem nome, tipo, endereço da página de agendamento (ex.: `/barbearia-do-ze/`), regras de agendamento e horário de funcionamento. |
| **Colaborador** | Usuário que atua em um ou mais estabelecimentos, como gerente e/ou profissional, com um único login. |
| **Procedimento** | Serviço oferecido (ex.: limpeza de pele, design de sobrancelha, depilação a laser). Tem duração, intervalo e preço. |
| **Duração** | Tempo do atendimento em si, que é o tempo exibido ao cliente. |
| **Intervalo** | Tempo após o atendimento para higienizar a sala, trocar materiais etc. Bloqueia a agenda, mas não aparece para o cliente. |
| **Tipo de recurso / Recurso** | Categoria de item físico limitado (ex.: tipo *Sala*) e suas unidades (Sala 1, Sala 2, Sala 3). |
| **Horário de funcionamento** | Horário do estabelecimento. Limita o horário de trabalho dos profissionais. |
| **Bloqueio** | Período sem atendimento. Pode ser **do profissional** (folga, férias) ou **geral do estabelecimento** (feriado, reforma). |
| **Grade de horários** | Espaçamento entre os horários oferecidos (ex.: 9:00, 9:15, 9:30 com uma grade de 15 min). |
| **Anamnese** | Ficha de saúde do cliente. **Fora do escopo da v1.** |

## 3. Perfis de usuário

Super Admin, Gerente, Profissional e Cliente. O Super Admin está descrito em 3.4.

### 3.1 Cliente (sem login)
- Agenda um procedimento **sempre escolhendo um profissional específico**. Não existe a opção "qualquer profissional".
- Informa **nome, telefone e data de nascimento**.
- Consulta, reagenda e cancela os próprios agendamentos informando **telefone + data de nascimento**.
- Pode cancelar ou reagendar **a qualquer momento**, sem antecedência mínima.
- Ao reagendar, pode escolher **qualquer horário livre**, mesmo fora da janela de antecedência mínima/máxima. As demais regras de disponibilidade continuam valendo.
- Não recebe notificações na v1: a confirmação aparece apenas na tela.

### 3.2 Profissional (com login)
- Define o **horário de trabalho semanal** (por dia da semana, com pausas como almoço), sempre dentro do horário do estabelecimento.
- Cria **bloqueios** pontuais (folgas, férias, compromissos).
- **Cria, move e cancela** agendamentos na própria agenda.
- Marca o status do atendimento: **atendido** ou **faltou**.
- **Vê apenas a própria agenda.** Não vê a agenda dos colegas.

### 3.3 Gerente (com login)
- **Cadastros** (criar, alterar, inativar):
  - Profissionais, com os procedimentos que cada um realiza (definidos pelo gerente). Ao cadastrar, o gerente informa nome e e-mail e o sistema envia um **convite por e-mail**; o profissional vira colaborador ao aceitar, criando a senha ou usando o login que já tem. Inativar o profissional tira o acesso dele **àquele estabelecimento** (o login continua valendo nos outros).
  - Procedimentos: nome, duração, intervalo, preço e recursos necessários
  - Tipos de recurso e recursos (salas e equipamentos)
- **Age em qualquer agenda**: cria, move e cancela agendamentos de qualquer profissional. Também faz o papel de recepção; **não existe perfil de recepcionista**.
- **Visualização**: agenda do dia com todos os profissionais, navegação por data e visão semanal.
- **Relatórios simples**:
  - Atendimentos por período e por profissional
  - Faturamento previsto
  - Taxa de faltas por cliente e por profissional
- **Configurações do estabelecimento**:
  - Nome, tipo (Clínica, Barbearia ou Salão de Beleza) e endereço da página de agendamento
  - Horário de funcionamento (por dia da semana)
  - Bloqueios gerais (feriados, reformas), que valem para todos os profissionais
  - Grade de horários (5, 10, 15 ou 30 min)
  - Antecedência mínima para agendar (ex.: 2h)
  - Antecedência máxima para agendar (ex.: 60 dias)

### 3.4 Vários estabelecimentos
- **Super Admin:** perfil de um único usuário (login `andredimov@hotmail.com`). Só ele **cadastra estabelecimentos**, escolhendo o tipo, e pode **entrar em qualquer estabelecimento como gerente**, sem precisar estar cadastrado como gerente dele. Depois de cadastrar, ele convida a equipe; quem vai administrar recebe o convite com "também será gerente".
- Um usuário pode ser **gerente e/ou profissional em vários estabelecimentos**, com o mesmo login.
- **Ao entrar**, o colaborador escolhe o estabelecimento e o perfil. Com uma única opção, entra direto. Dá para trocar pelo topo da página.
- **Convites** valem 7 dias, podem ser reenviados (gera um link novo) ou cancelados. O convite pode já dar o perfil de gerente.
- Cada colaborador cuida da própria senha ("Esqueci minha senha" no login).
- Os dados existentes antes dos vários estabelecimentos ficaram no primeiro estabelecimento (tipo Clínica).

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
1. O estabelecimento está aberto e não há bloqueio geral.
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
- O cliente é identificado pelo **telefone**, normalizado (ex.: +5511999999999), **dentro do estabelecimento**: o mesmo telefone em dois estabelecimentos são dois clientes, e "Meus agendamentos" mostra só os do estabelecimento da página.
- Para acessar os agendamentos, o cliente informa **telefone + data de nascimento**; os dois precisam bater.
- Tentativas de acesso têm **limite (rate limiting)** para impedir que alguém teste datas até acertar.
- **LGPD:** mostrar um aviso ou checkbox de consentimento no primeiro agendamento e coletar só os dados necessários.

### 4.6 Decisões da implementação da agenda
- **Horário de trabalho:** até **dois períodos por dia** (ex.: 09:00–12:00 e 13:00–18:00), sempre dentro do horário do estabelecimento.
- **Mudanças de horário:** se o profissional muda os horários de trabalho, ou o gerente muda o horário do estabelecimento, os agendamentos futuros que ficam fora do expediente viram **precisa reagendar**, igual aos bloqueios.
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
- **Agendamento online (cliente):**
  - A página inicial lista só os procedimentos ativos que têm pelo menos um profissional ativo.
  - Se só um profissional realiza o procedimento, ele já vem escolhido.
  - Um telefone já cadastrado só agenda com a **mesma data de nascimento**. Se a equipe o cadastrou sem data, ela é completada.
  - O consentimento LGPD é obrigatório e fica registrado no cliente.
- **Acesso a "Meus agendamentos":**
  - Após agendar ou se identificar, o cliente fica identificado por **30 minutos**, renovados a cada acesso.
  - Pode cancelar ou remarcar só **agendamentos futuros em aberto**, sempre com o mesmo profissional.
  - Clientes cadastrados pela equipe sem data de nascimento não conseguem entrar até ela ser informada.
- **Limite de tentativas:** até 5 falhas por telefone e 20 por IP em 15 minutos. As tentativas ficam no banco para valer com vários processos do servidor.
- **Agendamento duplo:** o banco de dados (PostgreSQL, *exclusion constraints*) impede sobreposição para o mesmo profissional ou recurso, mesmo com duas requisições simultâneas.

### 4.7 Fuso horário
- Um único fuso: **America/Sao_Paulo** **[suposição]**.

## 5. Fora do escopo da v1

- Notificações ao cliente (WhatsApp, SMS, e-mail)
- Pagamento online, sinal ou Pix (o pagamento é feito no estabelecimento)
- Pacotes e sessões
- Anamnese e ficha de saúde
- Opção "qualquer profissional"
- Cobrança/planos por estabelecimento (modelo SaaS pago)
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

## 7. Modelo de dados

- **Estabelecimento**: nome, tipo, endereço (slug), gerentes, grade (min), antecedência mínima, antecedência máxima
- **Profissional**: usuário, estabelecimento, nome, ativo, procedimentos que realiza (um por usuário em cada estabelecimento)
- **Convite**: estabelecimento, e-mail, nome, também gerente, procedimentos, token, enviado em, aceito em
- **HorarioFuncionamento**: estabelecimento, dia da semana, início, fim
- **HorarioTrabalho**: profissional, dia da semana, início, fim (várias linhas por dia para permitir pausas)
- **Bloqueio**: estabelecimento, profissional (vazio = bloqueio geral do estabelecimento), início, fim, motivo
- **Procedimento**: estabelecimento, nome, descrição, duração (min), intervalo (min), preço, ativo
- **TipoRecurso**: estabelecimento, nome (Sala, Laser, Cadeira...)
- **Recurso**: tipo, nome, ativo
- **ProcedimentoRecurso**: procedimento, tipo de recurso, quantidade
- **Cliente**: estabelecimento, nome, telefone (único no estabelecimento), data de nascimento, data do consentimento LGPD
- **Agendamento**: estabelecimento, cliente, profissional, procedimento, início, fim (duração + intervalo), preço/duração/intervalo copiados, status, origem (cliente/profissional/gerente), cancelado por, cancelado em
- **AgendamentoRecurso**: agendamento, recurso alocado

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
- Estabelecimento (dados, tipo, horário de funcionamento, regras de agendamento) e feriados/fechamentos

## 9. Pontos em aberto

- [ ] Nome e identidade visual do app.
- [ ] Hospedagem de produção e domínio.

### Antes de colocar em produção
- [x] **IP real do cliente atrás de proxy:** `publico/acesso.py::ip_de` usa o `X-Forwarded-For` conforme `PROXIES_CONFIAVEIS` (Render: 1).
- [ ] **Proteção contra agendamentos em massa (spam):** não há captcha nem limite por IP na criação de agendamentos online.
- [x] **Configurações de segurança do Django:** `DEBUG=0`, `SECRET_KEY` forte e `ALLOWED_HOSTS` por variável de ambiente; HTTPS atrás de proxy (`SECURE_PROXY_SSL_HEADER`), cookies seguros e `CSRF_TRUSTED_ORIGINS` em produção.
