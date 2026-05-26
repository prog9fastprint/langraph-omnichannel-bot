# Omnichannel AI Chatbot

This project implements a scalable, production-grade AI-powered chatbot microservice designed to operate across multiple messaging platforms, specifically WhatsApp and Telegram. Built with FastAPI and leveraging LangGraph for sophisticated AI orchestration, it integrates seamlessly with an existing Django ERP system for real-time data access and Google Gemini for conversational AI capabilities.

## Project Goal

The primary objective is to deliver a robust and flexible AI chatbot that:
- Supports both WhatsApp (via Meta Cloud API) and Telegram (via Bot API).
- Utilizes a unified AI Router powered by LangGraph to ensure consistent business logic across all platforms.
- Integrates Google Gemini (1.5 Flash/Pro) for conversational AI, including vision and audio processing.
- Operates without a local database for business logic, fetching all real-time data (stock, orders, complaints) and long-term memory through API calls to an existing Django ERP.
- Employs Redis for LangGraph checkpoint state persistence and rate-limiting functionalities.
- Is containerized using Docker, allowing for straightforward deployment to a Ubuntu VPS.

## Key Technologies

- **FastAPI**: High-performance Python web framework for building the microservice and handling webhooks.
- **LangGraph**: Declarative framework for building stateful, multi-actor applications with LLMs, used for AI orchestration.
- **LangChain**: Provides the necessary model bindings and tool integrations for the LLMs.
- **Google Gemini (2.5 Flash/Pro)**: The core AI model providing chat, vision, audio processing, and function calling capabilities.
- **Pydantic**: Used for robust data validation of incoming webhooks and API responses.
- **httpx**: Asynchronous HTTP client for efficient communication with external APIs (Meta, Telegram, ERP).
- **Redis**: Employed for conversational state persistence (LangGraph checkpoints) and rate limiting.
- **Django ERP**: The external source of truth for all business logic and data, accessed via HTTP APIs.

## Non-Negotiable Architecture Rules

- **Omnichannel Abstraction**: The AI logic must not care whether the message came from Telegram or WhatsApp.
- **Unified AI Router**: All business logic is centralized in LangGraph to ensure platform-agnostic behavior.
- **No Local Database**: The chatbot is a stateless microservice for business logic. All stock, order, and customer data MUST be fetched from the Django ERP via HTTP APIs.
- **Async/Await Pattern**: Use `async def`, `await`, and `httpx.AsyncClient` for all non-blocking I/O operations.
- **Strict Validation**: Pydantic models must be used for all incoming payloads and external API responses to ensure data integrity.

## Development Roadmap (Phases)

- **Phase 1: Foundation (FastAPI & Dual Webhooks)**: Initial project setup, server initialization, HMAC/Secret Token verification for Meta/Telegram, and payload normalization.
- **Phase 2: AI Core (LangGraph & Gemini Integration)**: Configuring LLM wrappers, building the state graph workflow, and integrating Redis for persistent conversation memory.
- **Phase 3: ERP Integration**: Building secure ERP API clients and wiring LangChain tools for real-time stock and order status checks.
- **Phase 4: Advanced Features**: Implementing multimodal media downloading (images/voice) and RAG querying via the ERP knowledge base.
- **Phase 5: Infrastructure**: Final Dockerization and container orchestration for production deployment.

## Features Implemented

- **Dual-Platform Webhooks**: Securely handles incoming messages and events from both WhatsApp and Telegram.
- **Omnichannel Abstraction**: AI logic is platform-agnostic, processing messages via a normalized format.
- **AI Orchestration**: LangGraph manages conversational flow, tool usage, and state transitions.
- **Conversational Memory**: Redis checkpointer ensures persistent conversation history.
- **ERP Integration**: Tools to query ERP for real-time stock levels and order statuses.
- **Media Processing**: Ability to download and pass voice notes and images to Gemini for multimodal understanding.
- **RAG Capabilities**: Tool for retrieving knowledge from the ERP's `pgvector` knowledge base.
- **Dockerization**: Containerized application setup for simplified deployment and environment management.

## Getting Started

To run this project, you will need Docker and Docker Compose installed.

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd python-omnichannel-ai
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the project root based on the provided `.env` template. Populate it with your API keys and configuration details for WhatsApp, Telegram, Gemini, ERP, and Redis.

3. **Build and Run with Docker Compose:**
   ```bash
   docker-compose up --build -d
   ```

   This command will build the FastAPI application image, start the Redis service, and then start the FastAPI application.

4. **Access the Application:**
   The FastAPI application will be accessible at `http://localhost:8000`.
   - Health check: `http://localhost:8000/health`
   - WhatsApp Webhook: `http://localhost:8000/webhook/whatsapp`
   - Telegram Webhook: `http://localhost:8000/webhook/telegram`

   You will need to configure your WhatsApp and Telegram webhook settings to point to your deployed application's URL (e.g., via Ngrok if running locally).

## Project Structure

```
.
├── .env                  # Environment variables (ignored by Git)
├── .gitignore            # Specifies intentionally untracked files to ignore
├── Dockerfile            # Docker build instructions for the FastAPI app
├── docker-compose.yml    # Defines multi-container Docker application (FastAPI + Redis)
├── requirements.txt      # Python dependencies
├── docs-python/          # Project documentation and build plan
│   └── ...
└── src/                  # Main application source code
    ├── __init__.py
    ├── config.py         # Loads environment variables via Pydantic
    ├── main.py           # FastAPI app instance, webhook endpoints, and global exception handler
    ├── normalizer.py     # Transforms platform-specific payloads into a normalized format
    ├── schemas.py        # Pydantic models for webhook payloads and normalized messages
    ├── security.py       # Webhook verification logic (HMAC for WhatsApp, Secret Token for Telegram)
    ├── agent/            # LangGraph agent implementation
    │   ├── __init__.py
    │   ├── graph.py      # LangGraph workflow definition and Redis checkpointer integration
    │   ├── llm.py        # Google Gemini LLM configuration
    │   └── models.py     # AgentState definition for LangGraph
    │   └── tools.py      # LangChain tools for ERP interaction (stock, orders, RAG)
    └── services/         # External service clients
        ├── __init__.py
        ├── erp_client.py       # Client for secure communication with Django ERP API
        ├── media_downloader.py # Downloads media from WhatsApp and Telegram
        ├── telegram_client.py  # Client for sending messages to Telegram
        └── whatsapp_client.py  # Client for sending messages to WhatsApp
```
