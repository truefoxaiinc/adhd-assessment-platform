# Production Docker deployment

Copy `.env.production.example` to `.env.production`, replace placeholders, then run:

```sh
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

The stack connects to AWS RDS PostgreSQL and includes persistent Redis, migrations,
Daphne for HTTP and WebSockets, a Celery worker, and Celery Beat. It binds to
`127.0.0.1:8000`; place a
TLS reverse proxy in front of it. Create an admin with:

```sh
docker compose exec web python manage.py createsuperuser
```

## AWS RDS

Create a PostgreSQL RDS instance and set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
`DATABASE_PASSWORD`, and `PGSSLMODE=require` in `.env.production`. The RDS security group must allow
TCP port 5432 inbound from the backend host's security group (preferred) or its
private IP—not from `0.0.0.0/0`. Keep RDS private when the backend runs in the same
VPC, enable storage encryption and automated backups, and require SSL connections.

Before deployment, verify connectivity from the Docker host:

```sh
docker compose run --rm migrate python manage.py migrate --check
```

On first deployment, `docker compose up -d` runs migrations against RDS before the
web, worker, and beat services start.

Application settings currently use `127.0.0.1` for the Channels Redis connection,
so app services share Redis's network namespace. This supports one Docker host.
Make that Redis URL configurable before scaling web containers across hosts.
