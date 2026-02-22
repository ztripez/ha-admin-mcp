"""Script CRUD tools."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.script.config import (  # pylint: disable=hass-component-root-import
    async_validate_config_item,
)
from homeassistant.config import SCRIPT_CONFIG_PATH
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from . import register_tool
from .common import async_read_yaml, async_write_yaml

_LOCK = asyncio.Lock()

LIST_SCRIPTS_SCHEMA = vol.Schema({})
GET_SCRIPT_SCHEMA = vol.Schema({vol.Required("id"): cv.slug})
CREATE_SCRIPT_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.slug,
        vol.Required("config"): dict,
    }
)
UPDATE_SCRIPT_SCHEMA = CREATE_SCRIPT_SCHEMA
DELETE_SCRIPT_SCHEMA = vol.Schema({vol.Required("id"): cv.slug})


async def _load_scripts(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Load scripts.yaml contents."""
    data = await async_read_yaml(hass, SCRIPT_CONFIG_PATH, {})
    return data


async def _validate(hass: HomeAssistant, script_id: str, config: dict[str, Any]) -> None:
    """Validate one script config payload."""
    if await async_validate_config_item(hass, script_id, config) is None:
        raise HomeAssistantError("Script config validation failed")


async def _reload_scripts(hass: HomeAssistant) -> None:
    """Reload scripts from YAML."""
    await hass.services.async_call(
        SCRIPT_DOMAIN,
        SERVICE_RELOAD,
        blocking=True,
    )


@register_tool(
    name="list_scripts",
    description="List all scripts from scripts.yaml",
    parameters=LIST_SCRIPTS_SCHEMA,
)
async def list_scripts(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return all scripts."""
    del arguments
    scripts = await _load_scripts(hass)
    return {"count": len(scripts), "scripts": scripts}


@register_tool(
    name="get_script",
    description="Get one script from scripts.yaml by ID",
    parameters=GET_SCRIPT_SCHEMA,
)
async def get_script(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return one script by ID."""
    script_id: str = arguments["id"]
    scripts = await _load_scripts(hass)

    if script_id not in scripts:
        raise HomeAssistantError(f"Script not found: {script_id}")

    return {"script": scripts[script_id]}


@register_tool(
    name="create_script",
    description="Create a new script in scripts.yaml",
    parameters=CREATE_SCRIPT_SCHEMA,
)
async def create_script(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create a script."""
    script_id: str = arguments["id"]
    config: dict[str, Any] = arguments["config"]

    await _validate(hass, script_id, config)

    async with _LOCK:
        scripts = await _load_scripts(hass)
        if script_id in scripts:
            raise HomeAssistantError(f"Script already exists: {script_id}")

        scripts[script_id] = config
        await async_write_yaml(hass, SCRIPT_CONFIG_PATH, scripts)

    await _reload_scripts(hass)
    return {"created": script_id, "script": config}


@register_tool(
    name="update_script",
    description="Update an existing script in scripts.yaml",
    parameters=UPDATE_SCRIPT_SCHEMA,
)
async def update_script(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Update a script."""
    script_id: str = arguments["id"]
    config: dict[str, Any] = arguments["config"]

    await _validate(hass, script_id, config)

    async with _LOCK:
        scripts = await _load_scripts(hass)
        if script_id not in scripts:
            raise HomeAssistantError(f"Script not found: {script_id}")

        scripts[script_id] = config
        await async_write_yaml(hass, SCRIPT_CONFIG_PATH, scripts)

    await _reload_scripts(hass)
    return {"updated": script_id, "script": config}


@register_tool(
    name="delete_script",
    description="Delete a script from scripts.yaml",
    parameters=DELETE_SCRIPT_SCHEMA,
)
async def delete_script(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Delete a script."""
    script_id: str = arguments["id"]

    async with _LOCK:
        scripts = await _load_scripts(hass)
        if script_id not in scripts:
            raise HomeAssistantError(f"Script not found: {script_id}")

        removed = scripts.pop(script_id)
        await async_write_yaml(hass, SCRIPT_CONFIG_PATH, scripts)

    ent_reg = er.async_get(hass)
    if entity_id := ent_reg.async_get_entity_id(SCRIPT_DOMAIN, SCRIPT_DOMAIN, script_id):
        ent_reg.async_remove(entity_id)

    return {"deleted": script_id, "script": removed}
