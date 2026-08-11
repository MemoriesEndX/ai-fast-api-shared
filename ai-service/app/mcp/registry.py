import logging
import inspect
from typing import Dict, Any, Callable, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_service.mcp.registry")


class MCPTool(BaseModel):
    """MCP Tool Metadata & Handler Definition."""
    name: str = Field(..., description="Unique tool identifier name")
    description: str = Field(..., description="Concise tool description for LLM selection")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema of required inputs")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema of returned output")
    handler: Callable = Field(..., description="Executable tool handler function")
    requires_auth: bool = Field(default=True, description="Whether tool requires authenticated user context")


class ToolRegistry:
    """Central MCP Tool Registry holding all registered tools."""

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        requires_auth: bool = True,
    ):
        """Decorator to register a tool in the MCP registry."""
        def decorator(func: Callable):
            tool = MCPTool(
                name=name,
                description=description.strip(),
                input_schema=input_schema or {},
                output_schema=output_schema or {},
                handler=func,
                requires_auth=requires_auth,
            )
            if name in self._tools:
                logger.warning(f"Overwriting existing tool registration for '{name}'.")
            self._tools[name] = tool
            logger.info(f"Registered MCP tool: '{name}'")
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[MCPTool]:
        """Return list of all registered tools."""
        return list(self._tools.values())

    def get_tool_declarations_for_llm(self) -> List[Dict[str, Any]]:
        """Format registered tools for Qwen system prompt tool declaration."""
        declarations = []
        for tool in self._tools.values():
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            })
        return declarations


# Global Singleton Tool Registry
tool_registry = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    requires_auth: bool = True,
):
    """Global decorator shortcut for tool registration."""
    return tool_registry.register(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema=output_schema,
        requires_auth=requires_auth,
    )
