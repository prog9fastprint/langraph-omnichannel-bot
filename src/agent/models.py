from typing import TypedDict, Literal, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Represents the state of our agent in LangGraph.
    - messages: List of messages in the conversation.
    - platform: The platform the message originated from (whatsapp, telegram).
    - user_id: The unique identifier for the user on that platform.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    platform: Literal["whatsapp", "telegram"]
    user_id: str
