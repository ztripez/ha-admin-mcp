"""Supervisor and add-on management tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data, redact_data

# Constant for error message when Supervisor is not available
SUPERVISOR_NOT_AVAILABLE_MSG = (
    "Supervisor not available. "
    "Requires Home Assistant OS or Supervised installation."
)


def _check_supervisor(hass: HomeAssistant) -> None:
    """Check if Supervisor is available, raise if not."""
    if "hassio" not in hass.config.components:
        raise HomeAssistantError(SUPERVISOR_NOT_AVAILABLE_MSG)


def _get_hassio(hass: HomeAssistant) -> Any:
    """Get the HassIO handler, raising if unavailable."""
    _check_supervisor(hass)
    from homeassistant.components.hassio.const import DATA_COMPONENT  # noqa: PLC0415

    hassio = hass.data.get(DATA_COMPONENT)
    if hassio is None:
        raise HomeAssistantError(SUPERVISOR_NOT_AVAILABLE_MSG)
    return hassio


def _get_supervisor_client(hass: HomeAssistant) -> Any:
    """Get the SupervisorClient, raising if unavailable."""
    _check_supervisor(hass)
    from homeassistant.components.hassio.handler import (  # noqa: PLC0415
        get_supervisor_client,
    )

    return get_supervisor_client(hass)


# Schemas
GET_SUPERVISOR_INFO_SCHEMA = vol.Schema({})
GET_HOST_INFO_SCHEMA = vol.Schema({})
LIST_ADDONS_SCHEMA = vol.Schema({})
GET_ADDON_INFO_SCHEMA = vol.Schema({vol.Required("slug"): cv.string})
GET_ADDON_LOGS_SCHEMA = vol.Schema(
    {
        vol.Required("slug"): cv.string,
        vol.Optional("lines", default=100): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10000)
        ),
    }
)
START_ADDON_SCHEMA = vol.Schema({vol.Required("slug"): cv.string})
STOP_ADDON_SCHEMA = vol.Schema({vol.Required("slug"): cv.string})
RESTART_ADDON_SCHEMA = vol.Schema({vol.Required("slug"): cv.string})
GET_SUPERVISOR_LOGS_SCHEMA = vol.Schema(
    {
        vol.Optional("lines", default=100): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10000)
        ),
    }
)


@register_tool(
    name="get_supervisor_info",
    description=(
        "Get Supervisor status and information including version, channel, "
        "architecture, health status, and IP address. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=GET_SUPERVISOR_INFO_SCHEMA,
)
async def get_supervisor_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get Supervisor status and information."""
    hassio = _get_hassio(hass)

    try:
        from homeassistant.components.hassio.handler import (  # noqa: PLC0415
            HassioAPIError,
        )

        info = await hassio.get_supervisor_info()
    except Exception as err:
        raise HomeAssistantError(f"Failed to get Supervisor info: {err}") from err

    # Extract relevant fields and normalize
    result = normalize_data(
        {
            "version": info.get("version"),
            "version_latest": info.get("version_latest"),
            "update_available": info.get("update_available", False),
            "channel": info.get("channel"),
            "arch": info.get("arch"),
            "supported": info.get("supported"),
            "healthy": info.get("healthy"),
            "ip_address": info.get("ip_address"),
            "timezone": info.get("timezone"),
            "logging": info.get("logging"),
            "debug": info.get("debug"),
            "debug_block": info.get("debug_block"),
            "diagnostics": info.get("diagnostics"),
            "addons": [
                {
                    "slug": addon.get("slug"),
                    "name": addon.get("name"),
                    "state": addon.get("state"),
                    "version": addon.get("version"),
                    "update_available": addon.get("update_available", False),
                }
                for addon in info.get("addons", [])
            ],
        }
    )

    return {"supervisor": result}


