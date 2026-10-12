# Production Docker deployment

Copy `.env.production.example` to `.env.production`, replace placeholders, then run:

```sh
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

The stack includes persistent PostgreSQL and Redis, migrations, Daphne for HTTP
and WebSockets, a Celery worker, and Celery Beat. It binds to `127.0.0.1:8000`;
place a TLS reverse proxy in front of it. Create an admin with:

```sh
docker compose exec web python manage.py createsuperuser
```

## PostgreSQL

Set `DB_HOST=postgres`, `DB_PORT=5432`, `DB_NAME`, `DB_USER`,
`DATABASE_PASSWORD`, and `PGSSLMODE=disable` in `.env.production`. Set matching
`POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` values for the database
container. PostgreSQL is private to the Compose network and persists in the
`postgres_data` volume.

Before deployment, verify connectivity from the Docker host:

```sh
docker compose run --rm migrate python manage.py migrate --check
```

On first deployment, `docker compose up -d` waits for PostgreSQL to become healthy
and runs migrations before the web, worker, and beat services start.

The build uses host networking to accommodate dedicated servers whose Docker
bridge cannot reach external DNS during `apt-get` and package installation.

Uploaded media is bind-mounted at `./media`. Before first startup, create the
directory and grant it to the container user:

```sh
mkdir -p media
sudo chown -R 10001:10001 media
```

Configure the host reverse proxy to serve `/media/` from this directory. Do not
run `docker compose down -v` unless you intend to delete PostgreSQL and Redis data.
