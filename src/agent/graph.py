from typing import Callable, Union
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.runnables import Runnable
from src.agent.models import AgentState
from src.agent.llm import llm
from src.services.whatsapp_client import whatsapp_client
from src.services.telegram_client import telegram_client
import logging
from langgraph.checkpoint.postgres import PostgresSaver
from src.config import settings
from src.agent.tools import search_products, check_order_status, get_product_price, get_product_stock
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)

# Define the tools available to the agent
tools = [search_products, check_order_status, get_product_price, get_product_stock]

# Bind tools to the LLM
# This allows the LLM to know about the tools and call them.
llm_with_tools = llm.bind_tools(tools)

def _agent_node(state: AgentState) -> dict:
    """
    Agent node: Determines the next action based on the conversation history.
    It either generates a response directly or calls a tool.
    """
    system_prompt = SystemMessage(
        content="""You are a warm and helpful FastPrint Omnichannel AI Assistant.
FastPrint specializes in printing raw materials and accessories.

You have access to the following tools:
- check_stock       → Check current stock availability for a product
- get_price         → Get the latest pricing for a product
- get_order_status  → Track and retrieve the status of a customer's order [COMING SOON]
- get_product_description → Get detailed description and specs of a product [COMING SOON]

## Greeting Behavior
When a customer first messages you (or asks what you can do), ALWAYS:
1. Greet them warmly by name if available, otherwise use a friendly general greeting.
2. Briefly introduce yourself as the FastPrint AI Assistant.
3. Proactively list ALL four capabilities so the customer knows what to expect.

Example opening:
"Hi there! 👋 I'm the FastPrint AI Assistant, here to make your experience as smooth as possible.
Here's what I can help you with today:
  ✅ Check stock availability
  ✅ Get product pricing
  🔜 Track your order status (coming soon)
  🔜 Product descriptions & specs (coming soon)
Just let me know what you need — I'm happy to help!"

## Handling Tool Availability
- check_stock and get_price are fully operational — use them confidently.
- get_order_status and get_product_description are NOT yet available.
  → If a customer asks for either, respond warmly, acknowledge the request,
    and let them know that feature is coming soon. Offer to help with what IS available.

## General Behavior
- Always be warm, clear, and patient.
- If a customer's request is unclear, ask one focused clarifying question.
- Never make up stock levels, prices, order statuses, or product details — always use the tools.
- Keep responses concise but friendly. Avoid robotic or overly formal language.
"""
    )

    messages = [system_prompt] + state["messages"]

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# Instantiate ToolNode with the defined tools
tool_node = ToolNode(tools)

async def _send_response_node(state: AgentState) -> dict:
    """
    Send response node: Sends the final AI message back to the user via the appropriate platform.
    """
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

    last_message = state["messages"][-1]
    user_id = state["user_id"]
    platform = state["platform"]

    # Extract the content from the last message.
    response_content = ""
    if isinstance(last_message, AIMessage):
        response_content = _extract_text(last_message.content)
    elif isinstance(last_message, ToolMessage):
        response_content = f"I've processed your request. {_extract_text(last_message.content)}"
    elif isinstance(last_message, HumanMessage): # Should not happen, but for safety
        response_content = f"I received: {_extract_text(last_message.content)}"

    if not response_content:
        logger.warning(f"No content to send for user {user_id} on {platform}. State: {state}")
        return {}

    if platform == "whatsapp":
        await whatsapp_client.send_text_message(to=user_id, text=response_content)
        logger.info(f"Sent WhatsApp response to {user_id}: {response_content}")
    elif platform == "telegram":
        await telegram_client.send_text_message(chat_id=user_id, text=response_content)
        logger.info(f"Sent Telegram response to {user_id}: {response_content}")
    else:
        logger.error(f"Unknown platform '{platform}' for user {user_id}. Cannot send message.")
    
    return {"messages": []} # Clear messages after sending

def _should_continue(state: AgentState) -> str:
    """
    Conditional edge: Determines whether to continue to a tool call or end the graph.
    """
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "continue"
    return "end"

# Build the graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", _agent_node)
workflow.add_node("tools", tool_node) # Use the instantiated ToolNode
workflow.add_node("send_response", _send_response_node)

workflow.set_entry_point("agent")

# Add conditional edges
workflow.add_conditional_edges(
    "agent",
    _should_continue,
    {
        "continue": "tools",
        "end": "send_response"
    }
)

# After tool execution, always go back to the agent to re-evaluate
workflow.add_edge("tools", "agent")

# After sending the response, end the graph
workflow.add_edge("send_response", END)

# Configure PostgresSaver for persistence
# NOTE: Call await checkpointer.setup() at application startup
checkpointer = PostgresSaver.from_conn_string(settings.ERP_DB_URL)

# Compile the graph with message history
app_graph: Runnable = workflow.compile(checkpointer=checkpointer)