@register_tool(
    name="get_host_info",
    description=(
        "Get host OS information including hostname, kernel version, "
        "OS name and version, disk usage statistics. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=GET_HOST_INFO_SCHEMA,
)
async def get_host_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get host OS information."""
    hassio = _get_hassio(hass)

    try:
        info = await hassio.get_host_info()
    except Exception as err:
        raise HomeAssistantError(f"Failed to get host info: {err}") from err

    result = normalize_data(
        {
            "hostname": info.get("hostname"),
            "kernel": info.get("kernel"),
            "operating_system": info.get("operating_system"),
            "cpe": info.get("cpe"),
            "deployment": info.get("deployment"),
            "disk_total": info.get("disk_total"),
            "disk_used": info.get("disk_used"),
            "disk_free": info.get("disk_free"),
            "disk_life_time": info.get("disk_life_time"),
            "features": info.get("features", []),
            "boot_timestamp": info.get("boot_timestamp"),
            "startup_time": info.get("startup_time"),
            "agent_version": info.get("agent_version"),
            "broadcast_llmnr": info.get("broadcast_llmnr"),
            "broadcast_mdns": info.get("broadcast_mdns"),
            "chassis": info.get("chassis"),
            "virtualization": info.get("virtualization"),
        }
    )

    return {"host": result}


@register_tool(
    name="list_addons",
    description=(
        "List all installed add-ons with their status including slug, name, "
        "description, version, state (started/stopped), and update availability. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=LIST_ADDONS_SCHEMA,
)
async def list_addons(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List all installed add-ons."""
    hassio = _get_hassio(hass)

    try:
        supervisor_info = await hassio.get_supervisor_info()
    except Exception as err:
        raise HomeAssistantError(f"Failed to list add-ons: {err}") from err

    addons_raw = supervisor_info.get("addons", [])

    addons = [
        normalize_data(
            {
                "slug": addon.get("slug"),
                "name": addon.get("name"),
                "description": addon.get("description"),
                "version": addon.get("version"),
                "version_latest": addon.get("version_latest"),
                "state": addon.get("state"),
                "installed": True,  # All addons from supervisor_info are installed
                "update_available": addon.get("update_available", False),
                "repository": addon.get("repository"),
                "icon": addon.get("icon"),
            }
        )
        for addon in addons_raw
    ]

    return {"count": len(addons), "addons": addons}


@register_tool(
    name="get_addon_info",
    description=(
        "Get detailed information about a specific add-on including configuration, "
        "ports, volumes, and status. Sensitive options are redacted. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=GET_ADDON_INFO_SCHEMA,
)
async def get_addon_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get detailed add-on information."""
    slug: str = arguments["slug"]
    client = _get_supervisor_client(hass)

    try:
        from aiohasupervisor import SupervisorError  # noqa: PLC0415

        info = await client.addons.addon_info(slug)
    except SupervisorError as err:
        raise HomeAssistantError(f"Failed to get add-on info for '{slug}': {err}") from err
    except Exception as err:
        raise HomeAssistantError(f"Failed to get add-on info for '{slug}': {err}") from err

    # Convert to dict and redact sensitive data
    info_dict = info.to_dict()

    # Redact sensitive options
    if "options" in info_dict:
        info_dict["options"] = redact_data(info_dict["options"])

    # Normalize the data
    result = normalize_data(info_dict)

    return {"addon": result}


@register_tool(
    name="get_addon_logs",
    description=(
        "Get log output from a specific add-on. Returns the last N lines of logs. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=GET_ADDON_LOGS_SCHEMA,
)
async def get_addon_logs(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get add-on log output."""
    slug: str = arguments["slug"]
    lines: int = arguments.get("lines", 100)
    hassio = _get_hassio(hass)

    try:
        from homeassistant.components.hassio.handler import (  # noqa: PLC0415
            HassioAPIError,
        )

        # Call the Supervisor API to get logs
        log_text = await hassio.send_command(
            f"/addons/{slug}/logs",
            method="get",
            return_text=True,
            timeout=30,
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to get logs for add-on '{slug}': {err}") from err

    # Limit the number of lines returned
    if log_text:
        log_lines = log_text.strip().split("\n")
        if len(log_lines) > lines:
            log_lines = log_lines[-lines:]
        log_text = "\n".join(log_lines)

    return {
        "slug": slug,
        "lines_requested": lines,
        "lines_returned": len(log_text.strip().split("\n")) if log_text else 0,
        "logs": log_text or "",
    }


@register_tool(
    name="start_addon",
    description=(
        "Start an add-on. The add-on must be installed. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=START_ADDON_SCHEMA,
)
async def start_addon(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Start an add-on."""
    slug: str = arguments["slug"]
    client = _get_supervisor_client(hass)

    try:
        from aiohasupervisor import SupervisorError  # noqa: PLC0415

        await client.addons.start_addon(slug)
    except SupervisorError as err:
        raise HomeAssistantError(f"Failed to start add-on '{slug}': {err}") from err
    except Exception as err:
        raise HomeAssistantError(f"Failed to start add-on '{slug}': {err}") from err

    return {
        "slug": slug,
        "status": "started",
        "message": f"Add-on '{slug}' has been started.",
    }


@register_tool(
    name="stop_addon",
    description=(
        "Stop a running add-on. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=STOP_ADDON_SCHEMA,
)
async def stop_addon(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Stop an add-on."""
    slug: str = arguments["slug"]
    client = _get_supervisor_client(hass)

    try:
        from aiohasupervisor import SupervisorError  # noqa: PLC0415

        await client.addons.stop_addon(slug)
    except SupervisorError as err:
        raise HomeAssistantError(f"Failed to stop add-on '{slug}': {err}") from err
    except Exception as err:
        raise HomeAssistantError(f"Failed to stop add-on '{slug}': {err}") from err

    return {
        "slug": slug,
        "status": "stopped",
        "message": f"Add-on '{slug}' has been stopped.",
    }


@register_tool(
    name="restart_addon",
    description=(
        "Restart a running add-on. The add-on will be stopped and started again. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=RESTART_ADDON_SCHEMA,
)
async def restart_addon(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Restart an add-on."""
    slug: str = arguments["slug"]
    client = _get_supervisor_client(hass)

    try:
        from aiohasupervisor import SupervisorError  # noqa: PLC0415

        await client.addons.restart_addon(slug)
    except SupervisorError as err:
        raise HomeAssistantError(f"Failed to restart add-on '{slug}': {err}") from err
    except Exception as err:
        raise HomeAssistantError(f"Failed to restart add-on '{slug}': {err}") from err

    return {
        "slug": slug,
        "status": "restarted",
        "message": f"Add-on '{slug}' has been restarted.",
    }


@register_tool(
    name="get_supervisor_logs",
    description=(
        "Get Supervisor log output. Returns the last N lines of Supervisor logs. "
        "Useful for debugging Supervisor issues. "
        "Requires Home Assistant OS or Supervised installation."
    ),
    parameters=GET_SUPERVISOR_LOGS_SCHEMA,
)
async def get_supervisor_logs(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get Supervisor log output."""
    lines: int = arguments.get("lines", 100)
    hassio = _get_hassio(hass)

    try:
        # Call the Supervisor API to get logs
        log_text = await hassio.send_command(
            "/supervisor/logs",
            method="get",
            return_text=True,
            timeout=30,
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to get Supervisor logs: {err}") from err

    # Limit the number of lines returned
    if log_text:
        log_lines = log_text.strip().split("\n")
        if len(log_lines) > lines:
            log_lines = log_lines[-lines:]
        log_text = "\n".join(log_lines)

    return {
        "lines_requested": lines,
        "lines_returned": len(log_text.strip().split("\n")) if log_text else 0,
        "logs": log_text or "",
    }
