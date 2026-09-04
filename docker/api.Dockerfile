# AEGIS API image. Build context is the repo root:
#   docker build -f docker/api.Dockerfile -t aegis-api .
FROM python:3.11-slim AS base

WORKDIR /app/backend

COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir -e .

COPY backend/ ./

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
