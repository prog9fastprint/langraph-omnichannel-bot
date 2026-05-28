from typing import Callable, Union, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.runnables import Runnable
from src.agent.models import AgentState
from src.agent.llm import llm
from src.services.whatsapp_client import whatsapp_client
from src.services.telegram_client import telegram_client
import logging
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from src.config import settings
from langgraph.prebuilt import ToolNode
from src.agent.skills import SalesSkill, SupportSkill
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Initialize Skills
sales_skill = SalesSkill()
support_skill = SupportSkill()

# Define the tools available to the agent (aggregated from skills)
tools = sales_skill.tools + support_skill.tools

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools)

# --- Pydantic models for structured routing ---

class RouteDestination(str, Enum):
    SALES = "sales"
    SUPPORT = "support"
    GREETING = "greeting"
    REFUSE = "refuse"

class SupervisorRouting(BaseModel):
    destination: RouteDestination = Field(description="The next node to route the conversation to.")
    reasoning: str = Field(description="Brief explanation for the routing decision.")

# --- Graph Nodes ---

def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor node: Routes the request to the appropriate skill.
    Returns internal routing message (not user-facing).
    """
    system_prompt = SystemMessage(
        content="""You are the FastPrint Omnichannel AI Supervisor.
Your role is to route customer requests to the correct expert skill:
- sales: product search, stock checks, pricing.
- support: order status tracking.
- greeting: polite greetings (detect language and respond in same).

STRICT CONSTRAINTS:
1. ONLY respond to Sales, Support, or Greeting requests.
2. DO NOT perform coding, general knowledge, or creative writing tasks.
3. If a request is out-of-scope, set destination to 'refuse'.
"""
    )
    # Pass full conversation history, but filter out internal routing tags
    filtered_messages = [m for m in state["messages"] if not (isinstance(m, AIMessage) and str(m.content).startswith("__ROUTE__:"))]
    messages = [system_prompt] + filtered_messages

    structured_llm = llm_with_tools.with_structured_output(SupervisorRouting)
    routing = structured_llm.invoke(messages)

    logger.info(f"Supervisor routed to: {routing.destination} — {routing.reasoning}")

    # Store routing as internal metadata, not user-facing
    return {"messages": [AIMessage(content=f"__ROUTE__:{routing.destination.value}")]}


async def sales_agent_node(state: AgentState) -> dict:
    """Sales agent: calls LLM with tools to handle sales queries."""
    system_prompt = SystemMessage(
        content="""You are a Sales expert for FastPrint, specializing in printing raw materials and accessories.
You have access to tools: search_products, get_product_price, get_product_stock.
Use these tools to help the customer. Be warm, concise, and helpful.
Always respond in the same language the customer used."""
    )
    # Filter out internal routing messages
    user_messages = [m for m in state["messages"] if not (isinstance(m, AIMessage) and m.content.startswith("__ROUTE__:"))]
    messages = [system_prompt] + user_messages

    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def support_agent_node(state: AgentState) -> dict:
    """Support agent: calls LLM with tools to handle support queries."""
    system_prompt = SystemMessage(
        content="""You are a Support expert for FastPrint.
You have access to tools: check_order_status.
Help customers track their orders. Be warm and concise.
Always respond in the same language the customer used."""
    )
    user_messages = [m for m in state["messages"] if not (isinstance(m, AIMessage) and m.content.startswith("__ROUTE__:"))]
    messages = [system_prompt] + user_messages

    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def greeting_node(state: AgentState) -> dict:
    """Greeting node: LLM generates polite greeting in detected language."""
    system_prompt = SystemMessage(
        content="""You are a warm and helpful FastPrint AI Assistant.
Respond to the user's greeting in the same language they used.
Briefly introduce yourself and list what you can help with:
  ✅ Search products
  ✅ Check stock availability
  ✅ Get product pricing
  🔜 Track order status (coming soon)
