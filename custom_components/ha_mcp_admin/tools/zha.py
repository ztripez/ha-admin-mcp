"""ZHA/Zigbee device management tools."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data

# IEEE address pattern: 8 pairs of hex digits separated by colons
IEEE_PATTERN = re.compile(r"^([0-9a-fA-F]{2}:){7}[0-9a-fA-F]{2}$")

LIST_ZHA_DEVICES_SCHEMA = vol.Schema({})

GET_ZHA_DEVICE_INFO_SCHEMA = vol.Schema({vol.Required("ieee"): cv.string})

PERMIT_ZHA_JOIN_SCHEMA = vol.Schema(
    {
        vol.Optional("duration", default=60): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=254)
        ),
        vol.Optional("ieee"): cv.string,
    }
)

RECONFIGURE_ZHA_DEVICE_SCHEMA = vol.Schema({vol.Required("ieee"): cv.string})


def _validate_ieee(ieee: str) -> str:
    """Validate IEEE address format."""
    if not IEEE_PATTERN.match(ieee):
        raise HomeAssistantError(
            f"Invalid IEEE address format: {ieee}. "
            "Expected format: 00:11:22:33:44:55:66:77"
        )
    return ieee


def _check_zha_loaded(hass: HomeAssistant) -> None:
    """Check if ZHA integration is loaded."""
    if "zha" not in hass.config.components:
        raise HomeAssistantError(
            "ZHA integration is not loaded. "
            "Please configure ZHA in Home Assistant first."
        )


def _get_zha_gateway(hass: HomeAssistant) -> Any:
    """Get the ZHA gateway from hass.data."""
    _check_zha_loaded(hass)

    zha_data = hass.data.get("zha")
    if zha_data is None:
        raise HomeAssistantError("ZHA data not available")

    # Try different ZHA data structures (varies by HA version)
    gateway = None
    if isinstance(zha_data, dict):
        gateway = zha_data.get("zha_gateway") or zha_data.get("gateway")
    elif hasattr(zha_data, "gateway"):
        gateway = zha_data.gateway

    if gateway is None:
        raise HomeAssistantError("ZHA gateway not found in ZHA data")

    return gateway


def _serialize_zha_device(device: Any) -> dict[str, Any]:
    """Serialize a ZHA device to a dictionary."""
    data: dict[str, Any] = {
        "ieee": str(device.ieee),
        "nwk": device.nwk,
        "manufacturer": getattr(device, "manufacturer", None),
        "model": getattr(device, "model", None),
        "name": getattr(device, "name", None),
        "quirk_applied": getattr(device, "quirk_applied", False),
        "available": getattr(device, "available", False),
        "lqi": getattr(device, "lqi", None),
        "rssi": getattr(device, "rssi", None),
        "last_seen": getattr(device, "last_seen", None),
    }
    return normalize_data(data)


def _serialize_zha_device_detailed(device: Any) -> dict[str, Any]:
    """Serialize a ZHA device with full details."""
    # Start with basic info
    data = _serialize_zha_device(device)

    # Add device type info
    data["device_type"] = getattr(device, "device_type", None)
    data["power_source"] = getattr(device, "power_source", None)
    data["skip_configuration"] = getattr(device, "skip_configuration", False)

    # Add signature if available
    if hasattr(device, "device") and hasattr(device.device, "signature"):
        data["signature"] = normalize_data(device.device.signature)

    # Add endpoints info
    endpoints: list[dict[str, Any]] = []
    if hasattr(device, "device") and hasattr(device.device, "endpoints"):
        for ep_id, endpoint in device.device.endpoints.items():
            ep_data: dict[str, Any] = {
                "id": ep_id,
                "device_type": getattr(endpoint, "device_type", None),
                "profile_id": getattr(endpoint, "profile_id", None),
            }

            # Input clusters
            if hasattr(endpoint, "in_clusters"):
                ep_data["in_clusters"] = [
                    {"id": c_id, "name": getattr(cluster, "name", str(c_id))}
                    for c_id, cluster in endpoint.in_clusters.items()
                ]

            # Output clusters
            if hasattr(endpoint, "out_clusters"):
                ep_data["out_clusters"] = [
                    {"id": c_id, "name": getattr(cluster, "name", str(c_id))}
                    for c_id, cluster in endpoint.out_clusters.items()
                ]

            endpoints.append(ep_data)

    data["endpoints"] = endpoints

    # Add neighbors info if available
    if hasattr(device, "neighbors"):
        data["neighbors"] = normalize_data(
            [
                {
                    "ieee": str(n.neighbor.ieee) if hasattr(n, "neighbor") else str(n),
                    "relationship": getattr(n, "relationship", None),
                    "depth": getattr(n, "depth", None),
                    "lqi": getattr(n, "lqi", None),
                }
                for n in device.neighbors
            ]
        )

    return normalize_data(data)


@register_tool(
    name="list_zha_devices",
    description="List all Zigbee devices managed by ZHA",
    parameters=LIST_ZHA_DEVICES_SCHEMA,
)
async def list_zha_devices(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List all ZHA Zigbee devices."""
    gateway = _get_zha_gateway(hass)

    devices_dict = getattr(gateway, "devices", {})
    devices = [_serialize_zha_device(device) for device in devices_dict.values()]

    return {"count": len(devices), "devices": devices}


