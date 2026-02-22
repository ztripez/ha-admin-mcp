"""MQTT tools for Home Assistant MCP Admin."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data, redact_data

# Constants
MQTT_DOMAIN = "mqtt"
DATA_MQTT = "mqtt"
DATA_MQTT_CLIENT = "mqtt_client"

# Schemas
GET_MQTT_STATUS_SCHEMA = vol.Schema({})
PUBLISH_MQTT_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("topic"): cv.string,
        vol.Required("payload"): cv.string,
        vol.Optional("qos", default=0): vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
        vol.Optional("retain", default=False): cv.boolean,
    }
)
GET_MQTT_DEBUG_INFO_SCHEMA = vol.Schema({})


def _check_mqtt_loaded(hass: HomeAssistant) -> None:
    """Check if MQTT integration is loaded and raise error if not."""
    if MQTT_DOMAIN not in hass.config.components:
        raise HomeAssistantError(
            "MQTT integration is not loaded. "
            "Please configure the MQTT integration in Home Assistant."
        )


def _get_mqtt_data(hass: HomeAssistant) -> dict[str, Any] | None:
    """Get MQTT component data from hass.data."""
    return hass.data.get(DATA_MQTT)


def _redact_broker_info(broker: str | None) -> str | None:
    """Redact broker hostname if it contains credentials."""
    if broker is None:
        return None
    # Check if broker contains embedded credentials (user:pass@host format)
    if "@" in broker:
        # Redact the credentials portion
        at_index = broker.rfind("@")
        return "**redacted**@" + broker[at_index + 1 :]
    return broker


@register_tool(
    name="get_mqtt_status",
    description="Get MQTT connection status and configuration",
    parameters=GET_MQTT_STATUS_SCHEMA,
)
async def get_mqtt_status(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get MQTT connection status.

    Returns information about the MQTT connection including
    connection state, broker info, and client configuration.
    """
    _check_mqtt_loaded(hass)

    mqtt_data = _get_mqtt_data(hass)

    # Basic status when MQTT is loaded but data structure varies
    status: dict[str, Any] = {
        "loaded": True,
        "connected": False,
    }

    if mqtt_data is None:
        status["message"] = "MQTT is loaded but client data is not available"
        return status

    # Try to extract client information from mqtt_data
    # The structure can vary between HA versions
    try:
        # In newer HA versions, mqtt_data is typically an MQTTComponent instance
        client = getattr(mqtt_data, "client", None)

        if client is not None:
            # Extract connection status
            status["connected"] = getattr(client, "connected", False)

            # Extract broker configuration (redact sensitive info)
            conf = getattr(client, "conf", {}) or {}
            if conf:
                status["broker"] = _redact_broker_info(conf.get("broker"))
                status["port"] = conf.get("port")
                status["client_id"] = conf.get("client_id")
                status["protocol"] = conf.get("protocol")
                status["keepalive"] = conf.get("keepalive")

                # Redact any auth-related fields
                if "username" in conf:
                    status["username"] = "**configured**"

            # Birth message status
            birth_message = getattr(client, "_birth_message", None)
            if birth_message is not None:
                status["birth_message_configured"] = True

        # Alternative: check entry data from config entries
        entries = hass.config_entries.async_entries(MQTT_DOMAIN)
        if entries:
            entry = entries[0]
            entry_data = redact_data(dict(entry.data))
            status["config_entry_id"] = entry.entry_id
            status["config_entry_state"] = entry.state.value

            # Extract non-sensitive broker info from entry if not already set
            if "broker" not in status and "broker" in entry.data:
                status["broker"] = _redact_broker_info(entry.data.get("broker"))
            if "port" not in status and "port" in entry.data:
                status["port"] = entry.data.get("port")

    except Exception as err:  # noqa: BLE001
        status["warning"] = f"Could not retrieve full MQTT status: {err}"

    return normalize_data(status)


