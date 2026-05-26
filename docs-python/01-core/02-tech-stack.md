# 02 — Technology Stack (Python / Omnichannel)

## Stack Overview

| Layer | Technology | Version | Role |
|-------|-----------|---------|------|
| Runtime | Python | 3.11+ | Server runtime |
| Web Framework | FastAPI | Latest | Async HTTP server, webhook routing for both platforms |
| AI Orchestration | LangGraph | Latest | Declarative stateful workflow orchestration |
| AI Wrapper | LangChain | Latest | Model bindings and tool integrations |
| Validation | Pydantic | V2 | Runtime schema validation for Meta and Telegram payloads |
| HTTP Client | httpx | Latest | Async client for Meta API, Telegram API, & ERP APIs |
| AI Model | Google Gemini | 1.5 Flash/Pro | Chat, vision, audio, function calling (Free Tier) |
| Cache / Session | Redis (redis-py) | Latest | LangGraph checkpoint persistence and rate limits |
| ERP Backend | Django ERP | Existing | Source of truth for database, models, and business logic |

---

## Python Dependencies (`requirements.txt`)

```text
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
pydantic>=2.0.0
httpx>=0.24.0
langchain>=0.1.0
langchain-google-genai>=0.0.5
langgraph>=0.0.20
python-dotenv>=1.0.0
redis>=5.0.0
python-multipart>=0.0.6
```

---

## Why Each Technology Was Chosen

### FastAPI + Raw httpx
By building custom Pydantic models for both Telegram and WhatsApp webhooks, we can normalize the inputs into a single generic `NormalizedMessage` object. We use raw `httpx` instead of bulky SDKs so that the bot remains a fast, lightweight API gateway.

### LangGraph + LangChain
Instead of orchestrating agent loops manually (which gets brittle and hard to trace), LangGraph organizes the flow as a declarative state graph. We use the LangChain Google wrapper (`langchain-google-genai`) for seamless integration with LangGraph's native tool calling and state management.

### Google Gemini API
A generous free tier that supports advanced features like Function Calling (Tools), Vision (multimodal image understanding), and Audio transcription for both Telegram voice notes and WhatsApp voice messages natively.

### Django ERP as Backend Source of Truth
We avoid recreating models and databases. The FastAPI bot acts as an omnichannel brain that fetches its knowledge from your Django ERP via HTTP APIs.

---

## Environment Variables Reference

```dotenv
# ── WhatsApp Cloud API ────────────────────────────────────
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_APP_SECRET=
WHATSAPP_WEBHOOK_VERIFY_TOKEN=
WHATSAPP_API_VERSION=v18.0

# ── Telegram Bot API ──────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_SECRET_TOKEN=

# ── Gemini API ───────────────────────────────────────────
GEMINI_API_KEY=

# ── Django ERP API Integration ───────────────────────────
ERP_BASE_URL=https://your-django-erp.com/api
ERP_API_TOKEN=

# ── Redis ────────────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379
```
