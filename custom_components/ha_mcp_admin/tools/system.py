"""System administration tools for Home Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.check_config import async_check_ha_config_file

from . import register_tool
from .common import normalize_data

# Schemas
GET_SYSTEM_HEALTH_SCHEMA = vol.Schema({})
GET_HA_INFO_SCHEMA = vol.Schema({})
VALIDATE_CONFIG_SCHEMA = vol.Schema({})
RESTART_HA_SCHEMA = vol.Schema({})
RELOAD_CORE_CONFIG_SCHEMA = vol.Schema({})
GET_SYSTEM_LOGS_SCHEMA = vol.Schema(
    {
        vol.Optional("level"): vol.In(
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        ),
    }
)
CLEAR_SYSTEM_LOGS_SCHEMA = vol.Schema({})


@register_tool(
    name="get_system_health",
    description="Get system health information from all registered domains",
    parameters=GET_SYSTEM_HEALTH_SCHEMA,
)
async def get_system_health(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get system health information from all registered domains.

    This collects health information from all integrations that have
    registered system health handlers.
    """
    # Import system_health component
    try:
        from homeassistant.components import system_health
    except ImportError as err:
        raise HomeAssistantError("system_health component not available") from err

    # Check if system_health is loaded
    if system_health.DOMAIN not in hass.data:
        raise HomeAssistantError(
            "system_health component is not loaded. "
            "Ensure it is enabled in your configuration."
        )

    # Get all registered info callbacks
    info_callbacks = hass.data[system_health.DOMAIN]

    health_info: dict[str, Any] = {}

    for domain, callback_info in info_callbacks.items():
        try:
            # Each domain registers a callback that returns health info
            info = await callback_info["info"](hass)
            health_info[domain] = normalize_data(info)
        except Exception as err:  # noqa: BLE001
            health_info[domain] = {"error": str(err)}

    return {"domains": health_info}


@register_tool(
    name="get_ha_info",
    description="Get Home Assistant core information including version, timezone, and location",
    parameters=GET_HA_INFO_SCHEMA,
)
async def get_ha_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get Home Assistant core configuration information.

    Returns version, timezone, location, unit system, and other core settings.
    """
    config = hass.config

    return {
        "version": config.version,
        "location_name": config.location_name,
        "time_zone": str(config.time_zone),
        "latitude": config.latitude,
        "longitude": config.longitude,
        "elevation": config.elevation,
        "unit_system": {
            "name": config.units.name,
            "temperature": config.units.temperature_unit,
            "length": config.units.length_unit,
            "mass": config.units.mass_unit,
            "volume": config.units.volume_unit,
            "pressure": config.units.pressure_unit,
            "wind_speed": config.units.wind_speed_unit,
            "accumulated_precipitation": config.units.accumulated_precipitation_unit,
        },
        "config_dir": config.config_dir,
        "allowlist_external_dirs": list(config.allowlist_external_dirs),
        "allowlist_external_urls": list(config.allowlist_external_urls),
        "components": sorted(config.components),
        "state": config.state.value,
        "external_url": config.external_url,
        "internal_url": config.internal_url,
        "currency": config.currency,
        "country": config.country,
        "language": config.language,
        "safe_mode": config.safe_mode,
        "recovery_mode": config.recovery_mode,
    }


@register_tool(
    name="validate_config",
    description="Validate Home Assistant configuration files for errors",
    parameters=VALIDATE_CONFIG_SCHEMA,
)
async def validate_config(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Validate Home Assistant configuration files.

    Runs the configuration validation check and returns any errors found.
    """
    result = await async_check_ha_config_file(hass)

    errors: list[dict[str, Any]] = []
    for error in result.errors:
        errors.append(
            {
                "domain": error.domain,
                "message": error.message,
            }
        )

    return {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
    }


@register_tool(
    name="restart_homeassistant",
    description=(
        "Restart Home Assistant. WARNING: This will end the current MCP session "
        "and all connections will be lost. Use with caution."
    ),
    parameters=RESTART_HA_SCHEMA,
)
async def restart_homeassistant(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Restart Home Assistant.

    WARNING: This will terminate the MCP session and all active connections.
    The system will restart and connections will need to be re-established.
    """
    await hass.services.async_call(
        "homeassistant",
        "restart",
        blocking=False,  # Don't block, as restart will terminate this connection
    )

    return {
        "status": "restart_initiated",
        "message": (
            "Home Assistant restart has been initiated. "
            "This session will end and you will need to reconnect."
        ),
    }


@register_tool(
    name="reload_core_config",
    description="Reload Home Assistant core configuration without restarting",
    parameters=RELOAD_CORE_CONFIG_SCHEMA,
)
async def reload_core_config(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Reload Home Assistant core configuration.

    This reloads core configuration from configuration.yaml without
    requiring a full restart.
    """
    await hass.services.async_call(
        "homeassistant",
        "reload_core_config",
        blocking=True,
    )

    return {
        "status": "reloaded",
        "message": "Core configuration has been reloaded successfully.",
    }


@register_tool(
    name="get_system_logs",
    description="Get system log entries, optionally filtered by log level",
    parameters=GET_SYSTEM_LOGS_SCHEMA,
)
async def get_system_logs(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get system log entries.

    Returns log entries from the system_log component, optionally
    filtered by minimum log level.
    """
    try:
        from homeassistant.components import system_log
    except ImportError as err:
        raise HomeAssistantError("system_log component not available") from err

    # Check if system_log is loaded
    if system_log.DOMAIN not in hass.data:
        raise HomeAssistantError(
            "system_log component is not loaded. "
            "Ensure it is enabled in your configuration."
        )

    # Get the log handler from hass.data
    log_handler = hass.data[system_log.DOMAIN]

    # Get all log entries
    entries = log_handler.records

    # Map log level names to numeric values for filtering
    level_map = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }

    filter_level = arguments.get("level")
    min_level = level_map.get(filter_level, 0) if filter_level else 0

    log_entries: list[dict[str, Any]] = []
    for entry in entries:
        # Filter by level if specified
        if entry.level < min_level:
            continue

        log_entry = {
            "name": entry.name,
            "level": entry.level,
            "message": entry.message,
            "timestamp": entry.timestamp,
            "exception": entry.exception,
            "count": entry.count,
            "first_occurred": entry.first_occurred,
        }
        log_entries.append(normalize_data(log_entry))

    return {
        "count": len(log_entries),
        "filter_level": filter_level,
        "entries": log_entries,
    }


@register_tool(
    name="clear_system_logs",
    description="Clear all system log entries",
    parameters=CLEAR_SYSTEM_LOGS_SCHEMA,
)
async def clear_system_logs(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Clear all system log entries.

    This removes all entries from the system log buffer.
    """
    # Check if system_log service is available
    if not hass.services.has_service("system_log", "clear"):
        raise HomeAssistantError(
            "system_log.clear service is not available. "
            "Ensure the system_log component is loaded."
        )

    await hass.services.async_call(
        "system_log",
        "clear",
        blocking=True,
    )

    return {
        "status": "cleared",
        "message": "System logs have been cleared successfully.",
    }
