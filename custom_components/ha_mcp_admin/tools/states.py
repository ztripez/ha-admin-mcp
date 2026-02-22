"""State read tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers import entity_registry as er

from . import register_tool
from .common import state_to_dict

GET_STATE_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})

GET_STATES_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_ids"): [cv.entity_id],
        vol.Optional("domain"): cv.string,
        vol.Optional("area_id"): cv.string,
        vol.Optional("include_attributes", default=True): cv.boolean,
    }
)


def _area_entity_ids(hass: HomeAssistant, area_id: str) -> set[str]:
    """Resolve all entity IDs that belong to an area."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    entity_ids = {
        entry.entity_id for entry in er.async_entries_for_area(ent_reg, area_id)
    }

    for device in dr.async_entries_for_area(dev_reg, area_id):
        entity_ids.update(
            entry.entity_id
            for entry in er.async_entries_for_device(ent_reg, device.id)
            if entry.entity_id is not None
        )

    return entity_ids


@register_tool(
    name="get_state",
    description="Get the current state for one entity",
    parameters=GET_STATE_SCHEMA,
)
async def get_state(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return state payload for one entity."""
    entity_id: str = arguments["entity_id"]
    state = hass.states.get(entity_id)
    if state is None:
        raise HomeAssistantError(f"Entity not found: {entity_id}")

    return state_to_dict(state)


@register_tool(
    name="get_states",
    description="Get current states for entities with optional filters",
    parameters=GET_STATES_SCHEMA,
)
async def get_states(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return state payload for many entities."""
    include_attributes: bool = arguments["include_attributes"]
    domain: str | None = arguments.get("domain")
    requested_entity_ids: set[str] | None = None
    area_ids: set[str] | None = None

    if entity_ids := arguments.get("entity_ids"):
        requested_entity_ids = set(entity_ids)

    if area_id := arguments.get("area_id"):
        area_ids = _area_entity_ids(hass, area_id)

    states: list[dict[str, Any]] = []
    for state in hass.states.async_all():
        if domain is not None and split_entity_id(state.entity_id)[0] != domain:
            continue
        if requested_entity_ids is not None and state.entity_id not in requested_entity_ids:
            continue
        if area_ids is not None and state.entity_id not in area_ids:
            continue

        states.append(state_to_dict(state, include_attributes=include_attributes))

    return {"count": len(states), "states": states}
