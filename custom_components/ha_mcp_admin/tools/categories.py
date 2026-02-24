"""Category registry tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import category_registry as cr, config_validation as cv

from . import register_tool
from .common import normalize_data, pick_kwargs

LIST_CATEGORIES_SCHEMA = vol.Schema({vol.Optional("scope"): cv.string})
CREATE_CATEGORY_SCHEMA = vol.Schema(
    {
        vol.Required("scope"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("icon"): vol.Any(None, cv.icon),
    }
)
UPDATE_CATEGORY_SCHEMA = vol.Schema(
    {
        vol.Required("scope"): cv.string,
        vol.Required("category_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("icon"): vol.Any(None, cv.icon),
    }
)
DELETE_CATEGORY_SCHEMA = vol.Schema(
    {
        vol.Required("scope"): cv.string,
        vol.Required("category_id"): cv.string,
    }
)


def _serialize_category(scope: str, entry: cr.CategoryEntry) -> dict[str, Any]:
    """Serialize one category entry."""
    return normalize_data(
        {
            "scope": scope,
            "category_id": entry.category_id,
            "name": entry.name,
            "icon": entry.icon,
            "created_at": entry.created_at,
            "modified_at": entry.modified_at,
        }
    )


@register_tool(
    name="list_categories",
    description="List category registry entries",
    parameters=LIST_CATEGORIES_SCHEMA,
)
async def list_categories(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List categories, optionally filtered by scope."""
    registry = cr.async_get(hass)

    if scope := arguments.get("scope"):
        categories = [
            _serialize_category(scope, entry)
            for entry in registry.async_list_categories(scope=scope)
        ]
        return {"count": len(categories), "scope": scope, "categories": categories}

    categories = [
        _serialize_category(scope, entry)
        for scope in sorted(registry.categories)
        for entry in registry.async_list_categories(scope=scope)
    ]
    return {"count": len(categories), "categories": categories}


@register_tool(
    name="create_category",
    description="Create a category registry entry",
    parameters=CREATE_CATEGORY_SCHEMA,
)
async def create_category(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create one category."""
    scope: str = arguments["scope"]
    registry = cr.async_get(hass)

    try:
        entry = registry.async_create(
            scope=scope,
            name=arguments["name"],
            icon=arguments.get("icon"),
        )
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"category": _serialize_category(scope, entry)}


@register_tool(
    name="update_category",
    description="Update a category registry entry",
    parameters=UPDATE_CATEGORY_SCHEMA,
)
async def update_category(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update one category."""
    scope: str = arguments["scope"]
    category_id: str = arguments["category_id"]
    registry = cr.async_get(hass)

    if registry.async_get_category(scope=scope, category_id=category_id) is None:
        raise HomeAssistantError(f"Category not found: {scope}::{category_id}")

    kwargs = pick_kwargs(arguments, ("name", "icon"))

    try:
        entry = registry.async_update(scope=scope, category_id=category_id, **kwargs)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"category": _serialize_category(scope, entry)}


@register_tool(
    name="delete_category",
    description="Delete a category registry entry",
    parameters=DELETE_CATEGORY_SCHEMA,
)
async def delete_category(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete one category."""
    scope: str = arguments["scope"]
    category_id: str = arguments["category_id"]
    registry = cr.async_get(hass)

    if registry.async_get_category(scope=scope, category_id=category_id) is None:
        raise HomeAssistantError(f"Category not found: {scope}::{category_id}")

    registry.async_delete(scope=scope, category_id=category_id)
    return {"scope": scope, "deleted": category_id}
