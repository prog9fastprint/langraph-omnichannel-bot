import os
import asyncio
import logging
from dotenv import load_dotenv
import psycopg
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_embeddings")

# Load environment variables
load_dotenv()

# We will read VECTOR_DB_URL from the env, falling back to ERP_DB_URL if not set
DB_URL = os.getenv("VECTOR_DB_URL") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def ingest_embeddings():
    if not DB_URL:
        logger.error("Database connection URL (VECTOR_DB_URL or ERP_DB_URL) is not set.")
        return

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set.")
        return

    logger.info("Initializing Google Gemini Embeddings client...")
    # 1. Update your primary model to the current standard
    embeddings_client = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2",  
        google_api_key=GEMINI_API_KEY,
        output_dimensionality=1536
    )
    
    # 2. Fix the naming convention string for your fallback model
    fallback_client = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",  # Added 'gemini-' prefix
        google_api_key=GEMINI_API_KEY,
        output_dimensionality=1536
    )

    logger.info("Connecting to the database...")
    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor() as cur:
            # 1. Fetch products that don't have embeddings yet
            await cur.execute(
                "SELECT id, title, body, tags FROM ai_product_shopify WHERE embedding IS NULL"
            )
            rows = await cur.fetchall()
            logger.info(f"Found {len(rows)} products needing embeddings.")

            if not rows:
                logger.info("No products to process.")
                return

            # Batch update embeddings
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch_rows = rows[i:i + batch_size]
                
                logger.info(f"Processing batch {i//batch_size + 1} of {(len(rows) + batch_size - 1)//batch_size} (Items {i+1} to {i+len(batch_rows)})...")
                
                texts_to_embed = []
                for row in batch_rows:
                    product_id, title, body, tags = row
                    texts_to_embed.append(f"Title: {title or ''}\nDescription: {body or ''}\nTags: {tags or ''}")
                
                try:
                    # Generate embeddings for the entire batch
                    try:
                        embeddings = await embeddings_client.aembed_documents(texts_to_embed)
                    except Exception as e_primary:
                        logger.warning(f"Primary model failed for batch, trying fallback: {e_primary}")
                        embeddings = await fallback_client.aembed_documents(texts_to_embed)
                    
                    # Update database
                    for (row, embedding) in zip(batch_rows, embeddings):
                        product_id = row[0]
                        await cur.execute(
                            "UPDATE ai_product_shopify SET embedding = %s WHERE id = %s",
                            (embedding, product_id)
                        )
                    # Commit batch
                    await conn.commit()
                    logger.info(f"Successfully processed and saved batch {i//batch_size + 1}.")
                    
                except Exception as e:
                    logger.error(f"Failed to process batch {i//batch_size + 1}: {e}")
                    await conn.rollback()

                # Intentional pause to avoid rate limits (429 Too Many Requests)
                if i + batch_size < len(rows):
                    logger.info("Pausing for 4 seconds to respect API rate limits...")
                    await asyncio.sleep(8)

    logger.info("Ingestion completed successfully.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(ingest_embeddings())
