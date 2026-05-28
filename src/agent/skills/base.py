from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseSkill(ABC):
    """
    Base class for all Skills in the Omnichannel AI.
    A Skill encapsulates a business capability and its associated tools.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def tools(self) -> List[Any]:
        pass
    
    @abstractmethod
    async def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the skill logic.
        """
        pass
