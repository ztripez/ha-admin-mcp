"""Backup management tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data


def _get_backup_manager(hass: HomeAssistant) -> Any:
    """Get the backup manager, raising if unavailable."""
    # Import here to avoid import errors if backup component isn't loaded
    from homeassistant.components.backup import async_get_manager  # noqa: PLC0415

    return async_get_manager(hass)


def _serialize_backup(backup: Any) -> dict[str, Any]:
    """Serialize a ManagerBackup to a dict."""
    return normalize_data(
        {
            "backup_id": backup.backup_id,
            "name": backup.name,
            "date": backup.date,
            "homeassistant_version": backup.homeassistant_version,
            "homeassistant_included": backup.homeassistant_included,
            "database_included": backup.database_included,
            "folders": [str(f) for f in backup.folders],
            "addons": [
                {"name": addon.name, "slug": addon.slug, "version": addon.version}
                for addon in backup.addons
            ],
            "agents": {
                agent_id: {"protected": status.protected, "size": status.size}
                for agent_id, status in backup.agents.items()
            },
            "failed_addons": [
                {"name": addon.name, "slug": addon.slug, "version": addon.version}
                for addon in backup.failed_addons
            ],
            "failed_agent_ids": backup.failed_agent_ids,
            "failed_folders": [str(f) for f in backup.failed_folders],
            "with_automatic_settings": backup.with_automatic_settings,
            "extra_metadata": backup.extra_metadata,
        }
    )


LIST_BACKUPS_SCHEMA = vol.Schema({})

GET_BACKUP_INFO_SCHEMA = vol.Schema({vol.Required("backup_id"): cv.string})

CREATE_BACKUP_SCHEMA = vol.Schema(
    {
        vol.Optional("name"): cv.string,
        vol.Optional("include_addons", default=True): cv.boolean,
        vol.Optional("include_database", default=True): cv.boolean,
        vol.Optional("include_folders"): vol.All(cv.ensure_list, [cv.string]),
    }
)

DELETE_BACKUP_SCHEMA = vol.Schema({vol.Required("backup_id"): cv.string})


@register_tool(
    name="list_backups",
    description="List all available backups with metadata (id, name, date, size, agents)",
    parameters=LIST_BACKUPS_SCHEMA,
)
async def list_backups(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List all available backups."""
    manager = _get_backup_manager(hass)

    backups, agent_errors = await manager.async_get_backups()

    payload = [_serialize_backup(backup) for backup in backups.values()]

    result: dict[str, Any] = {"count": len(payload), "backups": payload}
    if agent_errors:
        result["agent_errors"] = {
            agent_id: str(err) for agent_id, err in agent_errors.items()
        }

    return result


@register_tool(
    name="get_backup_info",
    description="Get details of a specific backup including contents and agent status",
    parameters=GET_BACKUP_INFO_SCHEMA,
)
async def get_backup_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get details of a specific backup."""
    backup_id: str = arguments["backup_id"]
    manager = _get_backup_manager(hass)

    backup, agent_errors = await manager.async_get_backup(backup_id)

    if backup is None:
        raise HomeAssistantError(f"Backup not found: {backup_id}")

    result: dict[str, Any] = {"backup": _serialize_backup(backup)}
    if agent_errors:
        result["agent_errors"] = {
            agent_id: str(err) for agent_id, err in agent_errors.items()
        }

    return result


@register_tool(
    name="create_backup",
    description=(
        "Create a new backup. This is a long-running operation that creates a backup "
        "of Home Assistant configuration. The backup will be stored according to "
        "configured backup agents."
    ),
    parameters=CREATE_BACKUP_SCHEMA,
)
async def create_backup(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create a new backup."""
    manager = _get_backup_manager(hass)

    # Get available agents
    agent_ids = list(manager.backup_agents.keys())
    if not agent_ids:
        raise HomeAssistantError("No backup agents available")

    # Build folder list if specified
    include_folders = None
    if "include_folders" in arguments:
        from homeassistant.components.backup.models import Folder  # noqa: PLC0415

        include_folders = []
        for folder_str in arguments["include_folders"]:
            try:
                include_folders.append(Folder(folder_str))
            except ValueError as err:
                raise HomeAssistantError(
                    f"Invalid folder '{folder_str}'. Valid options: "
                    f"{', '.join(f.value for f in Folder)}"
                ) from err

    try:
        new_backup = await manager.async_create_backup(
            agent_ids=agent_ids,
            name=arguments.get("name"),
            include_addons=None,  # None means include based on include_all_addons
            include_all_addons=arguments.get("include_addons", True),
            include_database=arguments.get("include_database", True),
            include_folders=include_folders,
            include_homeassistant=True,
            password=None,
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to create backup: {err}") from err

    return {
        "backup_job_id": new_backup.backup_job_id,
        "message": "Backup creation initiated",
    }


@register_tool(
    name="delete_backup",
    description=(
        "Delete a backup. WARNING: This permanently removes the backup from all "
        "backup agents. This action cannot be undone and may result in data loss."
    ),
    parameters=DELETE_BACKUP_SCHEMA,
)
async def delete_backup(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete a backup."""
    backup_id: str = arguments["backup_id"]
    manager = _get_backup_manager(hass)

    # Verify backup exists first
    backup, _ = await manager.async_get_backup(backup_id)
    if backup is None:
        raise HomeAssistantError(f"Backup not found: {backup_id}")

    agent_errors = await manager.async_delete_backup(backup_id)

    result: dict[str, Any] = {"backup_id": backup_id, "deleted": True}
    if agent_errors:
        result["agent_errors"] = {
            agent_id: str(err) for agent_id, err in agent_errors.items()
        }
        result["deleted"] = False

    return result
