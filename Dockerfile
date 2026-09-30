# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev libopenblas-dev libpq-dev pkg-config && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip 'setuptools<81' wheel && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.11-slim-bookworm AS runtime
ARG APP_UID=10001
ARG APP_GID=10001
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1 DJANGO_ENV=production QT_QPA_PLATFORM=offscreen PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends libegl1 libgl1 libglib2.0-0 libgomp1 liblapack3 libmariadb3 libopenblas0 libpq5 libsm6 libxext6 libxrender1 && rm -rf /var/lib/apt/lists/* && groupadd --gid ${APP_GID} app && useradd --uid ${APP_UID} --gid app --create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app . .
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod 0555 /usr/local/bin/entrypoint && mkdir -p /app/tmp_uploads && chown -R app:app /app/tmp_uploads
USER app
RUN SECRET_KEY=build-only-secret JWT_SIGNING_KEY=build-only-jwt-key DATABASE_PASSWORD=build-only-password FACEBOOK_APP_SECRET=build-only-secret EMAIL_HOST_PASSWORD=build-only-password AWS_ACCESS_KEY_ID=build-only-key AWS_SECRET_ACCESS_KEY=build-only-secret FIREBASE_INITIALIZE=False python manage.py collectstatic --noinput
EXPOSE 8000
STOPSIGNAL SIGTERM
ENTRYPOINT [entrypoint]
CMD [daphne, -b, 0.0.0.0, -p, 8000, --proxy-headers, project_adhd.asgi:application]
