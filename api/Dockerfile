# Build stage: install the app and its dependencies into a virtualenv.
FROM python:3.12-slim AS build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install .

# Runtime stage: only the virtualenv, running as an unprivileged user.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
# /data/uploads is the shared upload volume; chown so appuser can write.
RUN useradd --create-home appuser \
    && mkdir -p /data/uploads \
    && chown -R appuser:appuser /data
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
