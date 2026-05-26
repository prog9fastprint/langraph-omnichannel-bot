# 01 — System Architecture (Omnichannel FastAPI)

## High-Level Architecture Diagram

```
WhatsApp User                      Telegram User
      │                                  │
      ▼                                  ▼
 Meta Servers                      Telegram Servers
      │                                  │
      ▼ (POST /webhook/whatsapp)         ▼ (POST /webhook/telegram)
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Webhook Server               │
│                                                         │
│  ┌────────────────────┐          ┌───────────────────┐  │
│  │ WhatsApp Validator │          │ Telegram Validator│  │
│  │ (HMAC Verify +     │          │ (Secret Token +   │  │
│  │  Pydantic)         │          │  Pydantic)        │  │
│  └─────────┬──────────┘          └─────────┬─────────┘  │
│            │                               │            │
│            ▼                               ▼            │
│  ┌───────────────────────────────────────────────────┐  │
│  │                  Payload Normalizer               │  │
│  │     Converts payloads into generic NormalizedMsg  │  │
│  └─────────────────────────┬─────────────────────────┘  │
└────────────────────────────┼────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│              LangGraph Agent (AI Layer)                 │
│                                                         │
│  START ──▶ AI Node ──▶ Conditional Edge ──▶ Tool Node   │
│              │             │                   │        │
│              │             ├─ (Complete)       │        │
│              │             ▼                   │        │
│              │       Send Node ──▶ END         │        │
│              ▲                                 │        │
│              └──────── Loop if needed ─────────┘        │
│                                                         │
│  State: {messages, platform, user_id}                   │
└────────┬───────────────────┬───────────────────┬────────┘
         │                   │                   │
         ▼                   ▼                   ▼
    Redis Saver        Google Gemini       Django ERP APIs
 (Thread Checkpoints)
```

---

## Component Responsibilities

### Webhook Server (FastAPI)
- Exposes separate webhook endpoints for WhatsApp and Telegram.
- Applies the correct security validation per platform.
- Normalizes incoming payloads and hands off execution to the LangGraph runner asynchronously (via `BackgroundTasks` to avoid Meta/Telegram timeouts).

### Payload Normalizer
- Extracts text, media IDs, and sender ID from the raw payloads.
- Converts them into a generic format:
  ```python
  class NormalizedMessage:
      platform: Literal["whatsapp", "telegram"]
      user_id: str  # Phone number or Telegram chat ID
      type: Literal["text", "audio", "image"]
      text: Optional[str]
      media_id: Optional[str]
  ```

### LangGraph Agent
- **Platform Agnostic**: The AI logic only operates on the `AgentState`. It doesn't care where the message came from.
- **State Management**: Defines the schema (`AgentState`) containing message history and session metadata. Persists the conversation thread natively using an `AsyncRedisSaver` checkpointer.
- **Routing Decisions**: Uses conditional edges to decide whether to call a tool (e.g. Django ERP API) or transition to the output stage.

### Platform Clients (`src/services/whatsapp.py` & `src/services/telegram.py`)
- Provide uniform functions to send messages back.
- Example: `send_message(platform, user_id, text)` which internally branches to the correct `httpx` POST request based on the platform. Can be called directly from the LangGraph "Send Node".

### Django ERP APIs (External Dependency)
- The source of truth for all tools (checking stock, orders, RAG pgvector queries).
