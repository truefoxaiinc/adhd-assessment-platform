# Production Docker deployment

Copy `.env.production.example` to `.env.production`, replace placeholders, then run:

```sh
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

The stack includes PostgreSQL, persistent Redis, migrations, Daphne for HTTP and
WebSockets, a Celery worker, and Celery Beat. It binds to `127.0.0.1:8000`; place a
TLS reverse proxy in front of it. Create an admin with:

```sh
docker compose exec web python manage.py createsuperuser
```

Application settings currently use `127.0.0.1` for the Channels Redis connection,
so app services share Redis's network namespace. This supports one Docker host.
Make that Redis URL configurable before scaling web containers across hosts.
