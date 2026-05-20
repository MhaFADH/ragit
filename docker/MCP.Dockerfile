FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    "mcp>=1.12,<2" \
    "psycopg[binary]>=3.2,<4"

COPY mcp_server /app/mcp_server

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "mcp_server.server"]
