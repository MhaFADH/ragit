CREATE DATABASE docs_rag;
CREATE USER docs_rag WITH PASSWORD 'docs_rag';
GRANT ALL PRIVILEGES ON DATABASE docs_rag TO docs_rag;

\c docs_rag
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON SCHEMA public TO docs_rag;

CREATE TABLE documents (
    repo      TEXT NOT NULL,
    branch    TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL,
    sha256    TEXT NOT NULL,
    PRIMARY KEY (repo, branch, file_path)
);

CREATE TABLE chunks (
    id           BIGSERIAL PRIMARY KEY,
    repo         TEXT NOT NULL,
    branch       TEXT NOT NULL DEFAULT '',
    file_path    TEXT NOT NULL,
    chunk_index  INT NOT NULL,
    heading_path TEXT,
    content      TEXT NOT NULL,
    token_count  INT NOT NULL,
    embedding    vector(1024) NOT NULL,
    FOREIGN KEY (repo, branch, file_path)
        REFERENCES documents (repo, branch, file_path)
        ON DELETE CASCADE
);

CREATE INDEX chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

GRANT ALL ON ALL TABLES IN SCHEMA public TO docs_rag;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO docs_rag;
