CREATE TABLE IF NOT EXISTS ai_product_shopify  (
    id SERIAL PRIMARY KEY,
    handle VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    body TEXT,
    vendor VARCHAR(255),
    tags TEXT,
    variant_sku VARCHAR(100),
    variant_price DECIMAL(10,2)
);

\COPY ai_product_shopify(handle, title, body, vendor, tags, variant_sku, variant_price)
FROM 'F:\prog9\python-omnichannel-ai\scripts\products_for_postgres_final.csv'
WITH (FORMAT csv, HEADER true, QUOTE '"', ENCODING 'UTF8');

