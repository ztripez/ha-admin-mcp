"""Helper CRUD tools using StorageCollection."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.collection import StorageCollection

from . import register_tool

HELPER_DOMAINS = (
    "input_boolean",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "counter",
    "timer",
)

LIST_HELPERS_SCHEMA = vol.Schema(
    {
        vol.Optional("domain"): vol.In(HELPER_DOMAINS),
    }
)

CREATE_HELPER_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): vol.In(HELPER_DOMAINS),
        vol.Required("data"): dict,
    }
)

UPDATE_HELPER_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): vol.In(HELPER_DOMAINS),
        vol.Required("helper_id"): cv.string,
        vol.Required("data"): dict,
    }
)

DELETE_HELPER_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): vol.In(HELPER_DOMAINS),
        vol.Required("helper_id"): cv.string,
    }
)


def _get_storage_collection(hass: HomeAssistant, domain: str) -> StorageCollection:
    """Resolve a helper domain StorageCollection from websocket registrations."""
    handlers = hass.data.get(websocket_api.DOMAIN)
    if handlers is None:
        raise HomeAssistantError("WebSocket API is not initialized")

    command = f"{domain}/list"
    if command not in handlers:
        raise HomeAssistantError(
            f"Helper domain is not loaded or unsupported: {domain}"
        )

    handler, _ = handlers[command]
    owner = getattr(handler, "__self__", None)
    collection = getattr(owner, "storage_collection", None)

    if collection is None:
        raise HomeAssistantError(f"Could not resolve storage collection for {domain}")

    return collection


def _find_item(items: Iterable[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    """Find one collection item by id."""
    for item in items:
        if item.get("id") == item_id:
            return item
    return None


@register_tool(
    name="list_helpers",
    description="List helper entities managed by storage collections",
    parameters=LIST_HELPERS_SCHEMA,
)
async def list_helpers(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """List helper definitions."""
    if domain := arguments.get("domain"):
        collection = _get_storage_collection(hass, domain)
        items = collection.async_items()
        return {"count": len(items), "domain": domain, "helpers": items}

    result: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for helper_domain in HELPER_DOMAINS:
        collection = _get_storage_collection(hass, helper_domain)
        items = collection.async_items()
        result[helper_domain] = items
        total += len(items)

    return {"count": total, "helpers": result}


@register_tool(
    name="create_helper",
    description="Create a helper for one helper domain",
    parameters=CREATE_HELPER_SCHEMA,
)
async def create_helper(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create a helper item in a helper domain storage collection."""
    domain: str = arguments["domain"]
    data: dict[str, Any] = arguments["data"]

    collection = _get_storage_collection(hass, domain)
    created = await collection.async_create_item(data)
    return {"domain": domain, "helper": created}


@register_tool(
    name="update_helper",
    description="Update a helper item in one helper domain",
    parameters=UPDATE_HELPER_SCHEMA,
)
async def update_helper(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Update a helper item."""
    domain: str = arguments["domain"]
    helper_id: str = arguments["helper_id"]
    data: dict[str, Any] = arguments["data"]

    collection = _get_storage_collection(hass, domain)
    updated = await collection.async_update_item(helper_id, data)
    return {"domain": domain, "helper": updated}


@register_tool(
    name="delete_helper",
    description="Delete a helper item in one helper domain",
    parameters=DELETE_HELPER_SCHEMA,
)
async def delete_helper(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Delete a helper item."""
    domain: str = arguments["domain"]
    helper_id: str = arguments["helper_id"]

    collection = _get_storage_collection(hass, domain)
    items = collection.async_items()
    removed = _find_item(items, helper_id)
    if removed is None:
        raise HomeAssistantError(f"Helper not found: {domain}::{helper_id}")

    await collection.async_delete_item(helper_id)
    return {"domain": domain, "deleted": helper_id, "helper": removed}
