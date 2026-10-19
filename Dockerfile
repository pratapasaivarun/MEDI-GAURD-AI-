FROM python:3.13.1-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDIGUARD_CORE_DEMO=false \
    MEDIGUARD_TRUSTED_FIXTURES=false \
    AUTH_REQUIRED=true \
    MEDIGUARD_DB_PATH=/app/data/mediguard.db \
    MEDIGUARD_STORAGE_DIR=/app/data \
    CHROMA_DIR=/app/data/chroma \
    TESSERACT_CMD=/usr/bin/tesseract

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system mediguard \
    && useradd --system --gid mediguard --home-dir /app --no-create-home mediguard \
    && mkdir -p /app/data \
    && chown -R mediguard:mediguard /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=mediguard:mediguard . .

VOLUME ["/app/data"]
EXPOSE 8501
USER mediguard

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
