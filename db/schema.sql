-- Drops and recreates everything: all data can be rebuilt from the Documents.
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS corpus_settings;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS documents;

-- How the stored Chunks were made, so runs record that rather than today's code: one row,
-- written by the first ingest.
CREATE TABLE corpus_settings (
    one_row boolean PRIMARY KEY DEFAULT true CHECK (one_row),
    embedding_model text NOT NULL,
    chunk_tokens int NOT NULL,
    overlap_tokens int NOT NULL
);

CREATE TABLE documents (
    id serial PRIMARY KEY,
    name text NOT NULL UNIQUE,  -- FinanceBench doc_name, e.g. 3M_2018_10K
    company text NOT NULL,
    doc_type text NOT NULL CHECK (doc_type IN ('10-K', '10-Q', '8-K', 'Earnings')),
    fiscal_year int NOT NULL,
    page_count int NOT NULL
);

CREATE TABLE chunks (
    id serial PRIMARY KEY,
    document_id int NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    page int NOT NULL,          -- 1-based
    position int NOT NULL,      -- order within the Page
    text text NOT NULL,
    token_count int NOT NULL,
    embedding vector(1536) NOT NULL,  -- text-embedding-3-small
    -- Keyword search; queries must use the same 'english' config
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    UNIQUE (document_id, page, position)
);
CREATE INDEX chunks_tsv ON chunks USING gin (tsv);

-- No approximate-nearest-neighbor index: exact search keeps approximation noise out of the
-- baseline. Search with cosine distance: ORDER BY embedding <=> query.
