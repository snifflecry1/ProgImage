
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app


# Development image
FROM base AS development

COPY requirements/ /tmp/requirements/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements/base.txt \
                -r /tmp/requirements/dev.txt

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


# Production image
FROM base AS production

COPY requirements/base.txt /tmp/requirements/base.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements/base.txt

COPY . .

RUN groupadd --system app \
    && useradd --system --create-home --home-dir /home/app --gid app app \
    && mkdir -p /app/media \
    && chown -R app:app /app/media

USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
