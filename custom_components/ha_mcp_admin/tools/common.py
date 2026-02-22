"""Shared helpers for HA MCP Admin tools."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
import os
from typing import Any

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.file import write_utf8_file_atomic
from homeassistant.util.yaml import dump, load_yaml

YAML_CRUD_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.string,
        vol.Required("config"): dict,
    }
)


def find_list_item(
    items: list[dict[str, Any]], key: str, value: str
) -> tuple[int, dict[str, Any]] | None:
    """Find an item in a list of dicts by a key match."""
    for index, item in enumerate(items):
        if item.get(key) == value:
            return index, item
    return None


def pick_kwargs(
    arguments: dict[str, Any],
    scalar_keys: tuple[str, ...],
    set_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build a kwargs dict from arguments, converting set_keys to sets."""
    kwargs: dict[str, Any] = {}
    for key in scalar_keys:
        if key in arguments:
            kwargs[key] = arguments[key]
    for key in set_keys:
        if key in arguments:
            kwargs[key] = set(arguments[key])
    return kwargs


SENSITIVE_MARKERS = (
    "access_token",
    "api_key",
    "authorization",
    "bearer",
    "client_secret",
    "password",
    "refresh_token",
    "secret",
    "token",
)


def normalize_data(value: Any) -> Any:
    """Convert values into JSON-serializable primitives."""
    if isinstance(value, Mapping):
        return {str(key): normalize_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [normalize_data(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def redact_data(value: Any) -> Any:
    """Recursively redact sensitive fields in mappings."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if any(marker in key_str.lower() for marker in SENSITIVE_MARKERS):
                result[key_str] = "**redacted**"
            else:
                result[key_str] = redact_data(item)
        return result
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, tuple | set | frozenset):
        return [redact_data(item) for item in value]
    return value


def state_to_dict(state: State, *, include_attributes: bool = True) -> dict[str, Any]:
    """Serialize a Home Assistant state object."""
    payload: dict[str, Any] = {
        "entity_id": state.entity_id,
        "state": state.state,
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
        "context_id": state.context.id,
    }
    if include_attributes:
        payload["attributes"] = normalize_data(state.attributes)
    return payload


def _read_yaml(
    path: str, default: dict[str, Any] | list[Any]
) -> dict[str, Any] | list[Any]:
    """Read a YAML file from disk with a default fallback."""
    if not os.path.isfile(path):
        return default
    data = load_yaml(path)
    if data is None:
        return default
    return data


def _write_yaml(path: str, data: dict[str, Any] | list[Any]) -> None:
    """Write YAML data atomically to disk."""
    contents = dump(data)
    write_utf8_file_atomic(path, contents)


async def async_read_yaml(
    hass: HomeAssistant,
    relative_path: str,
    default: dict[str, Any] | list[Any],
) -> dict[str, Any] | list[Any]:
    """Read YAML data from Home Assistant config path."""
    path = hass.config.path(relative_path)
    data = await hass.async_add_executor_job(_read_yaml, path, default)
    if type(data) is not type(default):
        raise HomeAssistantError(
            f"Unexpected data type in {relative_path}: {type(data).__name__}"
        )
    return data


async def async_write_yaml(
    hass: HomeAssistant,
    relative_path: str,
    data: dict[str, Any] | list[Any],
) -> None:
    """Write YAML data into Home Assistant config path."""
    path = hass.config.path(relative_path)
    await hass.async_add_executor_job(_write_yaml, path, data)
