"""Automation CRUD tools."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.automation.config import (  # pylint: disable=hass-component-root-import
    async_validate_config_item,
)
from homeassistant.config import AUTOMATION_CONFIG_PATH
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    category_registry as cr,
    config_validation as cv,
    entity_registry as er,
)

from . import register_tool
from .common import async_read_yaml, async_write_yaml, find_list_item

_LOCK = asyncio.Lock()

LIST_AUTOMATIONS_SCHEMA = vol.Schema({})
GET_AUTOMATION_SCHEMA = vol.Schema(
    {vol.Required("id"): vol.All(str, vol.Length(min=1))}
)
DELETE_AUTOMATION_SCHEMA = GET_AUTOMATION_SCHEMA
AUTOMATION_CRUD_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.string,
        vol.Required("config"): dict,
        vol.Optional("category_id"): vol.Any(None, cv.string),
    }
)


async def _load_automations(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Load automation YAML list."""
    loaded = await async_read_yaml(hass, AUTOMATION_CONFIG_PATH, [])
    if not isinstance(loaded, list):
        raise HomeAssistantError("Expected automations.yaml to contain a list")
    return loaded


async def _validate(
    hass: HomeAssistant, automation_id: str, config: dict[str, Any]
) -> None:
    """Validate one automation config payload."""
    if await async_validate_config_item(hass, automation_id, config) is None:
        raise HomeAssistantError("Automation config validation failed")


async def _reload_automation(hass: HomeAssistant, automation_id: str) -> None:
    """Reload one automation by id."""
    await hass.services.async_call(
        AUTOMATION_DOMAIN,
        SERVICE_RELOAD,
        {CONF_ID: automation_id},
        blocking=True,
    )


def _ensure_automation_category_exists(
    hass: HomeAssistant, category_id: str | None
) -> None:
    """Validate that an automation category exists when provided."""
    if category_id is None:
        return

    registry = cr.async_get(hass)
    if (
        registry.async_get_category(scope=AUTOMATION_DOMAIN, category_id=category_id)
        is None
    ):
        raise HomeAssistantError(
            f"Category not found: {AUTOMATION_DOMAIN}::{category_id}"
        )


def _set_automation_category(
    hass: HomeAssistant, automation_id: str, category_id: str | None
) -> None:
    """Assign or clear the automation category in the entity registry."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        AUTOMATION_DOMAIN, AUTOMATION_DOMAIN, automation_id
    )
    if entity_id is None:
        raise HomeAssistantError(
            f"Automation entity not found for category assignment: {automation_id}"
        )

    entry = entity_registry.async_get(entity_id)
    if entry is None:
        raise HomeAssistantError(
            f"Entity registry entry not found for automation: {automation_id}"
        )

    categories = dict(entry.categories)
    if category_id is None:
        categories.pop(AUTOMATION_DOMAIN, None)
    else:
        categories[AUTOMATION_DOMAIN] = category_id

    try:
        entity_registry.async_update_entity(entity_id, categories=categories)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err


@register_tool(
    name="list_automations",
    description="List all automations from automations.yaml",
    parameters=LIST_AUTOMATIONS_SCHEMA,
)
async def list_automations(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Return all automations."""
    del arguments
    automations = await _load_automations(hass)
    return {"count": len(automations), "automations": automations}


@register_tool(
    name="get_automation",
    description="Get one automation from automations.yaml by id",
    parameters=GET_AUTOMATION_SCHEMA,
)
async def get_automation(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Return one automation by id."""
    automation_id: str = arguments["id"]
    automations = await _load_automations(hass)

    if (result := find_list_item(automations, CONF_ID, automation_id)) is None:
        raise HomeAssistantError(f"Automation not found: {automation_id}")

    _, automation = result
    return {"automation": automation}


@register_tool(
    name="create_automation",
    description="Create a new automation in automations.yaml",
    parameters=AUTOMATION_CRUD_SCHEMA,
)
async def create_automation(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create a new automation."""
    automation_id: str = arguments["id"]
    config: dict[str, Any] = {CONF_ID: automation_id, **arguments["config"]}
    has_category_update = "category_id" in arguments
    category_id: str | None = arguments.get("category_id")

    if has_category_update:
        _ensure_automation_category_exists(hass, category_id)

    await _validate(hass, automation_id, config)

    async with _LOCK:
        automations = await _load_automations(hass)
        if find_list_item(automations, CONF_ID, automation_id) is not None:
            raise HomeAssistantError(f"Automation already exists: {automation_id}")

        automations.append(config)
        await async_write_yaml(hass, AUTOMATION_CONFIG_PATH, automations)

    await _reload_automation(hass, automation_id)
    if has_category_update:
        _set_automation_category(hass, automation_id, category_id)

    response: dict[str, Any] = {"created": automation_id, "automation": config}
    if has_category_update:
        response["category_id"] = category_id
    return response


@register_tool(
    name="update_automation",
    description="Update an existing automation in automations.yaml",
    parameters=AUTOMATION_CRUD_SCHEMA,
)
async def update_automation(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update an existing automation."""
    automation_id: str = arguments["id"]
    config: dict[str, Any] = {CONF_ID: automation_id, **arguments["config"]}
    has_category_update = "category_id" in arguments
    category_id: str | None = arguments.get("category_id")

    if has_category_update:
        _ensure_automation_category_exists(hass, category_id)

    await _validate(hass, automation_id, config)

    async with _LOCK:
        automations = await _load_automations(hass)
        if (result := find_list_item(automations, CONF_ID, automation_id)) is None:
            raise HomeAssistantError(f"Automation not found: {automation_id}")

        index, _ = result
        automations[index] = config
        await async_write_yaml(hass, AUTOMATION_CONFIG_PATH, automations)

    await _reload_automation(hass, automation_id)
    if has_category_update:
        _set_automation_category(hass, automation_id, category_id)

    response: dict[str, Any] = {"updated": automation_id, "automation": config}
    if has_category_update:
        response["category_id"] = category_id
    return response


@register_tool(
    name="delete_automation",
    description="Delete an automation from automations.yaml",
    parameters=DELETE_AUTOMATION_SCHEMA,
)
async def delete_automation(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete an automation by id."""
    automation_id: str = arguments["id"]

    async with _LOCK:
        automations = await _load_automations(hass)
        if (result := find_list_item(automations, CONF_ID, automation_id)) is None:
            raise HomeAssistantError(f"Automation not found: {automation_id}")

        index, removed = result
        automations.pop(index)
        await async_write_yaml(hass, AUTOMATION_CONFIG_PATH, automations)

    ent_reg = er.async_get(hass)
    if entity_id := ent_reg.async_get_entity_id(
        AUTOMATION_DOMAIN, AUTOMATION_DOMAIN, automation_id
    ):
        ent_reg.async_remove(entity_id)

    return {"deleted": automation_id, "automation": removed}
