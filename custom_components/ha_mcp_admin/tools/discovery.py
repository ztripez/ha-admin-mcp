"""Network discovery tools for HA MCP Admin."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant

from . import register_tool
from .common import normalize_data

# All discovery tools take no parameters
EMPTY_SCHEMA = vol.Schema({})


@register_tool(
    name="get_dhcp_discoveries",
    description="Get DHCP-discovered devices on the network",
    parameters=EMPTY_SCHEMA,
)
async def get_dhcp_discoveries(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get DHCP-discovered devices."""
    # DHCP component stores discovery data in hass.data
    dhcp_data = hass.data.get("dhcp")

    if dhcp_data is None:
        return {
            "available": False,
            "message": "DHCP discovery not available - component not loaded",
            "devices": [],
        }

    devices: list[dict[str, Any]] = []

    # The DHCP component stores a DHCPWatcher instance
    # which has a _discoveries dict or similar structure
    watcher = dhcp_data.get("watcher") if isinstance(dhcp_data, dict) else dhcp_data

    if hasattr(watcher, "discoveries"):
        # Access the discoveries attribute if available
        for discovery in watcher.discoveries:
            device_info = {
                "mac": getattr(discovery, "macaddress", None),
                "hostname": getattr(discovery, "hostname", None),
                "ip": getattr(discovery, "ip", None),
            }
            devices.append(normalize_data(device_info))
    elif hasattr(watcher, "_discoveries"):
        # Try private attribute
        for key, discovery in watcher._discoveries.items():
            device_info = {
                "mac": getattr(discovery, "macaddress", str(key)),
                "hostname": getattr(discovery, "hostname", None),
                "ip": getattr(discovery, "ip", None),
            }
            devices.append(normalize_data(device_info))
    elif isinstance(dhcp_data, dict):
        # Try to extract any discovery-like data from dict structure
        for key, value in dhcp_data.items():
            if key != "watcher" and isinstance(value, dict):
                devices.append(normalize_data(value))

    return {
        "available": True,
        "count": len(devices),
        "devices": devices,
    }