@register_tool(
    name="publish_mqtt_message",
    description="Publish a message to an MQTT topic",
    parameters=PUBLISH_MQTT_MESSAGE_SCHEMA,
)
async def publish_mqtt_message(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Publish a message to an MQTT topic.

    Publishes the specified payload to the given MQTT topic with
    optional QoS level and retain flag.
    """
    _check_mqtt_loaded(hass)

    topic: str = arguments["topic"]
    payload: str = arguments["payload"]
    qos: int = arguments.get("qos", 0)
    retain: bool = arguments.get("retain", False)

    # Validate topic doesn't start with $ (system topics)
    if topic.startswith("$"):
        raise HomeAssistantError(
            f"Cannot publish to system topic: {topic}. "
            "Topics starting with '$' are reserved for system use."
        )

    # Validate topic is not empty and doesn't have invalid characters
    if not topic or topic.isspace():
        raise HomeAssistantError("Topic cannot be empty or whitespace only.")

    # Check if mqtt.publish service is available
    if not hass.services.has_service(MQTT_DOMAIN, "publish"):
        raise HomeAssistantError(
            "MQTT publish service is not available. "
            "Ensure MQTT integration is properly configured."
        )

    # Call the MQTT publish service
    await hass.services.async_call(
        MQTT_DOMAIN,
        "publish",
        {
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "retain": retain,
        },
        blocking=True,
    )

    return {
        "status": "published",
        "topic": topic,
        "payload_length": len(payload),
        "qos": qos,
        "retain": retain,
        "message": f"Message published to topic '{topic}' successfully.",
    }


@register_tool(
    name="get_mqtt_debug_info",
    description="Get MQTT debug information including subscriptions and statistics",
    parameters=GET_MQTT_DEBUG_INFO_SCHEMA,
)
async def get_mqtt_debug_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get MQTT debug information.

    Returns debug information about the MQTT integration including
    subscription counts, discovery configuration, and message statistics
    when available.
    """
    _check_mqtt_loaded(hass)

    mqtt_data = _get_mqtt_data(hass)

    debug_info: dict[str, Any] = {
        "available": True,
    }

    if mqtt_data is None:
        debug_info["available"] = False
        debug_info["message"] = "MQTT debug data is not accessible"
        return debug_info

    try:
        # Try to get client information
        client = getattr(mqtt_data, "client", None)

        if client is not None:
            # Subscription information
            subscriptions = getattr(client, "subscriptions", None)
            if subscriptions is not None:
                if isinstance(subscriptions, dict):
                    debug_info["subscription_count"] = len(subscriptions)
                    # List subscription topics (not the callbacks)
                    debug_info["subscribed_topics"] = list(subscriptions.keys())[:50]
                    if len(subscriptions) > 50:
                        debug_info["subscribed_topics_truncated"] = True
                elif hasattr(subscriptions, "__len__"):
                    debug_info["subscription_count"] = len(subscriptions)

            # Message statistics if available
            msg_sent = getattr(client, "_messages_sent", None)
            msg_received = getattr(client, "_messages_received", None)
            if msg_sent is not None:
                debug_info["messages_sent"] = msg_sent
            if msg_received is not None:
                debug_info["messages_received"] = msg_received

            # Last will configuration
            will = getattr(client, "_will", None) or getattr(client, "will", None)
            if will is not None:
                debug_info["last_will_configured"] = True
                if isinstance(will, dict):
                    debug_info["last_will_topic"] = will.get("topic")

            # Connection info
            debug_info["connected"] = getattr(client, "connected", False)

        # Discovery information from config entry
        entries = hass.config_entries.async_entries(MQTT_DOMAIN)
        if entries:
            entry = entries[0]
            options = entry.options or {}
            data = entry.data or {}

            # Discovery prefix
            discovery_prefix = options.get("discovery_prefix") or data.get(
                "discovery_prefix"
            )
            if discovery_prefix:
                debug_info["discovery_prefix"] = discovery_prefix

            # Discovery enabled
            discovery = options.get("discovery") or data.get("discovery")
            if discovery is not None:
                debug_info["discovery_enabled"] = discovery

            # Birth message config
            birth_message = options.get("birth_message") or data.get("birth_message")
            if birth_message:
                debug_info["birth_message"] = {
                    "topic": birth_message.get("topic"),
                    "qos": birth_message.get("qos"),
                    "retain": birth_message.get("retain"),
                }

            # Will message config (LWT)
            will_message = options.get("will_message") or data.get("will_message")
            if will_message:
                debug_info["will_message"] = {
                    "topic": will_message.get("topic"),
                    "qos": will_message.get("qos"),
                    "retain": will_message.get("retain"),
                }

        # Check for any debug data registered by MQTT component
        mqtt_debug = hass.data.get("mqtt_debug_info")
        if mqtt_debug:
            debug_info["component_debug"] = normalize_data(mqtt_debug)

    except Exception as err:  # noqa: BLE001
        debug_info["warning"] = f"Could not retrieve full debug info: {err}"

    return normalize_data(debug_info)
