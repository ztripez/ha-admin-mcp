"""Scene CRUD tools."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.scene import PLATFORM_SCHEMA as SCENE_PLATFORM_SCHEMA
from homeassistant.config import SCENE_CONFIG_PATH
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import register_tool
from .common import YAML_CRUD_SCHEMA, async_read_yaml, async_write_yaml, find_list_item

_LOCK = asyncio.Lock()

LIST_SCENES_SCHEMA = vol.Schema({})
GET_SCENE_SCHEMA = vol.Schema({vol.Required("id"): vol.All(str, vol.Length(min=1))})
DELETE_SCENE_SCHEMA = GET_SCENE_SCHEMA


async def _load_scenes(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Load scenes.yaml list."""
    return await async_read_yaml(hass, SCENE_CONFIG_PATH, [])


def _validate_scene_config(config: dict[str, Any]) -> None:
    """Validate one scene config payload."""
    SCENE_PLATFORM_SCHEMA(config)


async def _reload_scenes(hass: HomeAssistant) -> None:
    """Reload scenes from YAML."""
    await hass.services.async_call(SCENE_DOMAIN, SERVICE_RELOAD, blocking=True)


@register_tool(
    name="list_scenes",
    description="List all scenes from scenes.yaml",
    parameters=LIST_SCENES_SCHEMA,
)
async def list_scenes(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return all scenes."""
    del arguments
    scenes = await _load_scenes(hass)
    return {"count": len(scenes), "scenes": scenes}


@register_tool(
    name="get_scene",
    description="Get one scene from scenes.yaml by id",
    parameters=GET_SCENE_SCHEMA,
)
async def get_scene(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return one scene by ID."""
    scene_id: str = arguments["id"]
    scenes = await _load_scenes(hass)

    if (result := find_list_item(scenes, CONF_ID, scene_id)) is None:
        raise HomeAssistantError(f"Scene not found: {scene_id}")

    _, scene = result
    return {"scene": scene}


@register_tool(
    name="create_scene",
    description="Create a new scene in scenes.yaml",
    parameters=YAML_CRUD_SCHEMA,
)
async def create_scene(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create a scene."""
    scene_id: str = arguments["id"]
    config: dict[str, Any] = {CONF_ID: scene_id, **arguments["config"]}
    _validate_scene_config(config)

    async with _LOCK:
        scenes = await _load_scenes(hass)
        if find_list_item(scenes, CONF_ID, scene_id) is not None:
            raise HomeAssistantError(f"Scene already exists: {scene_id}")

        scenes.append(config)
        await async_write_yaml(hass, SCENE_CONFIG_PATH, scenes)

    await _reload_scenes(hass)
    return {"created": scene_id, "scene": config}


@register_tool(
    name="update_scene",
    description="Update an existing scene in scenes.yaml",
    parameters=YAML_CRUD_SCHEMA,
)
async def update_scene(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update a scene."""
    scene_id: str = arguments["id"]
    config: dict[str, Any] = {CONF_ID: scene_id, **arguments["config"]}
    _validate_scene_config(config)

    async with _LOCK:
        scenes = await _load_scenes(hass)
        if (result := find_list_item(scenes, CONF_ID, scene_id)) is None:
            raise HomeAssistantError(f"Scene not found: {scene_id}")

        index, _ = result
        scenes[index] = config
        await async_write_yaml(hass, SCENE_CONFIG_PATH, scenes)

    await _reload_scenes(hass)
    return {"updated": scene_id, "scene": config}


@register_tool(
    name="delete_scene",
    description="Delete a scene from scenes.yaml",
    parameters=DELETE_SCENE_SCHEMA,
)
async def delete_scene(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete a scene by ID."""
    scene_id: str = arguments["id"]

    async with _LOCK:
        scenes = await _load_scenes(hass)
        if (result := find_list_item(scenes, CONF_ID, scene_id)) is None:
            raise HomeAssistantError(f"Scene not found: {scene_id}")

        index, removed = result
        scenes.pop(index)
        await async_write_yaml(hass, SCENE_CONFIG_PATH, scenes)

    ent_reg = er.async_get(hass)
    if entity_id := ent_reg.async_get_entity_id(
        SCENE_DOMAIN, HOMEASSISTANT_DOMAIN, scene_id
    ):
        ent_reg.async_remove(entity_id)

    return {"deleted": scene_id, "scene": removed}
