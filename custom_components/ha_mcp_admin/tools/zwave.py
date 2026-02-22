"""Z-Wave JS management tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data

DOMAIN = "zwave_js"

GET_ZWAVE_NODE_INFO_SCHEMA = vol.Schema({vol.Required("node_id"): vol.Coerce(int)})
HEAL_ZWAVE_NETWORK_SCHEMA = vol.Schema({vol.Optional("node_id"): vol.Coerce(int)})


def _get_zwave_client_and_driver(hass: HomeAssistant) -> tuple[Any, Any, Any]:
    """Get Z-Wave JS client and driver from hass.data.

    Returns tuple of (entry, client, driver).
    Raises HomeAssistantError if Z-Wave JS is not loaded or not ready.
    """
    if DOMAIN not in hass.config.components:
        raise HomeAssistantError(
            "Z-Wave JS integration is not loaded. "
            "Please ensure the zwave_js integration is configured and running."
        )

    # Find Z-Wave JS config entries
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("No Z-Wave JS config entries found.")

    # Get the first loaded entry
    for entry in entries:
        if entry.state.name == "LOADED" and hasattr(entry, "runtime_data"):
            runtime_data = entry.runtime_data
            if runtime_data is None:
                continue

            client = runtime_data.client
            if client is None or not client.connected:
                continue

            driver = client.driver
            if driver is None:
                continue

            return entry, client, driver

    raise HomeAssistantError(
        "Z-Wave JS is not ready. The driver may still be initializing."
    )


def _serialize_node_basic(node: Any) -> dict[str, Any]:
    """Serialize basic node information."""
    return {
        "node_id": node.node_id,
        "name": node.name or node.device_config.description or f"Node {node.node_id}",
        "manufacturer": node.device_config.manufacturer,
        "product_description": node.device_config.description,
        "is_controller_node": node.is_controller_node,
        "status": node.status.name.lower() if hasattr(node.status, "name") else str(node.status),
        "is_secure": node.is_secure,
        "is_beaming": node.is_beaming,
        "is_routing": node.is_routing,
        "firmware_version": node.firmware_version,
        "ready": node.ready,
    }


def _serialize_node_detailed(node: Any) -> dict[str, Any]:
    """Serialize detailed node information."""
    basic = _serialize_node_basic(node)

    # Add endpoint information
    endpoints = []
    for endpoint_idx, endpoint in node.endpoints.items():
        endpoints.append({
            "index": endpoint_idx,
            "installer_icon": endpoint.installer_icon,
            "user_icon": endpoint.user_icon,
        })

    # Add command class information
    command_classes = []
    for cc in node.command_classes:
        command_classes.append({
            "id": cc.id,
            "name": cc.name if hasattr(cc, "name") else str(cc.id),
            "version": cc.version,
            "is_secure": cc.is_secure,
        })

    # Add device class information
    device_class = {
        "basic": node.device_class.basic.label if node.device_class and node.device_class.basic else None,
        "generic": node.device_class.generic.label if node.device_class and node.device_class.generic else None,
        "specific": node.device_class.specific.label if node.device_class and node.device_class.specific else None,
    }

    # Add statistics if available
    statistics = None
    if hasattr(node, "statistics") and node.statistics:
        stats = node.statistics
        statistics = {
            "commands_tx": stats.commands_tx if hasattr(stats, "commands_tx") else None,
            "commands_rx": stats.commands_rx if hasattr(stats, "commands_rx") else None,
            "commands_dropped_tx": stats.commands_dropped_tx if hasattr(stats, "commands_dropped_tx") else None,
            "commands_dropped_rx": stats.commands_dropped_rx if hasattr(stats, "commands_dropped_rx") else None,
            "timeout_response": stats.timeout_response if hasattr(stats, "timeout_response") else None,
        }

    # Build the detailed response
    detailed = {
        **basic,
        "endpoints": endpoints,
        "command_classes": command_classes,
        "device_class": device_class,
        "statistics": statistics,
        "zwave_plus_version": node.zwave_plus_version,
        "zwave_plus_node_type": node.zwave_plus_node_type,
        "zwave_plus_role_type": node.zwave_plus_role_type,
        "manufacturer_id": node.manufacturer_id,
        "product_id": node.product_id,
        "product_type": node.product_type,
        "label": node.device_config.label,
        "interview_stage": node.interview_stage if hasattr(node, "interview_stage") else None,
        "is_listening": node.is_listening,
        "is_frequent_listening": node.is_frequent_listening,
        "highest_security_class": node.highest_security_class.name if node.highest_security_class and hasattr(node.highest_security_class, "name") else None,
        "supports_beaming": node.supports_beaming if hasattr(node, "supports_beaming") else None,
        "database_url": node.device_database_url if hasattr(node, "device_database_url") else None,
    }

    return detailed


@register_tool(
    name="get_zwave_network_status",
    description="Get Z-Wave network status including controller information and node count",
    parameters=vol.Schema({}),
)
async def get_zwave_network_status(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get Z-Wave network status."""
    entry, client, driver = _get_zwave_client_and_driver(hass)
    controller = driver.controller

    # Get controller status
    controller_status = "ready"
    if hasattr(controller, "status"):
        controller_status = controller.status.name.lower() if hasattr(controller.status, "name") else str(controller.status)

    # Get node count
    node_count = len(controller.nodes) if controller.nodes else 0

    # Build response
    result = {
        "controller_status": controller_status,
        "home_id": str(controller.home_id) if controller.home_id else None,
        "home_id_hex": hex(controller.home_id) if controller.home_id else None,
        "node_count": node_count,
        "sdk_version": controller.sdk_version,
        "controller_type": controller.controller_type.name if hasattr(controller.controller_type, "name") else str(controller.controller_type) if controller.controller_type else None,
        "controller_node_id": controller.own_node_id,
        "is_suc": controller.is_suc,
        "is_sis_present": controller.is_SIS_present,
        "is_primary": controller.is_primary,
        "firmware_version": controller.firmware_version,
        "manufacturer_id": controller.manufacturer_id,
        "product_id": controller.product_id,
        "product_type": controller.product_type,
        "is_rebuilding_routes": controller.is_rebuilding_routes,
        "inclusion_state": controller.inclusion_state.name if hasattr(controller.inclusion_state, "name") else str(controller.inclusion_state) if controller.inclusion_state else None,
        "rf_region": controller.rf_region.name if hasattr(controller.rf_region, "name") else str(controller.rf_region) if controller.rf_region else None,
        "supports_long_range": controller.supports_long_range if hasattr(controller, "supports_long_range") else None,
        "client_connected": client.connected,
        "driver_version": client.version.driver_version if client.version else None,
        "server_version": client.version.server_version if client.version else None,
    }

    return normalize_data(result)


