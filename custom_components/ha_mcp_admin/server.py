"""MCP server implementation for HA MCP Admin."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
from typing import Any

from mcp import types
from mcp.server import Server
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .tools import AdminTool, get_tool, get_tools
from .tools.common import normalize_data

PROMPT_NAME = "home-assistant-admin"
PROMPT_TEXT = """You are connected to Home Assistant through an admin MCP server.

Use the available tools to manage Home Assistant configuration and runtime:
- Automations, scripts, and scenes CRUD
- Helper CRUD (input_* helpers, counter, timer)
- Group CRUD
- Entity/device/area/floor/label/category registry management
- Config entry management
- Assist pipeline and Assist satellite voice setup
- Service calls and state reads

Before destructive actions (delete/remove), verify the target exists.
When editing automations/scripts/scenes, preserve required fields and IDs.
"""


def _format_tool(
    tool: AdminTool, custom_serializer: Callable[[Any], Any] | None
) -> types.Tool:
    """Convert an internal tool definition into an MCP tool."""
    schema = convert(tool.parameters, custom_serializer=custom_serializer)
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": schema.get("properties", {}),
    }
    if required := schema.get("required"):
        input_schema["required"] = required

    return types.Tool(
        name=tool.name,
        description=tool.description,
        inputSchema=input_schema,
    )


async def create_server(hass: HomeAssistant) -> Server:
    """Create a stateless MCP server for admin tools."""
    server = Server[Any]("ha-mcp-admin")

    @server.list_prompts()  # type: ignore[no-untyped-call,untyped-decorator]  # mcp SDK lacks type stubs
    async def handle_list_prompts() -> list[types.Prompt]:
        return [
            types.Prompt(
                name=PROMPT_NAME,
                description="Home Assistant admin MCP operating instructions",
            )
        ]

    @server.get_prompt()  # type: ignore[no-untyped-call,untyped-decorator]  # mcp SDK lacks type stubs
    async def handle_get_prompt(
        name: str, arguments: dict[str, str] | None
    ) -> types.GetPromptResult:
        if name != PROMPT_NAME:
            raise ValueError(f"Unknown prompt: {name}")

        return types.GetPromptResult(
            description="Home Assistant admin MCP operating instructions",
            messages=[
                types.PromptMessage(
                    role="assistant",
                    content=types.TextContent(type="text", text=PROMPT_TEXT),
                )
            ],
        )

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]  # mcp SDK lacks type stubs
    async def handle_list_tools() -> list[types.Tool]:
        return [_format_tool(tool, None) for tool in get_tools()]

    @server.call_tool()  # type: ignore[untyped-decorator]  # mcp SDK lacks type stubs
    async def handle_call_tool(
        name: str, arguments: dict
    ) -> Sequence[types.TextContent]:
        if (tool := get_tool(name)) is None:
            raise HomeAssistantError(f"Unknown tool: {name}")

        try:
            valid_arguments = tool.parameters(arguments or {})
            result = await tool.handler(hass, valid_arguments)
        except (HomeAssistantError, ValueError, vol.Invalid) as err:
            raise HomeAssistantError(f"Tool call failed: {err}") from err

        return [
            types.TextContent(
                type="text",
                text=json.dumps(normalize_data(result), ensure_ascii=False),
            )
        ]

    return server
