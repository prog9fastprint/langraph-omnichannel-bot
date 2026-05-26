# 05 — Feature Specifications (Omnichannel & Django ERP)

## 1. Memory System (LangGraph Checkpointing)

- **Storage**: Redis (using `AsyncRedisSaver`)
- **TTL**: Configured on Redis key eviction
- **Flow**: The thread ID is mapped as `thread_id = f"{platform}:{user_id}"` (e.g., `whatsapp:+62812...` or `telegram:123456`). LangGraph automatically retrieves the full message history from the Redis checkpointer for this thread ID at the start of a run, and persists the updated graph state after execution completes.

---

## 2. Function / Tool Calling (LangGraph ToolNode)

We define Python functions as tools using LangChain's `@tool` decorator and map them to the Gemini model using LangGraph's native `ToolNode`. The LLM does not need to know which platform the user is on.

### Definition and Execution
```python
from langchain_core.tools import tool

@tool
async def check_stock(product_name: str) -> dict:
    """Check the real-time stock levels of a product in the ERP."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ERP_BASE_URL}/stock",
            params={"name": product_name},
            headers={"Authorization": f"Bearer {ERP_API_TOKEN}"}
        )
        return response.json()
```

Tools are compiled into a `ToolNode`:
```python
from langgraph.prebuilt import ToolNode
tools = [check_stock, place_order, search_knowledge_base]
tool_node = ToolNode(tools)
```

---

## 4. Voice Note and Image Support (Omnichannel)

Gemini 1.5 Flash natively understands audio bytes (`.ogg`, `.mp3`) and image bytes (`.jpeg`, `.png`). Our bot just needs to download the media from the respective platform before passing it to Gemini.

### Telegram Media Flow
1. Receive Telegram Update containing a `voice` or `photo` payload.
2. Get the file path via `https://api.telegram.org/bot<TOKEN>/getFile?file_id=...`.
3. Download media using `httpx`.
4. Pass binary to Gemini.

### WhatsApp Media Flow
1. Receive Meta payload with an `audio` or `image` ID.
2. Request the URL via `https://graph.facebook.com/v18.0/<MEDIA_ID>`.
3. Download the binary data using `httpx` and the Meta Bearer token.
4. Pass binary to Gemini.

---

## 5. RAG Knowledge Base (pgvector)

You store your document embeddings inside a Django model.
1. User asks a question on WA/TG.
2. FastAPI sends `POST /api/rag/query/` to the ERP.
3. Django returns chunks from `pgvector`.
4. FastAPI provides those chunks to Gemini as context.