@register_tool(
    name="get_zha_device_info",
    description="Get detailed information for a specific Zigbee device by IEEE address",
    parameters=GET_ZHA_DEVICE_INFO_SCHEMA,
)
async def get_zha_device_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get detailed info for a ZHA Zigbee device."""
    ieee = _validate_ieee(arguments["ieee"])
    gateway = _get_zha_gateway(hass)

    # Find device by IEEE address
    devices_dict = getattr(gateway, "devices", {})
    device = None

    for dev in devices_dict.values():
        if str(dev.ieee).lower() == ieee.lower():
            device = dev
            break

    if device is None:
        raise HomeAssistantError(f"ZHA device not found with IEEE: {ieee}")

    return {"device": _serialize_zha_device_detailed(device)}


@register_tool(
    name="permit_zha_join",
    description="Enable Zigbee network joining (pairing mode) for new devices",
    parameters=PERMIT_ZHA_JOIN_SCHEMA,
)
async def permit_zha_join(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Enable Zigbee network joining for pairing new devices."""
    _check_zha_loaded(hass)

    duration: int = arguments.get("duration", 60)
    ieee: str | None = arguments.get("ieee")

    service_data: dict[str, Any] = {"duration": duration}

    if ieee is not None:
        ieee = _validate_ieee(ieee)
        service_data["ieee"] = ieee

    await hass.services.async_call(
        domain="zha",
        service="permit",
        service_data=service_data,
        blocking=True,
    )

    result: dict[str, Any] = {
        "success": True,
        "duration": duration,
        "message": f"Zigbee network joining enabled for {duration} seconds",
    }

    if ieee:
        result["ieee"] = ieee
        result["message"] += f" via device {ieee}"

    return result


@register_tool(
    name="reconfigure_zha_device",
    description="Reconfigure a Zigbee device (re-interview and refresh configuration)",
    parameters=RECONFIGURE_ZHA_DEVICE_SCHEMA,
)
async def reconfigure_zha_device(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Reconfigure a ZHA Zigbee device."""
    _check_zha_loaded(hass)

    ieee = _validate_ieee(arguments["ieee"])

    # Verify device exists before reconfiguring
    gateway = _get_zha_gateway(hass)
    devices_dict = getattr(gateway, "devices", {})
    device_exists = any(
        str(dev.ieee).lower() == ieee.lower() for dev in devices_dict.values()
    )

    if not device_exists:
        raise HomeAssistantError(f"ZHA device not found with IEEE: {ieee}")

    await hass.services.async_call(
        domain="zha",
        service="reconfigure_device",
        service_data={"ieee": ieee},
        blocking=True,
    )

    return {
        "success": True,
        "ieee": ieee,
        "message": f"Reconfiguration initiated for device {ieee}",
    }
