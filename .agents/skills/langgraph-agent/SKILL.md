---
name: langgraph-agent
description: Handles core AI orchestration logic, LangGraph graph configuration, state management, state checkpointers (Redis/Postgres), and OpenRouter/Gemini model integrations.
---

# LangGraph Agent Skill

You are a specialized subagent for designing, modifying, and debugging the core AI logic using LangChain and LangGraph in this repository.

## Project Structure & Architecture
- **State Definitions**: Located in `src/agent/models.py`. Standardize schemas, agent state shapes, and type annotations here.
- **Graph Compilation**: Configured in `src/agent/graph.py`. It initializes the nodes, edges, conditional routing, and sets up state memory.
- **State Persistence**: The FastAPI application uses Postgres or Redis checkpointers initialized during startup (`src/main.py`).

## Guidelines
1. **Surgical Graph Changes**: When adding or updating nodes and edges:
   - Ensure `AgentState` in `src/agent/models.py` matches the keys returned by your new nodes.
   - Update `init_graph()` in `src/agent/graph.py` to correctly route messages.
   - Keep prompt templates descriptive and modular, utilizing `src/config.py` for API settings.
2. **Model Handlers**:
   - Primary: OpenRouter model (default: `settings.OPENROUTER_PRIMARY_MODEL`).
   - Fallback: Google Gemini (`langchain-google-genai` models) or free models specified in `settings.OPENROUTER_FALLBACK_MODELS`.
   - Always implement try-except blocks for API requests to fallback gracefully.
3. **Async Standard**: All nodes, state checkpointer interactions, and API calls must be fully async (`async/await`).
