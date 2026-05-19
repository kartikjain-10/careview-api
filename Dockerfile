FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers + chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Pre-download embedding model into the image so cold starts are fast.
# If the download fails (e.g. no internet at build time) the image still
# builds — the model will be fetched on first request instead.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('BAAI/bge-small-en-v1.5')" || \
    echo "Model pre-download skipped — will fetch at runtime."

# Persistent data directories (Render mounts a disk here in paid tier;
# on free tier data survives restarts but resets on redeploy — fine for now)
RUN mkdir -p data/chroma data/uploads

EXPOSE 8000

# $PORT is injected by Render at runtime
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
