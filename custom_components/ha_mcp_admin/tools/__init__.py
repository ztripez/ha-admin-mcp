"""Tool registry for HA MCP Admin."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant

type ToolHandler = Callable[[HomeAssistant, dict[str, Any]], Awaitable[Any]]


@dataclass(slots=True, frozen=True)
class AdminTool:
    """A registered admin tool."""

    name: str
    description: str
    parameters: vol.Schema
    handler: ToolHandler


_TOOLS: dict[str, AdminTool] = {}
_LOADED = False


def register_tool(
    *, name: str, description: str, parameters: vol.Schema
) -> Callable[[ToolHandler], ToolHandler]:
    """Register a tool handler."""

    def decorator(func: ToolHandler) -> ToolHandler:
        if name in _TOOLS:
            raise ValueError(f"Tool already registered: {name}")
        _TOOLS[name] = AdminTool(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
        )
        return func

    return decorator


def _load_tool_modules() -> None:
    """Load all tool modules once."""
    global _LOADED

    if _LOADED:
        return

    for module_name in (
        "automations",
        "backups",
        "config_entries",
        "diagnostics",
        "discovery",
        "history",
        "mqtt",
        "scripts",
        "scenes",
        "helpers",
        "groups",
        "entities",
        "areas",
        "floors",
        "labels",
        "categories",
        "services",
        "states",
        "voice",
        "supervisor",
        "system",
        "updates",
        "zha",
        "zwave",
    ):
        import_module(f"{__name__}.{module_name}")

    _LOADED = True


def get_tool(name: str) -> AdminTool | None:
    """Return a single tool by name."""
    _load_tool_modules()
    return _TOOLS.get(name)


def get_tools() -> list[AdminTool]:
    """Return all registered tools."""
    _load_tool_modules()
    return sorted(_TOOLS.values(), key=lambda tool: tool.name)