@register_tool(
    name="list_zwave_nodes",
    description="List all Z-Wave nodes in the network with their basic information",
    parameters=vol.Schema({}),
)
async def list_zwave_nodes(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List all Z-Wave nodes."""
    entry, client, driver = _get_zwave_client_and_driver(hass)
    controller = driver.controller

    nodes = []
    for node_id, node in controller.nodes.items():
        nodes.append(_serialize_node_basic(node))

    # Sort by node_id
    nodes.sort(key=lambda x: x["node_id"])

    return normalize_data({
        "count": len(nodes),
        "nodes": nodes,
    })


@register_tool(
    name="get_zwave_node_info",
    description="Get detailed information for a specific Z-Wave node including endpoints, command classes, and statistics",
    parameters=GET_ZWAVE_NODE_INFO_SCHEMA,
)
async def get_zwave_node_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get detailed information for a specific Z-Wave node."""
    node_id: int = arguments["node_id"]

    entry, client, driver = _get_zwave_client_and_driver(hass)
    controller = driver.controller

    if node_id not in controller.nodes:
        raise HomeAssistantError(f"Z-Wave node {node_id} not found in network.")

    node = controller.nodes[node_id]
    detailed = _serialize_node_detailed(node)

    return normalize_data({"node": detailed})


@register_tool(
    name="heal_zwave_network",
    description=(
        "Begin healing the Z-Wave network to optimize routing. "
        "WARNING: This process can take a very long time (potentially hours for large networks). "
        "If node_id is provided, only that node will be healed. "
        "Otherwise, the entire network will be healed."
    ),
    parameters=HEAL_ZWAVE_NETWORK_SCHEMA,
)
async def heal_zwave_network(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Begin healing the Z-Wave network."""
    node_id: int | None = arguments.get("node_id")

    entry, client, driver = _get_zwave_client_and_driver(hass)
    controller = driver.controller

    if node_id is not None:
        # Heal a specific node
        if node_id not in controller.nodes:
            raise HomeAssistantError(f"Z-Wave node {node_id} not found in network.")

        node = controller.nodes[node_id]

        # Use rebuild_node_routes for single node healing
        result = await controller.async_rebuild_node_routes(node_id)

        return normalize_data({
            "success": result,
            "message": f"Route rebuild initiated for node {node_id}. This may take several minutes.",
            "node_id": node_id,
        })
    else:
        # Heal the entire network
        if controller.is_rebuilding_routes:
            raise HomeAssistantError(
                "Network healing is already in progress. "
                "Please wait for the current operation to complete."
            )

        # Begin rebuilding routes for the entire network
        result = await controller.async_begin_rebuilding_routes()

        return normalize_data({
            "success": result,
            "message": (
                "Network healing has been initiated. "
                "WARNING: This process can take several hours for large networks. "
                "Nodes will be healed one at a time. "
                "You can check progress using get_zwave_network_status (is_rebuilding_routes field)."
            ),
            "node_count": len(controller.nodes),
        })
