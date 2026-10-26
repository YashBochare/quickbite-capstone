# QuickBite container image: tests run inside the build; runtime is minimal and non-root.
FROM python:3.13-slim AS base
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./

FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ ./tests/
RUN python -m pytest -q --junitxml=/srv/test-results.xml tests

FROM base AS runtime
COPY --from=test /srv/test-results.xml /srv/test-results.xml
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} PORT=8000
RUN useradd --uid 10001 --no-create-home appuser
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "main:app"]