@register_tool(
    name="get_ssdp_discoveries",
    description="Get SSDP/UPnP discovered services on the network",
    parameters=EMPTY_SCHEMA,
)
async def get_ssdp_discoveries(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get SSDP/UPnP discovered services."""
    ssdp_data = hass.data.get("ssdp")

    if ssdp_data is None:
        return {
            "available": False,
            "message": "SSDP discovery not available - component not loaded",
            "services": [],
        }

    services: list[dict[str, Any]] = []

    # SSDP component uses a Scanner class that tracks discovered devices
    scanner = ssdp_data.get("scanner") if isinstance(ssdp_data, dict) else ssdp_data

    if hasattr(scanner, "async_get_discovery_info_by_st"):
        # Newer API - get all service types
        try:
            # This would require knowing the STs, so try cache instead
            if hasattr(scanner, "_ssdp_devices"):
                for usn, device in scanner._ssdp_devices.items():
                    service_info = {
                        "usn": usn,
                        "st": getattr(device, "st", None),
                        "location": getattr(device, "location", None),
                        "manufacturer": getattr(device, "manufacturer", None),
                        "model_name": getattr(device, "model_name", None),
                        "model_number": getattr(device, "model_number", None),
                        "friendly_name": getattr(device, "friendly_name", None),
                        "serial_number": getattr(device, "serial_number", None),
                    }
                    services.append(normalize_data(service_info))
        except Exception:
            pass

    if hasattr(scanner, "cache") and not services:
        # Try accessing the cache
        for key, info in scanner.cache.items():
            if isinstance(info, dict):
                services.append(normalize_data(info))
            else:
                service_info = {
                    "usn": getattr(info, "usn", str(key)),
                    "st": getattr(info, "st", getattr(info, "ssdp_st", None)),
                    "location": getattr(
                        info, "location", getattr(info, "ssdp_location", None)
                    ),
                    "manufacturer": getattr(info, "manufacturer", None),
                    "model_name": getattr(info, "model_name", None),
                    "friendly_name": getattr(info, "friendly_name", None),
                }
                services.append(normalize_data(service_info))

    if isinstance(ssdp_data, dict) and not services:
        # Fallback: try to extract data from dict structure
        for key, value in ssdp_data.items():
            if key not in ("scanner", "browser") and isinstance(value, (dict, list)):
                if isinstance(value, dict):
                    services.append(normalize_data(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            services.append(normalize_data(item))

    return {
        "available": True,
        "count": len(services),
        "services": services,
    }


@register_tool(
    name="get_zeroconf_discoveries",
    description="Get mDNS/Zeroconf discovered services on the network",
    parameters=EMPTY_SCHEMA,
)
async def get_zeroconf_discoveries(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get mDNS/Zeroconf discovered services."""
    zeroconf_data = hass.data.get("zeroconf")

    if zeroconf_data is None:
        return {
            "available": False,
            "message": "Zeroconf discovery not available - component not loaded",
            "services": [],
        }

    services: list[dict[str, Any]] = []

    # Zeroconf component stores browser instances and discovered services
    if isinstance(zeroconf_data, dict):
        # Try to find browser or discovery data
        browser = zeroconf_data.get("browser") or zeroconf_data.get("zeroconf")

        if hasattr(browser, "async_get_service_info"):
            # Newer API with async service info
            pass

        if hasattr(browser, "_service_infos"):
            # Access cached service infos
            for key, info in browser._service_infos.items():
                service_info = {
                    "type": getattr(info, "type", None),
                    "name": getattr(info, "name", str(key)),
                    "host": getattr(info, "server", getattr(info, "host", None)),
                    "port": getattr(info, "port", None),
                    "properties": normalize_data(
                        getattr(info, "properties", {}) or {}
                    ),
                    "addresses": [
                        str(addr) for addr in (getattr(info, "addresses", []) or [])
                    ],
                }
                services.append(normalize_data(service_info))

        if hasattr(browser, "services") and not services:
            # Try services attribute
            for service_type, service_list in browser.services.items():
                for service in service_list:
                    service_info = {
                        "type": service_type,
                        "name": getattr(service, "name", str(service)),
                        "host": getattr(service, "server", None),
                        "port": getattr(service, "port", None),
                    }
                    services.append(normalize_data(service_info))

        # Check for discovery entries in the dict
        if not services:
            for key, value in zeroconf_data.items():
                if key not in ("zeroconf", "browser", "instance") and isinstance(
                    value, (dict, list)
                ):
                    if isinstance(value, dict):
                        services.append(normalize_data(value))
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                services.append(normalize_data(item))

    return {
        "available": True,
        "count": len(services),
        "services": services,
    }


@register_tool(
    name="get_usb_devices",
    description="Get connected USB devices detected by Home Assistant",
    parameters=EMPTY_SCHEMA,
)
async def get_usb_devices(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get connected USB devices."""
    usb_data = hass.data.get("usb")

    if usb_data is None:
        return {
            "available": False,
            "message": "USB discovery not available - component not loaded",
            "devices": [],
        }

    devices: list[dict[str, Any]] = []

    # USB component uses a USBDiscovery class
    discovery = usb_data.get("discovery") if isinstance(usb_data, dict) else usb_data

    if hasattr(discovery, "usb"):
        # Access USB device list
        for device in discovery.usb:
            device_info = {
                "device": getattr(device, "device", None),
                "vid": getattr(device, "vid", getattr(device, "vendor_id", None)),
                "pid": getattr(device, "pid", getattr(device, "product_id", None)),
                "serial_number": getattr(device, "serial_number", None),
                "manufacturer": getattr(device, "manufacturer", None),
                "description": getattr(device, "description", None),
            }
            devices.append(normalize_data(device_info))

    if hasattr(discovery, "_usb_info") and not devices:
        # Try private attribute
        for device in discovery._usb_info:
            device_info = {
                "device": getattr(device, "device", None),
                "vid": getattr(device, "vid", None),
                "pid": getattr(device, "pid", None),
                "serial_number": getattr(device, "serial_number", None),
                "manufacturer": getattr(device, "manufacturer", None),
                "description": getattr(device, "description", None),
            }
            devices.append(normalize_data(device_info))

    if hasattr(discovery, "scan") and not devices:
        # Try to get devices via scan method result cache
        if hasattr(discovery, "_scanned_devices"):
            for device in discovery._scanned_devices:
                device_info = {
                    "device": getattr(device, "device", str(device)),
                    "vid": getattr(device, "vid", None),
                    "pid": getattr(device, "pid", None),
                    "serial_number": getattr(device, "serial_number", None),
                    "manufacturer": getattr(device, "manufacturer", None),
                    "description": getattr(device, "description", None),
                }
                devices.append(normalize_data(device_info))

    if isinstance(usb_data, dict) and not devices:
        # Fallback: extract from dict structure
        for key, value in usb_data.items():
            if key != "discovery" and isinstance(value, (dict, list)):
                if isinstance(value, dict):
                    devices.append(normalize_data(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            devices.append(normalize_data(item))

    return {
        "available": True,
        "count": len(devices),
        "devices": devices,
    }


@register_tool(
    name="get_bluetooth_devices",
    description="Get Bluetooth/BLE devices discovered by Home Assistant",
    parameters=EMPTY_SCHEMA,
)
async def get_bluetooth_devices(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get Bluetooth/BLE discovered devices."""
    bluetooth_data = hass.data.get("bluetooth")

    if bluetooth_data is None:
        return {
            "available": False,
            "message": "Bluetooth discovery not available - component not loaded",
            "devices": [],
        }

    devices: list[dict[str, Any]] = []

    # Bluetooth component uses BluetoothManager
    manager = (
        bluetooth_data.get("manager") if isinstance(bluetooth_data, dict) else None
    )

    # Try to access via the manager's scanner or device tracking
    if manager is not None:
        if hasattr(manager, "scanner"):
            scanner = manager.scanner
            if hasattr(scanner, "discovered_devices"):
                for address, device in scanner.discovered_devices.items():
                    device_info = {
                        "address": address,
                        "name": getattr(device, "name", None),
                        "rssi": getattr(device, "rssi", None),
                        "manufacturer_data": normalize_data(
                            getattr(device, "manufacturer_data", {}) or {}
                        ),
                        "service_uuids": list(
                            getattr(device, "service_uuids", []) or []
                        ),
                        "service_data": normalize_data(
                            getattr(device, "service_data", {}) or {}
                        ),
                    }
                    devices.append(normalize_data(device_info))

        if hasattr(manager, "async_discovered_devices") and not devices:
            # Try getting via async method if available (would need to call)
            pass

        if hasattr(manager, "_discovered_devices") and not devices:
            for address, device in manager._discovered_devices.items():
                device_info = {
                    "address": address,
                    "name": getattr(device, "name", None),
                    "rssi": getattr(device, "rssi", None),
                }
                devices.append(normalize_data(device_info))

    # Try alternate data structures
    if isinstance(bluetooth_data, dict) and not devices:
        # Check for scanners dict
        scanners = bluetooth_data.get("scanners", {})
        for scanner_id, scanner in scanners.items():
            if hasattr(scanner, "discovered_devices"):
                for address, device in scanner.discovered_devices.items():
                    device_info = {
                        "address": address,
                        "name": getattr(device, "name", None),
                        "rssi": getattr(device, "rssi", None),
                        "scanner": scanner_id,
                    }
                    devices.append(normalize_data(device_info))

        # Check for history/cache
        if hasattr(bluetooth_data, "get"):
            history = bluetooth_data.get("history", {})
            for address, info in history.items():
                device_info = {
                    "address": address,
                    "name": info.get("name") if isinstance(info, dict) else None,
                    "rssi": info.get("rssi") if isinstance(info, dict) else None,
                    "last_seen": (
                        info.get("last_seen") if isinstance(info, dict) else None
                    ),
                }
                devices.append(normalize_data(device_info))

    # Try to use bluetooth integration's API directly if available
    try:
        from homeassistant.components.bluetooth import async_discovered_service_info

        service_infos = async_discovered_service_info(hass)
        if service_infos and not devices:
            for info in service_infos:
                device_info = {
                    "address": info.address,
                    "name": info.name,
                    "rssi": info.rssi,
                    "manufacturer_data": normalize_data(info.manufacturer_data or {}),
                    "service_uuids": list(info.service_uuids or []),
                    "service_data": normalize_data(info.service_data or {}),
                    "source": info.source,
                    "connectable": info.connectable,
                }
                devices.append(normalize_data(device_info))
    except (ImportError, AttributeError):
        # Bluetooth component API not available or different version
        pass

    # Deduplicate by address
    seen_addresses: set[str] = set()
    unique_devices: list[dict[str, Any]] = []
    for device in devices:
        address = device.get("address")
        if address and address not in seen_addresses:
            seen_addresses.add(address)
            unique_devices.append(device)

    return {
        "available": True,
        "count": len(unique_devices),
        "devices": unique_devices,
    }
