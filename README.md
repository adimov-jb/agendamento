# Agendamento

App web de agendamento para clínica de estética. Premissas e regras de negócio em [PROJETO.md](PROJETO.md).

Stack: Django + HTMX + Tailwind CSS + PostgreSQL, tudo em Docker. Basta ter o Docker instalado.

## Primeira vez

```sh
cp .env.example .env        # no PowerShell: Copy-Item .env.example .env
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Acesse http://localhost:8000 (ou a porta definida em `WEB_PORT` no `.env`).

- **Área da equipe:** `/entrar/`. O superusuário conta como gerente. Outros gerentes são usuários no grupo "Gerente" (via `/admin/`).
- **Profissionais:** o gerente os cadastra em *Profissionais*, definindo o e-mail e a senha inicial de cada um.

## Estrutura

| App | Conteúdo |
|---|---|
| `core` | Layout, login, permissões (`eh_gerente`), painel inicial |
| `clinica` | Configuração da clínica (regras de agendamento) e horário de funcionamento |
| `catalogo` | Procedimentos, tipos de recurso e recursos (salas/equipamentos) |
| `equipe` | Profissionais e seus logins |
| `agenda` | Clientes, horários de trabalho, bloqueios, agendamentos e o cálculo de disponibilidade (`agenda/servicos.py`) |

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
