"""Diagnostics tools for HA MCP Admin."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.loader import async_get_integration

from . import register_tool
from .common import normalize_data, redact_data

GET_CONFIG_ENTRY_DIAGNOSTICS_SCHEMA = vol.Schema(
    {vol.Required("entry_id"): cv.string}
)

GET_DEVICE_DIAGNOSTICS_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

GET_INTEGRATION_INFO_SCHEMA = vol.Schema({vol.Required("domain"): cv.string})

ENABLE_CONFIG_ENTRY_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string})

DISABLE_CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Optional("disable_reason", default="user"): cv.string,
    }
)


@register_tool(
    name="get_config_entry_diagnostics",
    description="Get diagnostics for an integration",
    parameters=GET_CONFIG_ENTRY_DIAGNOSTICS_SCHEMA,
)
async def get_config_entry_diagnostics(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get diagnostics for a config entry."""
    entry_id: str = arguments["entry_id"]

    # Validate config entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise HomeAssistantError(f"Config entry not found: {entry_id}")

    # Check if diagnostics component is available
    try:
        from homeassistant.components.diagnostics import (
            async_get_config_entry_diagnostics,
        )
    except ImportError as err:
        raise HomeAssistantError("Diagnostics component is not available") from err

    try:
        diagnostics = await async_get_config_entry_diagnostics(hass, entry.domain, entry)
    except Exception as err:
        raise HomeAssistantError(
            f"Failed to get diagnostics for {entry.domain}: {err}"
        ) from err

    if diagnostics is None:
        return {
            "entry_id": entry_id,
            "domain": entry.domain,
            "diagnostics": None,
            "message": f"Integration '{entry.domain}' does not support diagnostics",
        }

    return {
        "entry_id": entry_id,
        "domain": entry.domain,
        "diagnostics": normalize_data(diagnostics),
    }


