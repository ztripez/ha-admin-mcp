"""Group CRUD tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data

LIST_GROUPS_SCHEMA = vol.Schema({})

GROUP_SET_SCHEMA = vol.Schema(
    {
        vol.Required("object_id"): cv.slug,
        vol.Optional("name"): cv.string,
        vol.Optional("icon"): cv.icon,
        vol.Optional("all"): cv.boolean,
        vol.Optional("entities"): [cv.entity_id],
        vol.Optional("add_entities"): [cv.entity_id],
        vol.Optional("remove_entities"): [cv.entity_id],
    }
)

DELETE_GROUP_SCHEMA = vol.Schema({vol.Required("object_id"): cv.slug})


@register_tool(
    name="list_groups",
    description="List group entities and their attributes",
    parameters=LIST_GROUPS_SCHEMA,
)
async def list_groups(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """List all states in the group domain."""
    del arguments
    groups: list[dict[str, Any]] = []
    for state in hass.states.async_all():
        if split_entity_id(state.entity_id)[0] != GROUP_DOMAIN:
            continue
        groups.append(
            {
                "entity_id": state.entity_id,
                "state": state.state,
                "attributes": normalize_data(state.attributes),
            }
        )

    return {"count": len(groups), "groups": groups}


@register_tool(
    name="create_group",
    description="Create a group.group entity using group.set",
    parameters=GROUP_SET_SCHEMA,
)
async def create_group(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create or update a group with group.set."""
    await hass.services.async_call(
        GROUP_DOMAIN,
        "set",
        service_data=arguments,
        blocking=True,
    )
    object_id: str = arguments["object_id"]
    entity_id = f"group.{object_id}"
    state = hass.states.get(entity_id)
    if state is None:
        raise HomeAssistantError(f"Group was not created: {entity_id}")

    return {
        "entity_id": entity_id,
        "state": state.state,
        "attributes": normalize_data(state.attributes),
    }


@register_tool(
    name="update_group",
    description="Update a group.group entity using group.set",
    parameters=GROUP_SET_SCHEMA,
)
async def update_group(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Update a group with group.set."""
    return await create_group(hass, arguments)


@register_tool(
    name="delete_group",
    description="Delete a group.group entity using group.remove",
    parameters=DELETE_GROUP_SCHEMA,
)
async def delete_group(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Delete a group by object ID."""
    object_id: str = arguments["object_id"]
    entity_id = f"group.{object_id}"
    if hass.states.get(entity_id) is None:
        raise HomeAssistantError(f"Group not found: {entity_id}")

    await hass.services.async_call(
        GROUP_DOMAIN,
        "remove",
        service_data={"object_id": object_id},
        blocking=True,
    )

    return {"deleted": entity_id}
