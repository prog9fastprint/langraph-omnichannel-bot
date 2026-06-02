-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the shopify product table
CREATE TABLE IF NOT EXISTS ai_product_shopify  (
    id SERIAL PRIMARY KEY,
    handle VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    body TEXT,
    vendor VARCHAR(255),
    tags TEXT,
    variant_sku VARCHAR(100),
    variant_price DECIMAL(10,2),
    embedding vector(1536) -- 1536 dimensions matching gemini-embedding-2 output
);

-- Create HNSW index for fast cosine distance similarity search
CREATE INDEX IF NOT EXISTS ai_product_shopify_embedding_hnsw_idx 
ON ai_product_shopify 
USING hnsw (embedding vector_cosine_ops);

-- Copy data from CSV (Make sure the path matches your environment)
\COPY ai_product_shopify(handle, title, body, vendor, tags, variant_sku, variant_price)
FROM 'F:\prog9\python-omnichannel-ai\scripts\products_for_postgres_final.csv'
WITH (FORMAT csv, HEADER true, QUOTE '"', ENCODING 'UTF8');
