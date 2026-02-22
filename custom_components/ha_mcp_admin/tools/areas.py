"""Area registry tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar, config_validation as cv
from homeassistant.helpers import floor_registry as fr, label_registry as lr

from . import register_tool
from .common import normalize_data, pick_kwargs

LIST_AREAS_SCHEMA = vol.Schema({})
CREATE_AREA_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("aliases"): [cv.string],
        vol.Optional("floor_id"): vol.Any(None, cv.string),
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("labels"): [cv.string],
        vol.Optional("picture"): vol.Any(None, cv.string),
        vol.Optional("temperature_entity_id"): vol.Any(None, cv.entity_id),
        vol.Optional("humidity_entity_id"): vol.Any(None, cv.entity_id),
    }
)
UPDATE_AREA_SCHEMA = vol.Schema(
    {
        vol.Required("area_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("aliases"): [cv.string],
        vol.Optional("floor_id"): vol.Any(None, cv.string),
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("labels"): [cv.string],
        vol.Optional("picture"): vol.Any(None, cv.string),
        vol.Optional("temperature_entity_id"): vol.Any(None, cv.entity_id),
        vol.Optional("humidity_entity_id"): vol.Any(None, cv.entity_id),
    }
)
DELETE_AREA_SCHEMA = vol.Schema({vol.Required("area_id"): cv.string})


def _serialize_area(entry: ar.AreaEntry) -> dict[str, Any]:
    """Serialize area entry."""
    return normalize_data(
        {
            "area_id": entry.id,
            "name": entry.name,
            "aliases": sorted(entry.aliases),
            "floor_id": entry.floor_id,
            "icon": entry.icon,
            "labels": sorted(entry.labels),
            "picture": entry.picture,
            "temperature_entity_id": entry.temperature_entity_id,
            "humidity_entity_id": entry.humidity_entity_id,
            "created_at": entry.created_at,
            "modified_at": entry.modified_at,
        }
    )


def _validate_floor_exists(hass: HomeAssistant, floor_id: str | None) -> None:
    """Validate floor ID if provided."""
    if floor_id is None:
        return
    floor_registry = fr.async_get(hass)
    if floor_registry.async_get_floor(floor_id) is None:
        raise HomeAssistantError(f"Floor not found: {floor_id}")


def _validate_labels_exist(hass: HomeAssistant, label_ids: list[str] | None) -> None:
    """Validate each label ID if provided."""
    if label_ids is None:
        return
    label_registry = lr.async_get(hass)
    for label_id in label_ids:
        if label_registry.async_get_label(label_id) is None:
            raise HomeAssistantError(f"Label not found: {label_id}")


@register_tool(
    name="list_areas",
    description="List all area registry entries",
    parameters=LIST_AREAS_SCHEMA,
)
async def list_areas(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """List all areas."""
    del arguments
    registry = ar.async_get(hass)
    areas = [_serialize_area(entry) for entry in registry.async_list_areas()]
    return {"count": len(areas), "areas": areas}


@register_tool(
    name="create_area",
    description="Create an area registry entry",
    parameters=CREATE_AREA_SCHEMA,
)
async def create_area(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create one area."""
    _validate_floor_exists(hass, arguments.get("floor_id"))
    _validate_labels_exist(hass, arguments.get("labels"))

    registry = ar.async_get(hass)
    try:
        entry = registry.async_create(
            arguments["name"],
            aliases=set(arguments.get("aliases", [])),
            floor_id=arguments.get("floor_id"),
            icon=arguments.get("icon"),
            labels=set(arguments.get("labels", [])),
            picture=arguments.get("picture"),
            temperature_entity_id=arguments.get("temperature_entity_id"),
            humidity_entity_id=arguments.get("humidity_entity_id"),
        )
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"area": _serialize_area(entry)}


@register_tool(
    name="update_area",
    description="Update an area registry entry",
    parameters=UPDATE_AREA_SCHEMA,
)
async def update_area(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Update one area."""
    area_id: str = arguments["area_id"]
    registry = ar.async_get(hass)
    if registry.async_get_area(area_id) is None:
        raise HomeAssistantError(f"Area not found: {area_id}")

    _validate_floor_exists(hass, arguments.get("floor_id"))
    _validate_labels_exist(hass, arguments.get("labels"))

    kwargs = pick_kwargs(
        arguments,
        (
            "name",
            "floor_id",
            "icon",
            "picture",
            "temperature_entity_id",
            "humidity_entity_id",
        ),
        ("aliases", "labels"),
    )

    try:
        entry = registry.async_update(area_id, **kwargs)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"area": _serialize_area(entry)}


@register_tool(
    name="delete_area",
    description="Delete an area registry entry",
    parameters=DELETE_AREA_SCHEMA,
)
async def delete_area(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Delete one area."""
    area_id: str = arguments["area_id"]
    registry = ar.async_get(hass)
    if registry.async_get_area(area_id) is None:
        raise HomeAssistantError(f"Area not found: {area_id}")

    registry.async_delete(area_id)
    return {"deleted": area_id}
