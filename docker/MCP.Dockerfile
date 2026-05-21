FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    "mcp>=1.12,<2" \
    "psycopg[binary]>=3.2,<4" \
    "pgvector>=0.4,<1" \
    "fastembed>=0.4,<1" \
    "numpy>=1.26,<3"

RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-large-en-v1.5')" \
 && python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder(model_name='BAAI/bge-reranker-base')"

COPY mcp_server /app/mcp_server

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "mcp_server.server"]
