"""Area, floor, and label registry tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar, config_validation as cv
from homeassistant.helpers import floor_registry as fr, label_registry as lr

from . import register_tool
from .common import normalize_data

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

    kwargs: dict[str, Any] = {}
    for key in (
        "name",
        "floor_id",
        "icon",
        "picture",
        "temperature_entity_id",
        "humidity_entity_id",
    ):
        if key in arguments:
            kwargs[key] = arguments[key]

    if "aliases" in arguments:
        kwargs["aliases"] = set(arguments["aliases"])
    if "labels" in arguments:
        kwargs["labels"] = set(arguments["labels"])

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
async def create_floor(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
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
async def update_floor(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Update one floor."""
    floor_id: str = arguments["floor_id"]
    registry = fr.async_get(hass)
    if registry.async_get_floor(floor_id) is None:
        raise HomeAssistantError(f"Floor not found: {floor_id}")

    kwargs: dict[str, Any] = {}
    for key in ("name", "icon", "level"):
        if key in arguments:
            kwargs[key] = arguments[key]
    if "aliases" in arguments:
        kwargs["aliases"] = set(arguments["aliases"])

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
async def delete_floor(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Delete one floor."""
    floor_id: str = arguments["floor_id"]
    registry = fr.async_get(hass)
    if registry.async_get_floor(floor_id) is None:
        raise HomeAssistantError(f"Floor not found: {floor_id}")

    registry.async_delete(floor_id)
    return {"deleted": floor_id}


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
async def create_label(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
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
async def update_label(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Update one label."""
    label_id: str = arguments["label_id"]
    registry = lr.async_get(hass)
    if registry.async_get_label(label_id) is None:
        raise HomeAssistantError(f"Label not found: {label_id}")

    kwargs: dict[str, Any] = {}
    for key in ("name", "color", "icon", "description"):
        if key in arguments:
            kwargs[key] = arguments[key]

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
async def delete_label(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Delete one label."""
    label_id: str = arguments["label_id"]
    registry = lr.async_get(hass)
    if registry.async_get_label(label_id) is None:
        raise HomeAssistantError(f"Label not found: {label_id}")

    registry.async_delete(label_id)
    return {"deleted": label_id}
