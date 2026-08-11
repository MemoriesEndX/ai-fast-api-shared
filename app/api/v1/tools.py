import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from app.mcp.registry import tool_registry
from app.core.security import verify_api_key

logger = logging.getLogger("ai_service.api.tools")
router = APIRouter()


@router.get("/tools", summary="List registered MCP LMS & RAG tools (Development/Admin debug)")
async def list_mcp_tools(client_app: str = Depends(verify_api_key)) -> Dict[str, Any]:
    """List all registered MCP tools with input schemas and authorization requirements."""
    tools = tool_registry.list_tools()
    tool_list = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
            "output_schema": t.output_schema,
            "requires_auth": t.requires_auth,
        }
        for t in tools
    ]
    return {
        "status": "success",
        "total_tools": len(tool_list),
        "tools": tool_list,
    }
