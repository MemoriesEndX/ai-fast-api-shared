import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.mcp.registry import tool_registry

logger = logging.getLogger("ai_service.mcp.client")


class MCPClient:
    """MCP Client helper for formatting LLM prompts and parsing tool call decisions."""

    @staticmethod
    def build_system_prompt_with_tools(base_system_prompt: str) -> str:
        """Inject concise MCP tool declarations into LLM system prompt."""
        tools = tool_registry.get_tool_declarations_for_llm()
        if not tools:
            return base_system_prompt

        tools_json = json.dumps(tools, indent=2)
        prompt_addition = f"""

You have access to the following LMS tools to answer user requests accurately:

{tools_json}

INSTRUCTIONS FOR TOOL USAGE:
- If you need information from LMS tools (e.g. profile, progress, recommendations, PDF rules, video transcript), output ONLY a JSON object in this format:
```json
{{
  "tool": "<tool_name>",
  "arguments": {{ ... }}
}}
```
- Do NOT output extra conversational text when invoking a tool.
- If you have sufficient information or no tool is needed, respond directly to the user in clean natural language.
- NEVER invent user data, recommendations, or timestamps. Rely strictly on tool outputs.
"""
        return base_system_prompt.strip() + "\n" + prompt_addition.strip()

    @staticmethod
    def parse_tool_call(llm_output: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Extract tool call name and arguments from LLM output if present."""
        if not llm_output:
            return None

        # 1. Search for markdown json block
        json_match = re.search(r"```(?:json)?\s*(\{\s*\"tool\".*?\})\s*```", llm_output, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "tool" in data and isinstance(data["tool"], str):
                    return data["tool"], data.get("arguments", {})
            except Exception:
                pass

        # 2. Search for direct JSON string containing "tool" and "arguments"
        direct_match = re.search(r"(\{\s*\"tool\"\s*:\s*\"[^\"]+\".*?\})", llm_output, re.DOTALL)
        if direct_match:
            try:
                data = json.loads(direct_match.group(1))
                if "tool" in data and isinstance(data["tool"], str):
                    return data["tool"], data.get("arguments", {})
            except Exception:
                pass

        return None
