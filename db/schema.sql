-- Drops and recreates everything: all data can be rebuilt from the Documents.
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS documents;

CREATE TABLE documents (
    id serial PRIMARY KEY,
    name text NOT NULL UNIQUE,  -- FinanceBench doc_name, e.g. 3M_2018_10K
    company text NOT NULL,
    doc_type text NOT NULL,     -- 10-K, 10-Q, 8-K, Earnings
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
    UNIQUE (document_id, page, position)
);

-- No approximate-nearest-neighbor index: exact search keeps approximation noise out of the
-- baseline. Search with cosine distance: ORDER BY embedding <=> query.
