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
from homeassistant.helpers import entity_registry as er

from . import register_tool
from .common import YAML_CRUD_SCHEMA, async_read_yaml, async_write_yaml, find_list_item

_LOCK = asyncio.Lock()

LIST_AUTOMATIONS_SCHEMA = vol.Schema({})
GET_AUTOMATION_SCHEMA = vol.Schema(
    {vol.Required("id"): vol.All(str, vol.Length(min=1))}
)
DELETE_AUTOMATION_SCHEMA = GET_AUTOMATION_SCHEMA


async def _load_automations(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Load automation YAML list."""
    return await async_read_yaml(hass, AUTOMATION_CONFIG_PATH, [])


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
    parameters=YAML_CRUD_SCHEMA,
)
async def create_automation(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create a new automation."""
    automation_id: str = arguments["id"]
    config: dict[str, Any] = {CONF_ID: automation_id, **arguments["config"]}

    await _validate(hass, automation_id, config)

    async with _LOCK:
        automations = await _load_automations(hass)
        if find_list_item(automations, CONF_ID, automation_id) is not None:
            raise HomeAssistantError(f"Automation already exists: {automation_id}")

        automations.append(config)
        await async_write_yaml(hass, AUTOMATION_CONFIG_PATH, automations)

    await _reload_automation(hass, automation_id)
    return {"created": automation_id, "automation": config}


@register_tool(
    name="update_automation",
    description="Update an existing automation in automations.yaml",
    parameters=YAML_CRUD_SCHEMA,
)
async def update_automation(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update an existing automation."""
    automation_id: str = arguments["id"]
    config: dict[str, Any] = {CONF_ID: automation_id, **arguments["config"]}

    await _validate(hass, automation_id, config)

    async with _LOCK:
        automations = await _load_automations(hass)
        if (result := find_list_item(automations, CONF_ID, automation_id)) is None:
            raise HomeAssistantError(f"Automation not found: {automation_id}")

        index, _ = result
        automations[index] = config
        await async_write_yaml(hass, AUTOMATION_CONFIG_PATH, automations)

    await _reload_automation(hass, automation_id)
    return {"updated": automation_id, "automation": config}


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
