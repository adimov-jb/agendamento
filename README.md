# Agendamento

App web de agendamento para vários estabelecimentos (clínicas, barbearias e salões de beleza). Premissas e regras de negócio em [PROJETO.md](PROJETO.md).

Stack: Django + HTMX + Tailwind CSS + PostgreSQL, tudo em Docker. Basta ter o Docker instalado.

## Primeira vez

```sh
cp .env.example .env        # no PowerShell: Copy-Item .env.example .env
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Acesse http://localhost:8000 (ou a porta definida em `WEB_PORT` no `.env`).

- **Super Admin:** só o login `andredimov@hotmail.com` (fixo em `SUPER_ADMIN_LOGIN`, em `config/settings.py`). Cadastra os estabelecimentos (nome, tipo e endereço) e entra em qualquer um deles como gerente.
- **Área da equipe:** `/entrar/`. Quem participa de mais de um estabelecimento escolhe, ao entrar, o estabelecimento e o perfil (gerente ou profissional).
- **Profissionais:** o gerente os cadastra em *Profissionais* informando nome e e-mail; o sistema envia um convite por e-mail. Pelo link, o profissional cria a senha (ou entra com o login que já tem, se já atua em outro estabelecimento). Em desenvolvimento, sem `EMAIL_HOST`, o e-mail aparece em `docker compose logs web`; o link também fica na lista de convites pendentes.
- **Clientes:** cada estabelecimento tem a sua página, em `/<endereço>/` (ex.: `/barbearia-do-ze/`). A página inicial `/` lista os estabelecimentos, ou vai direto para ele se só houver um.

## Estrutura

| App | Conteúdo |
|---|---|
| `core` | Layout, login, permissões e escolha do estabelecimento/perfil (`core/permissions.py`), painel inicial |
| `clinica` | Estabelecimentos (tipo, endereço, foto, regras de agendamento) e horário de funcionamento. A foto é reduzida para WebP de até 800px e guardada no banco, porque o disco do Render é apagado a cada deploy. O nome do app ficou `clinica` por compatibilidade com o banco; na interface é "Estabelecimento" |
| `catalogo` | Procedimentos, tipos de recurso e recursos (salas/equipamentos) |
| `equipe` | Profissionais de cada estabelecimento e convites por e-mail |
| `agenda` | Clientes, horários de trabalho, bloqueios, agendamentos e o cálculo de disponibilidade (`agenda/servicos.py`). Telas do profissional e do gerente, incluindo relatórios |
| `publico` | Área do cliente, sem login, em `/<endereço do estabelecimento>/`: agendamento online e "Meus agendamentos" (telefone + data de nascimento) |

## Dia a dia

| Tarefa | Comando |
|---|---|
| Subir o ambiente | `docker compose up -d` |
| Parar | `docker compose down` |
| Ver logs | `docker compose logs -f web` |
| Rodar testes | `docker compose run --rm web pytest` |
| Criar migrações | `docker compose exec web python manage.py makemigrations` |
| Aplicar migrações | `docker compose exec web python manage.py migrate` |
| Shell do Django | `docker compose exec web python manage.py shell` |
| Após mudar `requirements.txt` | `docker compose up -d --build` |

O código é montado dentro do container: alterações em Python e templates recarregam sozinhas. O serviço `tailwind` recompila `static/css/app.css` sempre que um template muda.

## Serviços

- **web**: Django (runserver em desenvolvimento)
- **db**: PostgreSQL 16 (dados persistem no volume `postgres_data`)
- **tailwind**: compila o CSS em modo watch

## Deploy (Render + Neon)

A imagem de produção compila o CSS e coleta os estáticos no build. Ao iniciar ([iniciar.sh](iniciar.sh)), aplica as migrações, cria o primeiro gerente (se `GERENTE_EMAIL`/`GERENTE_SENHA` estiverem definidos) e sobe o gunicorn na porta `PORT`.

No Render: **New → Web Service**, escolha o repositório, runtime **Docker**, e defina as variáveis:

| Variável | Valor |
|---|---|
| `DJANGO_SECRET_KEY` | chave aleatória longa (botão *Generate*) |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `seu-app.onrender.com` (e o domínio próprio, separados por vírgula) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | host do banco / `5432` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | da string de conexão `postgresql://USER:PASSWORD@HOST/DB` |
| `POSTGRES_SSLMODE` | `require` (Neon) |
| `POSTGRES_POOLER` | `1` só se usar o host com `-pooler` do Neon |
| `PROXIES_CONFIAVEIS` | `1` |
| `GERENTE_EMAIL` / `GERENTE_SENHA` | cria o primeiro usuário, se ainda não existir. Use `andredimov@hotmail.com` para que ele seja o Super Admin (pode remover depois do primeiro deploy) |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | servidor SMTP para os convites e a recuperação de senha |
| `DEFAULT_FROM_EMAIL` | remetente dos e-mails (ex.: `Agendamento <nao-responda@seudominio.com>`) |

Em *Settings*, use `/health/` como **Health Check Path**.
