from src.agent.skills.base import BaseSkill
from src.agent.tools import check_order_status
from typing import Any, Dict, List
from langchain_core.messages import SystemMessage

class SupportSkill(BaseSkill):
    """
    Skill for handling order status and support inquiries.
    """

    @property
    def name(self) -> str:
        return "support_skill"

    @property
    def tools(self) -> List[Any]:
        return [check_order_status]

    async def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Enforce scope
        system_msg = SystemMessage(content="You are a Support expert. ONLY assist with order status tracking and support inquiries. Refuse all other requests.")
        state["messages"] = [system_msg] + state["messages"]
        return state
