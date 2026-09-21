from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.ai.tools.base import BaseTool, ToolResult
from app.ai.tools.commerce_tools import (
    ProductSearchTool,
    OrderTrackingTool,
    InventoryTool,
    CouponTool,
    RefundPolicyTool,
)
from app.ai.tools.knowledge_tool import KnowledgeSearchTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register(ProductSearchTool())
        self.register(OrderTrackingTool())
        self.register(InventoryTool())
        self.register(CouponTool())
        self.register(RefundPolicyTool())
        self.register(KnowledgeSearchTool())

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tool_descriptions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    def execute_tool(
        self,
        tool_name: str,
        db: Session,
        workspace_id: UUID,
        arguments: dict[str, Any],
        is_authorized: bool = False,
    ) -> ToolResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found in registry.",
            )

        # Enforce state-changing and authorization constraints
        if tool.requires_authorization and not is_authorized:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Security violation: Tool '{tool_name}' requires explicit authorization.",
            )

        try:
            return tool.execute(db=db, workspace_id=workspace_id, **arguments)
        except Exception as e:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Exception during execution of {tool_name}: {str(e)}",
            )



# Global singleton instance
tool_registry = ToolRegistry()
