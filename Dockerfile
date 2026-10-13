# API, ETL and air archiver image (Python 3.12, same minor version as the dev venv; D-001).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# rasterio wheels need libexpat at runtime
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY etl ./etl
COPY api ./api
RUN pip install .
COPY config ./config
COPY data/manifest.yml ./data/manifest.yml
EXPOSE 8000
# access log off: geocoder queries may contain addresses (privacy, CLAUDE.md)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
