import os
import asyncio
import logging
from dotenv import load_dotenv
import psycopg
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ingest_embeddings")

load_dotenv()

DB_URL = os.getenv("VECTOR_DB_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ── Free-tier friendly settings ──────────────────────────────────────────────
BATCH_SIZE = 5           # Small batches to avoid quota bursts
BATCH_DELAY_SEC = 12     # Pause between every batch
MAX_RETRIES = 4          # How many times to retry a rate-limited batch
RETRY_BASE_DELAY = 20    # Base seconds for exponential backoff (doubles each attempt)
# ─────────────────────────────────────────────────────────────────────────────


def build_text(row: tuple) -> str:
    """Combine product fields into a single embeddable string."""
    _, title, body, tags = row
    return f"Title: {title or ''}\nDescription: {body or ''}\nTags: {tags or ''}"


async def embed_with_retry(
    primary: GoogleGenerativeAIEmbeddings,
    fallback: GoogleGenerativeAIEmbeddings,
    texts: list[str],
) -> list:
    """
    Try the primary model first.
    - On rate-limit (429 / quota) → exponential backoff, then retry primary.
    - On other errors            → immediately try fallback model.
    - If both fail               → raise so the caller can rollback + skip.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await primary.aembed_documents(texts)

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            is_rate_limit = any(kw in err_str for kw in ("429", "quota", "rate limit", "resource_exhausted"))

            if is_rate_limit:
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))   # 20 → 40 → 80 → 160 s
                logger.warning(
                    f"Rate limit hit (attempt {attempt}/{MAX_RETRIES}). "
                    f"Backing off for {wait}s …"
                )
                await asyncio.sleep(wait)
                # Retry primary after waiting
                continue

            # Non-rate-limit error → try fallback once
            logger.warning(f"Primary model error (non-rate-limit): {e}. Trying fallback …")
            try:
                return await fallback.aembed_documents(texts)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                raise RuntimeError(f"Both models failed. Primary: {e} | Fallback: {e2}") from e2

    raise RuntimeError(
        f"Primary model still rate-limited after {MAX_RETRIES} retries. "
        f"Last error: {last_error}"
    )


async def ingest_embeddings():
    # ── Pre-flight checks ────────────────────────────────────────────────────
    if not DB_URL:
        logger.error("VECTOR_DB_URL is not set in your environment.")
        return
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set in your environment.")
        return

    # ── Initialise embedding clients ─────────────────────────────────────────
    logger.info("Initialising embedding clients …")
    primary_client = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2",
        google_api_key=GEMINI_API_KEY,
        output_dimensionality=1536,
    )
    fallback_client = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=GEMINI_API_KEY,
        output_dimensionality=1536,
    )

    # ── Connect and fetch only NULL-embedding rows ───────────────────────────
    logger.info("Connecting to database …")
    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor() as cur:

            await cur.execute(
                """
                SELECT id, title, body, tags
                FROM   ai_product_shopify
                WHERE  embedding IS NULL          -- skip already-embedded products
                ORDER  BY id                      -- stable ordering for resumability
                """
            )
            rows = await cur.fetchall()
            total = len(rows)

            if total == 0:
                logger.info("All products already have embeddings. Nothing to do. ✅")
                return

            logger.info(f"Found {total} product(s) without embeddings.")

            # ── Batch loop ───────────────────────────────────────────────────
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
            succeeded = 0
            failed_ids: list[int] = []

            for batch_num, offset in enumerate(range(0, total, BATCH_SIZE), start=1):
                batch = rows[offset : offset + BATCH_SIZE]
                batch_ids = [r[0] for r in batch]
                texts = [build_text(r) for r in batch]

                logger.info(
                    f"Batch {batch_num}/{total_batches} "
                    f"— IDs {batch_ids[0]}…{batch_ids[-1]} "
                    f"({len(batch)} item(s))"
                )

                try:
                    embeddings = await embed_with_retry(primary_client, fallback_client, texts)

                    # Persist embeddings for this batch
                    for row, embedding in zip(batch, embeddings):
                        await cur.execute(
                            "UPDATE ai_product_shopify SET embedding = %s WHERE id = %s",
                            (embedding, row[0]),
                        )
                    await conn.commit()
                    succeeded += len(batch)
                    logger.info(
                        f"Batch {batch_num} saved ✅ "
                        f"({succeeded}/{total} total done)"
                    )

                except Exception as e:
                    logger.error(f"Batch {batch_num} failed permanently — rolling back: {e}")
                    await conn.rollback()
                    failed_ids.extend(batch_ids)

                # Pause before the next batch (skip pause after the last batch)
                if offset + BATCH_SIZE < total:
                    logger.info(f"Waiting {BATCH_DELAY_SEC}s before next batch …")
                    await asyncio.sleep(BATCH_DELAY_SEC)

            # ── Summary ──────────────────────────────────────────────────────
            logger.info("=" * 60)
            logger.info(f"Ingestion complete.")
            logger.info(f"  ✅ Succeeded : {succeeded}")
            logger.info(f"  ❌ Failed    : {len(failed_ids)}")
            if failed_ids:
                logger.info(f"  Failed IDs  : {failed_ids}")
            logger.info("=" * 60)


if __name__ == "__main__":
    if os.name == "nt":
        # Required on Windows to avoid "Event loop is closed" errors
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(ingest_embeddings())