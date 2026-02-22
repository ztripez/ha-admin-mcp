"""Update management tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data, state_to_dict

LIST_PENDING_UPDATES_SCHEMA = vol.Schema({})

GET_UPDATE_INFO_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.string})

INSTALL_UPDATE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.string,
        vol.Optional("version"): cv.string,
        vol.Optional("backup"): cv.boolean,
    }
)

SKIP_UPDATE_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.string})


def _validate_update_entity_id(entity_id: str) -> None:
    """Validate that entity_id is an update entity."""
    if not entity_id.startswith("update."):
        raise HomeAssistantError(
            f"Invalid entity_id: {entity_id}. Must start with 'update.'"
        )


def _extract_update_info(state: Any) -> dict[str, Any]:
    """Extract key update information from a state object."""
    attrs = state.attributes
    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "title": attrs.get("title"),
        "installed_version": attrs.get("installed_version"),
        "latest_version": attrs.get("latest_version"),
        "release_summary": attrs.get("release_summary"),
        "release_url": attrs.get("release_url"),
        "skipped_version": attrs.get("skipped_version"),
    }


@register_tool(
    name="list_pending_updates",
    description=(
        "List all pending updates available in Home Assistant. "
        "Returns only entities where an update is available (state != 'off'). "
        "Includes entity_id, title, installed_version, latest_version, "
        "release_summary, and release_url for each pending update."
    ),
    parameters=LIST_PENDING_UPDATES_SCHEMA,
)
async def list_pending_updates(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List all pending updates."""
    all_updates = hass.states.async_all("update")

    # Filter to only show entities with available updates (state != "off")
    pending_updates = [
        _extract_update_info(state) for state in all_updates if state.state != "off"
    ]

    return {
        "count": len(pending_updates),
        "updates": pending_updates,
        "total_update_entities": len(all_updates),
    }


@register_tool(
    name="get_update_info",
    description=(
        "Get detailed information about a specific update entity. "
        "Returns full state including all attributes such as in_progress, "
        "auto_update, supported_features, release_notes, etc."
    ),
    parameters=GET_UPDATE_INFO_SCHEMA,
)
async def get_update_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get detailed info about a specific update entity."""
    entity_id: str = arguments["entity_id"]
    _validate_update_entity_id(entity_id)

    state = hass.states.get(entity_id)
    if state is None:
        raise HomeAssistantError(f"Update entity not found: {entity_id}")

    return {"update": state_to_dict(state)}


@register_tool(
    name="install_update",
    description=(
        "Install an update for a specific entity. "
        "WARNING: This may cause service interruption if updating Home Assistant Core "
        "or critical integrations. Optionally specify a version to install or create "
        "a backup before updating. The update process may take several minutes."
    ),
    parameters=INSTALL_UPDATE_SCHEMA,
)
async def install_update(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Install an update."""
    entity_id: str = arguments["entity_id"]
    _validate_update_entity_id(entity_id)

    state = hass.states.get(entity_id)
    if state is None:
        raise HomeAssistantError(f"Update entity not found: {entity_id}")

    if state.state == "off":
        raise HomeAssistantError(f"No update available for: {entity_id}")

    # Build service data
    service_data: dict[str, Any] = {}
    if "version" in arguments:
        service_data["version"] = arguments["version"]
    if "backup" in arguments:
        service_data["backup"] = arguments["backup"]

    await hass.services.async_call(
        domain="update",
        service="install",
        service_data=service_data,
        target={"entity_id": entity_id},
        blocking=True,
    )

    # Get updated state after install
    updated_state = hass.states.get(entity_id)
    return {
        "entity_id": entity_id,
        "install_initiated": True,
        "previous_version": state.attributes.get("installed_version"),
        "target_version": arguments.get("version") or state.attributes.get(
            "latest_version"
        ),
        "current_state": normalize_data(
            state_to_dict(updated_state) if updated_state else None
        ),
        "warning": (
            "Update installation initiated. This may cause service interruption. "
            "Monitor the update progress via the update entity state."
        ),
    }


@register_tool(
    name="skip_update",
    description=(
        "Skip/dismiss a pending update. The skipped version will be recorded "
        "and the update will no longer appear as pending until a newer version "
        "is available."
    ),
    parameters=SKIP_UPDATE_SCHEMA,
)
async def skip_update(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Skip a pending update."""
    entity_id: str = arguments["entity_id"]
    _validate_update_entity_id(entity_id)

    state = hass.states.get(entity_id)
    if state is None:
        raise HomeAssistantError(f"Update entity not found: {entity_id}")

    if state.state == "off":
        raise HomeAssistantError(f"No update available to skip for: {entity_id}")

    skipped_version = state.attributes.get("latest_version")

    await hass.services.async_call(
        domain="update",
        service="skip",
        target={"entity_id": entity_id},
        blocking=True,
    )

    return {
        "entity_id": entity_id,
        "skipped": True,
        "skipped_version": skipped_version,
    }
