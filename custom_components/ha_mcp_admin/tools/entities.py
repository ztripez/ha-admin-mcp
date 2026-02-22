"""Entity and device registry tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import (
    RegistryEntryDisabler,
    RegistryEntryHider,
)
from . import register_tool
from .common import normalize_data, pick_kwargs

LIST_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Optional("domain"): cv.string,
        vol.Optional("area_id"): cv.string,
        vol.Optional("device_id"): cv.string,
        vol.Optional("include_disabled", default=True): cv.boolean,
    }
)

GET_ENTITY_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})

UPDATE_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("name"): vol.Any(None, cv.string),
        vol.Optional("icon"): vol.Any(None, cv.icon),
        vol.Optional("area_id"): vol.Any(None, cv.string),
        vol.Optional("device_id"): vol.Any(None, cv.string),
        vol.Optional("disabled_by"): vol.Any(None, cv.string),
        vol.Optional("hidden_by"): vol.Any(None, cv.string),
        vol.Optional("labels"): [cv.string],
    }
)

REMOVE_ENTITY_SCHEMA = GET_ENTITY_SCHEMA

LIST_DEVICES_SCHEMA = vol.Schema(
    {
        vol.Optional("area_id"): cv.string,
        vol.Optional("manufacturer"): cv.string,
        vol.Optional("model"): cv.string,
        vol.Optional("include_disabled", default=True): cv.boolean,
    }
)

GET_DEVICE_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string})

UPDATE_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("name"): vol.Any(None, cv.string),
        vol.Optional("name_by_user"): vol.Any(None, cv.string),
        vol.Optional("area_id"): vol.Any(None, cv.string),
        vol.Optional("disabled_by"): vol.Any(None, cv.string),
        vol.Optional("manufacturer"): vol.Any(None, cv.string),
        vol.Optional("model"): vol.Any(None, cv.string),
        vol.Optional("sw_version"): vol.Any(None, cv.string),
        vol.Optional("hw_version"): vol.Any(None, cv.string),
        vol.Optional("labels"): [cv.string],
    }
)

REMOVE_DEVICE_SCHEMA = GET_DEVICE_SCHEMA


def _serialize_entity(entry: er.RegistryEntry) -> dict[str, Any]:
    """Serialize an entity registry entry."""
    return normalize_data(entry.extended_dict)


def _serialize_device(entry: dr.DeviceEntry) -> dict[str, Any]:
    """Serialize a device registry entry."""
    return normalize_data(entry.dict_repr)


def _parse_enum(value: str | None, cls: type) -> Any:
    """Parse an optional string into an enum value, or return None."""
    if value is None:
        return None
    return cls(value)


@register_tool(
    name="list_entities",
    description="List entity registry entries with optional filters",
    parameters=LIST_ENTITIES_SCHEMA,
)
async def list_entities(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List entities from the entity registry."""
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    requested_domain: str | None = arguments.get("domain")
    requested_area_id: str | None = arguments.get("area_id")
    requested_device_id: str | None = arguments.get("device_id")
    include_disabled: bool = arguments["include_disabled"]

    entities: list[dict[str, Any]] = []
    for entry in registry.entities.values():
        if requested_domain and entry.domain != requested_domain:
            continue
        if not include_disabled and entry.disabled:
            continue
        if requested_device_id and entry.device_id != requested_device_id:
            continue

        if requested_area_id:
            entry_area_id = entry.area_id
            if entry_area_id is None and entry.device_id is not None:
                if device := device_registry.async_get(entry.device_id):
                    entry_area_id = device.area_id
            if entry_area_id != requested_area_id:
                continue

        entities.append(_serialize_entity(entry))

    return {"count": len(entities), "entities": entities}


