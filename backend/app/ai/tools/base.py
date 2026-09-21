from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


class ToolResult(BaseModel):
    success: bool = True
    tool_name: str
    data: Any = None
    error: str | None = None

    def to_readable_text(self) -> str:
        if not self.success:
            return f"Error executing {self.tool_name}: {self.error}"
        if self.data is None:
            return f"No results found for {self.tool_name}."
        if isinstance(self.data, (list, dict)):
            import json
            return json.dumps(self.data, indent=2)
        return str(self.data)


class BaseTool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]
    is_state_changing: bool = False
    requires_authorization: bool = False

    @abstractmethod
    def execute(self, db: Session, workspace_id: UUID, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments within the specified workspace boundary."""
        pass
