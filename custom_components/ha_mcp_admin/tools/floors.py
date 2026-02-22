"""Floor registry tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, floor_registry as fr

from . import register_tool
from .common import normalize_data, pick_kwargs

LIST_FLOORS_SCHEMA = vol.Schema({})
CREATE_FLOOR_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("aliases"): [cv.string],
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("level"): vol.Any(None, vol.Coerce(int)),
    }
)
UPDATE_FLOOR_SCHEMA = vol.Schema(
    {
        vol.Required("floor_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("aliases"): [cv.string],
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("level"): vol.Any(None, vol.Coerce(int)),
    }
)
DELETE_FLOOR_SCHEMA = vol.Schema({vol.Required("floor_id"): cv.string})


def _serialize_floor(entry: fr.FloorEntry) -> dict[str, Any]:
    """Serialize floor entry."""
    return normalize_data(
        {
            "floor_id": entry.floor_id,
            "name": entry.name,
            "aliases": sorted(entry.aliases),
            "icon": entry.icon,
            "level": entry.level,
            "created_at": entry.created_at,
            "modified_at": entry.modified_at,
        }
    )


@register_tool(
    name="list_floors",
    description="List all floor registry entries",
    parameters=LIST_FLOORS_SCHEMA,
)
async def list_floors(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """List all floors."""
    del arguments
    registry = fr.async_get(hass)
    floors = [_serialize_floor(entry) for entry in registry.async_list_floors()]
    return {"count": len(floors), "floors": floors}


@register_tool(
    name="create_floor",
    description="Create a floor registry entry",
    parameters=CREATE_FLOOR_SCHEMA,
)
async def create_floor(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create one floor."""
    registry = fr.async_get(hass)
    try:
        entry = registry.async_create(
            arguments["name"],
            aliases=set(arguments.get("aliases", [])),
            icon=arguments.get("icon"),
            level=arguments.get("level"),
        )
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"floor": _serialize_floor(entry)}


@register_tool(
    name="update_floor",
    description="Update a floor registry entry",
    parameters=UPDATE_FLOOR_SCHEMA,
)
async def update_floor(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update one floor."""
    floor_id: str = arguments["floor_id"]
    registry = fr.async_get(hass)
    if registry.async_get_floor(floor_id) is None:
        raise HomeAssistantError(f"Floor not found: {floor_id}")

    kwargs = pick_kwargs(arguments, ("name", "icon", "level"), ("aliases",))

    try:
        entry = registry.async_update(floor_id, **kwargs)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"floor": _serialize_floor(entry)}


@register_tool(
    name="delete_floor",
    description="Delete a floor registry entry",
    parameters=DELETE_FLOOR_SCHEMA,
)
async def delete_floor(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete one floor."""
    floor_id: str = arguments["floor_id"]
    registry = fr.async_get(hass)
    if registry.async_get_floor(floor_id) is None:
        raise HomeAssistantError(f"Floor not found: {floor_id}")

    registry.async_delete(floor_id)
    return {"deleted": floor_id}