@register_tool(
    name="get_entity",
    description="Get one entity registry entry",
    parameters=GET_ENTITY_SCHEMA,
)
async def get_entity(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Get one entity registry entry."""
    entity_id: str = arguments["entity_id"]
    registry = er.async_get(hass)
    if (entry := registry.async_get(entity_id)) is None:
        raise HomeAssistantError(f"Entity not found: {entity_id}")

    return {"entity": _serialize_entity(entry)}


@register_tool(
    name="update_entity",
    description="Update one entity registry entry",
    parameters=UPDATE_ENTITY_SCHEMA,
)
async def update_entity(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update one entity registry entry."""
    entity_id: str = arguments["entity_id"]
    registry = er.async_get(hass)
    if registry.async_get(entity_id) is None:
        raise HomeAssistantError(f"Entity not found: {entity_id}")

    kwargs = pick_kwargs(
        arguments, ("name", "icon", "area_id", "device_id"), ("labels",)
    )
    if "disabled_by" in arguments:
        kwargs["disabled_by"] = _parse_enum(
            arguments["disabled_by"], RegistryEntryDisabler
        )
    if "hidden_by" in arguments:
        kwargs["hidden_by"] = _parse_enum(arguments["hidden_by"], RegistryEntryHider)

    try:
        updated = registry.async_update_entity(entity_id, **kwargs)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"entity": _serialize_entity(updated)}


@register_tool(
    name="remove_entity",
    description="Remove one entity from entity registry",
    parameters=REMOVE_ENTITY_SCHEMA,
)
async def remove_entity(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Remove one entity registry entry."""
    entity_id: str = arguments["entity_id"]
    registry = er.async_get(hass)
    if registry.async_get(entity_id) is None:
        raise HomeAssistantError(f"Entity not found: {entity_id}")

    registry.async_remove(entity_id)
    return {"deleted": entity_id}


@register_tool(
    name="list_devices",
    description="List device registry entries with optional filters",
    parameters=LIST_DEVICES_SCHEMA,
)
async def list_devices(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List devices from the device registry."""
    registry = dr.async_get(hass)
    requested_area_id: str | None = arguments.get("area_id")
    requested_manufacturer: str | None = arguments.get("manufacturer")
    requested_model: str | None = arguments.get("model")
    include_disabled: bool = arguments["include_disabled"]

    devices: list[dict[str, Any]] = []
    for entry in registry.devices.values():
        if requested_area_id and entry.area_id != requested_area_id:
            continue
        if requested_manufacturer and entry.manufacturer != requested_manufacturer:
            continue
        if requested_model and entry.model != requested_model:
            continue
        if not include_disabled and entry.disabled:
            continue
        devices.append(_serialize_device(entry))

    return {"count": len(devices), "devices": devices}


@register_tool(
    name="get_device",
    description="Get one device registry entry",
    parameters=GET_DEVICE_SCHEMA,
)
async def get_device(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Get one device registry entry."""
    device_id: str = arguments["device_id"]
    registry = dr.async_get(hass)
    if (entry := registry.async_get(device_id)) is None:
        raise HomeAssistantError(f"Device not found: {device_id}")

    return {"device": _serialize_device(entry)}


@register_tool(
    name="update_device",
    description="Update one device registry entry",
    parameters=UPDATE_DEVICE_SCHEMA,
)
async def update_device(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update one device registry entry."""
    device_id: str = arguments["device_id"]
    registry = dr.async_get(hass)
    if registry.async_get(device_id) is None:
        raise HomeAssistantError(f"Device not found: {device_id}")

    kwargs = pick_kwargs(
        arguments,
        (
            "name",
            "name_by_user",
            "area_id",
            "manufacturer",
            "model",
            "sw_version",
            "hw_version",
        ),
        ("labels",),
    )
    if "disabled_by" in arguments:
        kwargs["disabled_by"] = _parse_enum(
            arguments["disabled_by"], DeviceEntryDisabler
        )

    try:
        updated = registry.async_update_device(device_id, **kwargs)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    if updated is None:
        raise HomeAssistantError(f"Unable to update device: {device_id}")

    return {"device": _serialize_device(updated)}


@register_tool(
    name="remove_device",
    description="Remove one device from device registry",
    parameters=REMOVE_DEVICE_SCHEMA,
)
async def remove_device(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Remove one device registry entry."""
    device_id: str = arguments["device_id"]
    registry = dr.async_get(hass)
    if registry.async_get(device_id) is None:
        raise HomeAssistantError(f"Device not found: {device_id}")

    registry.async_remove_device(device_id)
    return {"deleted": device_id}