@register_tool(
    name="get_device_diagnostics",
    description="Get diagnostics for a device",
    parameters=GET_DEVICE_DIAGNOSTICS_SCHEMA,
)
async def get_device_diagnostics(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get diagnostics for a device."""
    device_id: str = arguments["device_id"]
    entry_id: str | None = arguments.get("entry_id")

    # Get the device
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Device not found: {device_id}")

    # Determine which config entry to use
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise HomeAssistantError(f"Config entry not found: {entry_id}")
        if entry_id not in device.config_entries:
            raise HomeAssistantError(
                f"Device {device_id} is not associated with config entry {entry_id}"
            )
    elif device.config_entries:
        # Use the first config entry if not specified
        entry_id = next(iter(device.config_entries))
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise HomeAssistantError(
                f"Config entry not found for device: {entry_id}"
            )
    else:
        raise HomeAssistantError(
            f"Device {device_id} has no associated config entries"
        )

    # Check if diagnostics component is available
    try:
        from homeassistant.components.diagnostics import (
            async_get_device_diagnostics,
        )
    except ImportError as err:
        raise HomeAssistantError("Diagnostics component is not available") from err

    try:
        diagnostics = await async_get_device_diagnostics(
            hass, entry.domain, entry, device
        )
    except Exception as err:
        raise HomeAssistantError(
            f"Failed to get device diagnostics for {entry.domain}: {err}"
        ) from err

    if diagnostics is None:
        return {
            "device_id": device_id,
            "entry_id": entry_id,
            "domain": entry.domain,
            "diagnostics": None,
            "message": f"Integration '{entry.domain}' does not support device diagnostics",
        }

    return {
        "device_id": device_id,
        "entry_id": entry_id,
        "domain": entry.domain,
        "diagnostics": normalize_data(diagnostics),
    }


@register_tool(
    name="get_integration_info",
    description="Get detailed integration information",
    parameters=GET_INTEGRATION_INFO_SCHEMA,
)
async def get_integration_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get detailed information about an integration."""
    domain: str = arguments["domain"]

    # Try to load the integration
    try:
        integration = await async_get_integration(hass, domain)
    except Exception as err:
        raise HomeAssistantError(f"Integration not found: {domain}") from err

    # Get manifest information
    manifest = integration.manifest
    manifest_data = {
        "domain": manifest.get("domain"),
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "documentation": manifest.get("documentation"),
        "dependencies": manifest.get("dependencies", []),
        "after_dependencies": manifest.get("after_dependencies", []),
        "requirements": manifest.get("requirements", []),
        "codeowners": manifest.get("codeowners", []),
        "config_flow": manifest.get("config_flow", False),
        "iot_class": manifest.get("iot_class"),
        "integration_type": manifest.get("integration_type"),
        "quality_scale": manifest.get("quality_scale"),
        "is_built_in": integration.is_built_in,
    }

    # Get all config entries for this domain
    entries = hass.config_entries.async_entries(domain)
    config_entries_data = []
    for entry in entries:
        entry_data = {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "state": entry.state.value,
            "disabled_by": entry.disabled_by.value if entry.disabled_by else None,
            "source": entry.source,
        }
        config_entries_data.append(entry_data)

    # Count entities and devices for this domain
    entity_count = 0
    device_count = 0

    # Get entity count from entity registry
    from homeassistant.helpers import entity_registry as er

    entity_registry = er.async_get(hass)
    for entity_entry in entity_registry.entities.values():
        if entity_entry.platform == domain:
            entity_count += 1

    # Get device count from device registry
    device_registry = dr.async_get(hass)
    entry_ids = {entry.entry_id for entry in entries}
    seen_devices: set[str] = set()
    for device in device_registry.devices.values():
        if device.config_entries & entry_ids:
            if device.id not in seen_devices:
                seen_devices.add(device.id)
                device_count += 1

    # Check integration state via hass.data
    integration_data = hass.data.get(domain)
    has_data = integration_data is not None

    return {
        "domain": domain,
        "manifest": normalize_data(manifest_data),
        "config_entries": config_entries_data,
        "entity_count": entity_count,
        "device_count": device_count,
        "is_loaded": has_data,
        "config_entry_count": len(config_entries_data),
    }


@register_tool(
    name="enable_config_entry",
    description="Enable a disabled integration",
    parameters=ENABLE_CONFIG_ENTRY_SCHEMA,
)
async def enable_config_entry(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Enable a disabled config entry."""
    entry_id: str = arguments["entry_id"]

    # Validate config entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise HomeAssistantError(f"Config entry not found: {entry_id}")

    if entry.disabled_by is None:
        return {
            "entry_id": entry_id,
            "domain": entry.domain,
            "enabled": True,
            "message": "Config entry is already enabled",
        }

    result = await hass.config_entries.async_set_disabled_by(entry_id, None)

    if not result:
        raise HomeAssistantError(f"Failed to enable config entry: {entry_id}")

    return {
        "entry_id": entry_id,
        "domain": entry.domain,
        "enabled": True,
        "previous_disabled_by": entry.disabled_by.value if entry.disabled_by else None,
    }


@register_tool(
    name="disable_config_entry",
    description="Disable an integration",
    parameters=DISABLE_CONFIG_ENTRY_SCHEMA,
)
async def disable_config_entry(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Disable a config entry."""
    entry_id: str = arguments["entry_id"]
    disable_reason: str = arguments.get("disable_reason", "user")

    # Validate config entry exists
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise HomeAssistantError(f"Config entry not found: {entry_id}")

    # Map disable reason string to ConfigEntryDisabler
    disabler_map = {
        "user": ConfigEntryDisabler.USER,
    }
    disabler = disabler_map.get(disable_reason.lower())
    if disabler is None:
        # Default to USER if reason not recognized
        disabler = ConfigEntryDisabler.USER

    if entry.disabled_by is not None:
        return {
            "entry_id": entry_id,
            "domain": entry.domain,
            "disabled": True,
            "disabled_by": entry.disabled_by.value,
            "message": "Config entry is already disabled",
        }

    result = await hass.config_entries.async_set_disabled_by(entry_id, disabler)

    if not result:
        raise HomeAssistantError(f"Failed to disable config entry: {entry_id}")

    return {
        "entry_id": entry_id,
        "domain": entry.domain,
        "disabled": True,
        "disabled_by": disabler.value,
    }
