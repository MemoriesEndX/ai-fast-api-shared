import logging
import asyncio
import time
import inspect
from typing import Dict, Any, Optional
from app.core.config import settings
from app.mcp.registry import tool_registry, MCPTool
from app.tools.auth import UserAuthContext, ToolAuthorizationService

logger = logging.getLogger("ai_service.mcp.server")


class MCPServer:
    """MCP Server Dispatcher and Execution Orchestrator."""

    def __init__(self, registry=tool_registry):
        self.registry = registry

    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        auth_context: Optional[UserAuthContext] = None,
    ) -> Dict[str, Any]:
        """Execute registered MCP tool with strict authorization, timeout, and error sanitization."""
        start_time = time.time()
        tool: Optional[MCPTool] = self.registry.get_tool(name)

        if not tool:
            logger.error(f"Tool '{name}' not found in registry.")
            return {
                "error": {
                    "code": "TOOL_NOT_FOUND",
                    "message": f"Requested tool '{name}' is not registered in MCP registry.",
                }
            }

        # Auth & Tenant Enforcement
        if tool.requires_auth:
            if not auth_context:
                logger.warning(f"Unauthenticated invocation rejected for tool '{name}'.")
                return {
                    "error": {
                        "code": "UNAUTHENTICATED",
                        "message": "Tool execution requires an authenticated user context.",
                    }
                }
            try:
                # 1. Enforce tenant isolation based on tool owner
                shared_tools = {"search_pdf_knowledge", "search_video_transcript"}
                required_app = auth_context.application if name in shared_tools else "owl"
                ToolAuthorizationService.validate_tenant_access(auth_context, required_application=required_app)

                # 2. Enforce user isolation if user_id is provided in arguments
                if "user_id" in arguments and arguments["user_id"] is not None:
                    target_user_id = int(arguments["user_id"])
                    ToolAuthorizationService.validate_user_access(auth_context, target_user_id)
            except PermissionError as pe:
                return {
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": str(pe),
                    }
                }

        # Inject auth_context into handler if requested by signature
        handler_kwargs = dict(arguments)
        sig = inspect.signature(tool.handler)
        if "auth_context" in sig.parameters:
            handler_kwargs["auth_context"] = auth_context

        # Execute Tool Handler with Timeout
        timeout = settings.TOOL_TIMEOUT
        app_label = auth_context.application if auth_context else "shared"
        from app.core.metrics import metrics_registry
        metrics_registry.inc("mcp_tool_calls_total", labels={"tool": name, "application": app_label})

        try:
            if inspect.iscoroutinefunction(tool.handler):
                result = await asyncio.wait_for(tool.handler(**handler_kwargs), timeout=timeout)
            else:
                result = tool.handler(**handler_kwargs)

            duration_sec = time.time() - start_time
            duration_ms = round(duration_sec * 1000, 2)
            metrics_registry.observe("mcp_tool_latency_seconds", duration_sec, labels={"tool": name})
            logger.info(
                f"MCP Tool '{name}' executed successfully for app={app_label} user_id={auth_context.user_id if auth_context else 'None'} in {duration_ms} ms."
            )
            return result

        except asyncio.TimeoutError:
            duration_sec = time.time() - start_time
            duration_ms = round(duration_sec * 1000, 2)
            metrics_registry.observe("mcp_tool_latency_seconds", duration_sec, labels={"tool": name})
            logger.error(f"MCP Tool '{name}' timed out after {timeout} seconds for app={app_label}.")
            return {
                "error": {
                    "code": "TOOL_TIMEOUT",
                    "message": f"Execution of tool '{name}' timed out after {timeout} seconds.",
                }
            }
        except Exception as e:
            duration_sec = time.time() - start_time
            duration_ms = round(duration_sec * 1000, 2)
            metrics_registry.observe("mcp_tool_latency_seconds", duration_sec, labels={"tool": name})
            logger.error(f"Error executing MCP tool '{name}' for app={app_label}: {e}", exc_info=True)
            # Never expose internal SQL, stack trace, or credentials
            return {
                "error": {
                    "code": "LMS_SERVICE_UNAVAILABLE",
                    "message": "Learning service tool encountered an error processing your request.",
                }
            }


# Singleton MCPServer instance
mcp_server = MCPServer()
