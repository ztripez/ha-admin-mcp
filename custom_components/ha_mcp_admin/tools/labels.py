"""Label registry tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, label_registry as lr

from . import register_tool
from .common import normalize_data, pick_kwargs

LIST_LABELS_SCHEMA = vol.Schema({})
CREATE_LABEL_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("color"): vol.Any(None, cv.string),
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("description"): vol.Any(None, cv.string),
    }
)
UPDATE_LABEL_SCHEMA = vol.Schema(
    {
        vol.Required("label_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("color"): vol.Any(None, cv.string),
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("description"): vol.Any(None, cv.string),
    }
)
DELETE_LABEL_SCHEMA = vol.Schema({vol.Required("label_id"): cv.string})


def _serialize_label(entry: lr.LabelEntry) -> dict[str, Any]:
    """Serialize label entry."""
    return normalize_data(
        {
            "label_id": entry.label_id,
            "name": entry.name,
            "color": entry.color,
            "icon": entry.icon,
            "description": entry.description,
            "created_at": entry.created_at,
            "modified_at": entry.modified_at,
        }
    )


@register_tool(
    name="list_labels",
    description="List all label registry entries",
    parameters=LIST_LABELS_SCHEMA,
)
async def list_labels(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """List all labels."""
    del arguments
    registry = lr.async_get(hass)
    labels = [_serialize_label(entry) for entry in registry.async_list_labels()]
    return {"count": len(labels), "labels": labels}


@register_tool(
    name="create_label",
    description="Create a label registry entry",
    parameters=CREATE_LABEL_SCHEMA,
)
async def create_label(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create one label."""
    registry = lr.async_get(hass)
    try:
        entry = registry.async_create(
            arguments["name"],
            color=arguments.get("color"),
            icon=arguments.get("icon"),
            description=arguments.get("description"),
        )
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"label": _serialize_label(entry)}


@register_tool(
    name="update_label",
    description="Update a label registry entry",
    parameters=UPDATE_LABEL_SCHEMA,
)
async def update_label(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update one label."""
    label_id: str = arguments["label_id"]
    registry = lr.async_get(hass)
    if registry.async_get_label(label_id) is None:
        raise HomeAssistantError(f"Label not found: {label_id}")

    kwargs = pick_kwargs(arguments, ("name", "color", "icon", "description"))

    try:
        entry = registry.async_update(label_id, **kwargs)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"label": _serialize_label(entry)}


@register_tool(
    name="delete_label",
    description="Delete a label registry entry",
    parameters=DELETE_LABEL_SCHEMA,
)
async def delete_label(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete one label."""
    label_id: str = arguments["label_id"]
    registry = lr.async_get(hass)
    if registry.async_get_label(label_id) is None:
        raise HomeAssistantError(f"Label not found: {label_id}")

    registry.async_delete(label_id)
    return {"deleted": label_id}
