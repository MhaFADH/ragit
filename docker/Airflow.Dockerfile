FROM apache/airflow:3.1.6-python3.12

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir \
    "psycopg[binary]>=3.2,<4" \
    "pgvector>=0.4,<1" \
    "langchain-text-splitters>=0.3,<1" \
    "fastembed>=0.4,<1" \
    "tokenizers>=0.20,<1" \
    "numpy>=1.26,<3"

RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-large-en-v1.5')" \
 && python -c "from tokenizers import Tokenizer; Tokenizer.from_pretrained('BAAI/bge-large-en-v1.5')"