Keep it friendly and concise."""
    )
    filtered_messages = [m for m in state["messages"] if not (isinstance(m, AIMessage) and str(m.content).startswith("__ROUTE__:"))]
    messages = [system_prompt] + filtered_messages
    response = await llm.ainvoke(messages)
    return {"messages": [AIMessage(content=response.content)]}


async def refusal_node(state: AgentState) -> dict:
    """Refusal node: politely declines out-of-scope requests."""
    return {"messages": [AIMessage(content="Mohon maaf, saya hanya dapat membantu untuk pencarian produk, pengecekan stok, harga, dan status pesanan. Ada yang bisa saya bantu terkait hal tersebut?")]}


# Instantiate ToolNode
tool_node = ToolNode(tools)


async def _send_response_node(state: AgentState) -> dict:
    """Send the final AI response to user via appropriate platform."""
    import json

    def _extract_text(content) -> str:
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    return " ".join([p.get("text", "") for p in parsed if isinstance(p, dict) and p.get("type") == "text"])
            except Exception:
                pass
            return content
        elif isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    texts.append(part["text"])
                elif isinstance(part, str):
                    texts.append(part)
            return " ".join(texts)
        return str(content)

    # Find the last non-routing AI message (skip both new __ROUTE__: and old "Routing to:" formats)
    last_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage):
            if msg.content.startswith("__ROUTE__:") or msg.content.startswith("Routing to:"):
                continue
            last_message = msg
            break
        if isinstance(msg, ToolMessage):
            last_message = msg
            break

    if last_message is None:
        return {}

    user_id = state["user_id"]
    platform = state["platform"]

    response_content = ""
    if isinstance(last_message, AIMessage):
        response_content = _extract_text(last_message.content)
    elif isinstance(last_message, ToolMessage):
        response_content = f"I've processed your request. {_extract_text(last_message.content)}"

    if not response_content:
        return {}

    if platform == "whatsapp":
        await whatsapp_client.send_text_message(to=user_id, text=response_content)
    elif platform == "telegram":
        await telegram_client.send_text_message(chat_id=user_id, text=response_content)

    return {"messages": []}


# --- Conditional edges ---

def _route_supervisor(state: AgentState) -> Literal["sales", "support", "greeting", "refusal"]:
    """Route based on supervisor's internal routing tag."""
    last_msg = state["messages"][-1]
    content = last_msg.content if isinstance(last_msg, AIMessage) else ""
    if "__ROUTE__:sales" in content:
        return "sales"
    if "__ROUTE__:support" in content:
        return "support"
    if "__ROUTE__:greeting" in content:
        return "greeting"
    return "refusal"


def _should_continue_after_agent(state: AgentState) -> Literal["tools", "send_response"]:
    """After sales/support agent: if LLM requested tool calls, go to tools. Otherwise send response."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "send_response"


def _should_continue_after_tools(state: AgentState) -> Literal["sales_agent", "support_agent"]:
    """After tools execute, route back to the agent that invoked them.
    We check for the routing tag to determine which agent to return to."""
    for msg in state["messages"]:
        if isinstance(msg, AIMessage) and msg.content.startswith("__ROUTE__:"):
            if "support" in msg.content:
                return "support_agent"
    return "sales_agent"


# --- Build the graph ---
workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("sales_agent", sales_agent_node)
workflow.add_node("support_agent", support_agent_node)
workflow.add_node("greeting", greeting_node)
workflow.add_node("refusal", refusal_node)
workflow.add_node("tools", tool_node)
workflow.add_node("send_response", _send_response_node)

workflow.set_entry_point("supervisor")

# Supervisor → skill routing
workflow.add_conditional_edges(
    "supervisor",
    _route_supervisor,
    {
        "sales": "sales_agent",
        "support": "support_agent",
        "greeting": "greeting",
        "refusal": "refusal"
    }
)

# Sales/Support agent → tools or send_response
workflow.add_conditional_edges(
    "sales_agent",
    _should_continue_after_agent,
    {"tools": "tools", "send_response": "send_response"}
)
workflow.add_conditional_edges(
    "support_agent",
    _should_continue_after_agent,
    {"tools": "tools", "send_response": "send_response"}
)

# Tools → back to the calling agent
workflow.add_conditional_edges(
    "tools",
    _should_continue_after_tools,
    {"sales_agent": "sales_agent", "support_agent": "support_agent"}
)

# Terminal nodes → send_response → END
workflow.add_edge("greeting", "send_response")
workflow.add_edge("refusal", "send_response")
workflow.add_edge("send_response", END)

# Configure PostgresSaver for persistence
pool = None

async def init_graph():
    global pool
    if pool is None:
        pool = AsyncConnectionPool(
            conninfo=settings.ERP_DB_URL,
            max_size=20,
            open=True,
            kwargs={"autocommit": True}
        )
    checkpointer = AsyncPostgresSaver(conn=pool)
    app_graph: Runnable = workflow.compile(checkpointer=checkpointer)
    return checkpointer, app_graph
