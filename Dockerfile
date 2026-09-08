FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr \
       tesseract-ocr-por \
       tesseract-ocr-eng \
       libgl1 \
       libglib2.0-0 \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts

RUN pip install --no-cache-dir . \
    && python scripts/download_models.py \
    && groupadd --system faceapp \
    && useradd --system --gid faceapp --home-dir /app --shell /usr/sbin/nologin faceapp \
    && mkdir -p /app/data \
    && chown -R faceapp:faceapp /app

USER faceapp

EXPOSE 8091

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8091/api/v1/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091"]
