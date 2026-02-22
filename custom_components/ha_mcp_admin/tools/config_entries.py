"""Config entry management tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data, redact_data

LIST_CONFIG_ENTRIES_SCHEMA = vol.Schema({vol.Optional("domain"): cv.string})
GET_CONFIG_ENTRY_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string})
RELOAD_CONFIG_ENTRY_SCHEMA = GET_CONFIG_ENTRY_SCHEMA
DELETE_CONFIG_ENTRY_SCHEMA = GET_CONFIG_ENTRY_SCHEMA


def _serialize_config_entry(entry: Any) -> dict[str, Any]:
    """Serialize config entry with redacted sensitive fields."""
    data = entry.as_dict()
    data["state"] = entry.state.value
    data["data"] = redact_data(data.get("data", {}))
    data["options"] = redact_data(data.get("options", {}))
    return normalize_data(data)


@register_tool(
    name="list_config_entries",
    description="List integration config entries",
    parameters=LIST_CONFIG_ENTRIES_SCHEMA,
)
async def list_config_entries(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List config entries, optionally filtered by domain."""
    requested_domain: str | None = arguments.get("domain")
    entries = hass.config_entries.async_entries(requested_domain)
    payload = [_serialize_config_entry(entry) for entry in entries]
    return {"count": len(payload), "entries": payload}


@register_tool(
    name="get_config_entry",
    description="Get one integration config entry",
    parameters=GET_CONFIG_ENTRY_SCHEMA,
)
async def get_config_entry(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get one config entry by entry_id."""
    entry_id: str = arguments["entry_id"]
    if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
        raise HomeAssistantError(f"Config entry not found: {entry_id}")

    return {"entry": _serialize_config_entry(entry)}


@register_tool(
    name="reload_config_entry",
    description="Reload one integration config entry",
    parameters=RELOAD_CONFIG_ENTRY_SCHEMA,
)
async def reload_config_entry(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Reload one config entry."""
    entry_id: str = arguments["entry_id"]
    if hass.config_entries.async_get_entry(entry_id) is None:
        raise HomeAssistantError(f"Config entry not found: {entry_id}")

    if not await hass.config_entries.async_reload(entry_id):
        raise HomeAssistantError(f"Failed to reload config entry: {entry_id}")
    return {"entry_id": entry_id, "reloaded": True}


@register_tool(
    name="delete_config_entry",
    description="Delete one integration config entry",
    parameters=DELETE_CONFIG_ENTRY_SCHEMA,
)
async def delete_config_entry(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete one config entry."""
    entry_id: str = arguments["entry_id"]
    if hass.config_entries.async_get_entry(entry_id) is None:
        raise HomeAssistantError(f"Config entry not found: {entry_id}")

    result = await hass.config_entries.async_remove(entry_id)
    return {"entry_id": entry_id, "result": normalize_data(result)}
