
from src.agent.skills.base import BaseSkill
from src.agent.tools import search_products, get_product_price, get_product_stock
from typing import Any, Dict, List
from langchain_core.messages import SystemMessage

class SalesSkill(BaseSkill):
    """
    Skill for handling product search, stock checks, and pricing.
    """

    @property
    def name(self) -> str:
        return "sales_skill"

    @property
    def tools(self) -> List[Any]:
        return [search_products, get_product_price, get_product_stock]

    async def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Enforce scope
        system_msg = SystemMessage(content="You are a Sales expert. ONLY assist with product search, stock checks, and pricing. Refuse all other requests.")
        state["messages"] = [system_msg] + state["messages"]
        return state
