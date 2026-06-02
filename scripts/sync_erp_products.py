import asyncio
import os
import sys
import logging
from typing import List, Dict

# Add the project root to the Python path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.services.erp_client import erp_client
import psycopg
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

class GeneratedProductContent(BaseModel):
    description: str = Field(description="A professional, rich e-commerce product description.")
    tags: str = Field(description="Comma separated SEO tags relevant to the product.")
    vendor: str = Field(description="The guessed vendor or brand name (e.g., Epson, Canon, FastPrint). Use 'FastPrint' if unknown.")

async def sync_new_products():
    logger.info("Starting AI Auto-Generation Pipeline...")
    
    # 1. Fetch all products from ERP
    try:
        logger.info("Fetching products from ERP...")
        response = await erp_client.get("inventory/api/ai/products/")
        
        if response.get("status") != "success":
            logger.error(f"ERP returned error: {response}")
            return

        erp_products = response.get("data", [])

        logger.info(f"Received {len(erp_products)} products from ERP")
    except Exception as e:
        logger.error(f"Failed to fetch ERP products: {e}")
        return

    # Extract ERP SKUs mapping
    erp_mapping = {}
    for p in erp_products:
        sku = p.get("sku") or p.get("variant_sku")
        if sku:
            erp_mapping[str(sku)] = p

    logger.info(f"Found {len(erp_mapping)} products with SKUs in ERP.")

    # 2. Fetch existing SKUs from Postgres
    db_url = settings.VECTOR_DB_URL or settings.ERP_DB_URL
    if not db_url:
        logger.error("No database URL configured (VECTOR_DB_URL or ERP_DB_URL).")
        return

    existing_skus = set()
    try:
        async with await psycopg.AsyncConnection.connect(db_url) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT variant_sku FROM ai_product_shopify WHERE variant_sku IS NOT NULL")
                rows = await cur.fetchall()
                for row in rows:
                    existing_skus.add(str(row[0]))
    except Exception as e:
        logger.error(f"Failed to connect to Postgres or query ai_product_shopify: {e}")
        return

    logger.info(f"Found {len(existing_skus)} existing products in Vector DB.")

    # 3. Find missing products
    missing_skus = [sku for sku in erp_mapping.keys() if sku not in existing_skus]
    logger.info(f"Found {len(missing_skus)} new products missing from Vector DB.")

    if not missing_skus:
        logger.info("Everything is up-to-date! Exiting.")
        return

    # 4. Initialize AI Clients
    api_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
    if not api_key:
         logger.error("GEMINI_API_KEY is not configured.")
         return

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0.7)
    structured_llm = llm.with_structured_output(GeneratedProductContent)
    embeddings_client = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2", google_api_key=api_key, output_dimensionality=1536)

    # 5. Process and Insert Missing Products
    async with await psycopg.AsyncConnection.connect(db_url) as conn:
        for sku in missing_skus:
            erp_data = erp_mapping[sku]
            name = erp_data.get("name") or erp_data.get("title") or f"Product {sku}"
            handle = name.lower().replace(" ", "-")
            price = erp_data.get("price") or erp_data.get("variant_price") or 0.0

            logger.info(f"Processing new product: [{sku}] {name}")
            
            try:
                # Generate rich text via Gemini
                prompt = f"You are an expert e-commerce copywriter for FastPrint.\nWrite a rich, professional product description for a printing/office supply product named '{name}' (SKU: {sku}).\nAlso provide a list of SEO tags, and guess the manufacturer/vendor brand based on the name."
                
                content = await structured_llm.ainvoke([HumanMessage(content=prompt)])
                
                # Create the embedding vector for the generated description
                vector = await embeddings_client.aembed_query(content.description)

                # Insert into Postgres
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO ai_product_shopify 
                        (handle, title, body, vendor, tags, variant_sku, variant_price, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                        """,
                        (handle, name, content.description, content.vendor, content.tags, sku, price, vector)
                    )
                await conn.commit()
                logger.info(f"Successfully inserted [{sku}] into Vector DB.")
            except Exception as e:
                logger.error(f"Failed to process or insert product {sku}: {e}")
                await conn.rollback()

    logger.info("Sync complete!")

if __name__ == "__main__":
    asyncio.run(sync_new_products())
