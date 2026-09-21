# Fly Brain dashboard + LIF server. Same image on Mac / Linux / ARM / x86.
#   docker compose up --build
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-mac.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements-mac.txt

COPY mac ./mac
COPY shared ./shared
COPY data ./data
COPY connectome_cache.npz ./connectome_cache.npz

RUN useradd --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/state >/dev/null || exit 1

CMD ["python", "-m", "mac.server"]
