"""Media source mapping tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data

LIST_MEDIA_SOURCE_DIRECTORIES_SCHEMA = vol.Schema({})

MAP_RESOURCES_TO_MEDIA_SOURCES_SCHEMA = vol.Schema(
    {
        vol.Required("resources"): vol.All([cv.string], vol.Length(min=1)),
        vol.Optional("default_source_dir"): cv.string,
        vol.Optional("target_media_player"): cv.entity_id,
        vol.Optional("include_resolved_url", default=False): cv.boolean,
    }
)


def _get_media_dirs(hass: HomeAssistant) -> dict[str, str]:
    """Return configured media directories."""
    return {
        source_dir_id: str(path)
        for source_dir_id, path in hass.config.media_dirs.items()
    }


def _normalize_location(location: str) -> str:
    """Normalize a media location path and reject traversal."""
    sanitized = location.replace("\\", "/").lstrip("/")
    if not sanitized:
        return ""

    parts = [part for part in sanitized.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError("path traversal is not allowed")

    return "/".join(parts)


def _relative_posix_if_within(path: Path, base_path: Path) -> str | None:
    """Return POSIX relative path if path is inside base_path."""
    try:
        relative = path.resolve().relative_to(base_path.resolve())
    except ValueError:
        return None

    relative_posix = relative.as_posix()
    return "" if relative_posix == "." else relative_posix


def _local_mapping(
    source_dir_id: str, location: str, media_dirs: dict[str, str]
) -> dict[str, Any]:
    """Build mapping payload for a local media directory location."""
    from homeassistant.components import media_source

    identifier = source_dir_id if location == "" else f"{source_dir_id}/{location}"
    absolute_path = str(Path(media_dirs[source_dir_id], location))
    web_path = f"/media/{source_dir_id}"
    if location:
        web_path = f"{web_path}/{location}"

    return {
        "mapped": True,
        "domain": media_source.DOMAIN,
        "identifier": identifier,
        "source_dir_id": source_dir_id,
        "location": location,
        "media_source_id": media_source.generate_media_source_id(
            media_source.DOMAIN,
            identifier,
        ),
        "web_path": web_path,
        "absolute_path": absolute_path,
    }


def _from_media_web_path(path: str, media_dirs: dict[str, str]) -> dict[str, Any]:
    """Map /media/{source_dir}/{location} paths to media source IDs."""
    if not path.startswith("/media/"):
        return {"mapped": False, "reason": "not a /media path"}

    payload = path.removeprefix("/media/")
    source_dir_id, _, location = payload.partition("/")
    if not source_dir_id:
        return {
            "mapped": False,
            "reason": "missing media source directory id in path",
        }

    if source_dir_id not in media_dirs:
        return {
            "mapped": False,
            "reason": f"unknown media source directory: {source_dir_id}",
        }

    try:
        normalized_location = _normalize_location(location)
    except ValueError as err:
        return {"mapped": False, "reason": str(err)}

    return _local_mapping(source_dir_id, normalized_location, media_dirs)


def _from_absolute_path(path_str: str, media_dirs: dict[str, str]) -> dict[str, Any]:
    """Map an absolute filesystem path to a media source ID."""
    candidate = Path(path_str).expanduser()
    if not candidate.is_absolute():
        return {"mapped": False, "reason": "path is not absolute"}

    for source_dir_id, base_path in media_dirs.items():
        location = _relative_posix_if_within(candidate, Path(base_path).expanduser())
        if location is None:
            continue
        return _local_mapping(source_dir_id, location, media_dirs)

    return {
        "mapped": False,
        "reason": "path is not inside any configured media source directory",
    }


def _map_single_resource(
    hass: HomeAssistant,
    resource: str,
    media_dirs: dict[str, str],
    default_source_dir: str | None,
) -> dict[str, Any]:
    """Map one resource string to a media source identifier when possible."""
    from homeassistant.components import media_source

    result: dict[str, Any] = {
        "resource": resource,
        "mapped": False,
    }

    candidate = resource.strip()
    if candidate == "":
        result["reason"] = "resource is empty"
        return result

    if media_source.is_media_source_id(candidate):
        try:
            item = media_source.MediaSourceItem.from_uri(hass, candidate, None)
        except ValueError as err:
            result["reason"] = str(err)
            return result

        result.update(
            {
                "mapped": True,
                "domain": item.domain,
                "identifier": item.identifier,
                "media_source_id": item.media_source_id,
            }
        )

        if item.domain == media_source.DOMAIN:
            source_dir_id, _, location = item.identifier.partition("/")
            if source_dir_id in media_dirs:
                result.update(_local_mapping(source_dir_id, location, media_dirs))
            else:
                result["source_dir_id"] = source_dir_id
                result["reason"] = f"unknown media source directory: {source_dir_id}"

        return normalize_data(result)

    parsed = urlparse(candidate)
    if parsed.scheme in ("http", "https"):
        web_path_mapping = _from_media_web_path(unquote(parsed.path), media_dirs)
        result.update(web_path_mapping)
        if not web_path_mapping["mapped"] and "reason" not in result:
            result["reason"] = "URL path does not match /media/{source_dir}/{location}"
        return normalize_data(result)

    if parsed.scheme == "file":
        result.update(_from_absolute_path(unquote(parsed.path), media_dirs))
        return normalize_data(result)

    if candidate.startswith("/media/"):
        result.update(_from_media_web_path(candidate, media_dirs))
        return normalize_data(result)

    if candidate.startswith("/local/"):
        result["reason"] = (
            "'/local/' resources are static www assets and not media source URLs"
        )
        return normalize_data(result)

    absolute_path_mapping = _from_absolute_path(candidate, media_dirs)
    if absolute_path_mapping["mapped"]:
        result.update(absolute_path_mapping)
        return normalize_data(result)

    source_dir_id = default_source_dir
    if source_dir_id is None and len(media_dirs) == 1:
        source_dir_id = next(iter(media_dirs))

    if source_dir_id is None:
        result["reason"] = "relative path is ambiguous; provide default_source_dir"
        return normalize_data(result)

    if source_dir_id not in media_dirs:
        result["reason"] = f"unknown default_source_dir: {source_dir_id}"
        return normalize_data(result)

    try:
        location = _normalize_location(candidate)
    except ValueError as err:
        result["reason"] = str(err)
        return normalize_data(result)

    result.update(_local_mapping(source_dir_id, location, media_dirs))
    return normalize_data(result)


@register_tool(
    name="list_media_source_directories",
    description="List configured local media source directories and their URL roots",
    parameters=LIST_MEDIA_SOURCE_DIRECTORIES_SCHEMA,
)
async def list_media_source_directories(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List configured media source directories."""
    media_dirs = _get_media_dirs(hass)

    directories: list[dict[str, Any]] = []
    for source_dir_id, path in sorted(media_dirs.items()):
        mapping = _local_mapping(source_dir_id, "", media_dirs)
        directories.append(
            {
                "source_dir_id": source_dir_id,
                "path": path,
                "media_source_root": mapping["media_source_id"],
                "web_path_root": mapping["web_path"],
            }
        )

    return {
        "count": len(directories),
        "directories": normalize_data(directories),
    }


@register_tool(
    name="map_resources_to_media_sources",
    description=(
        "Map resources (paths, /media URLs, media-source IDs, file URLs) to "
        "Home Assistant media-source identifiers"
    ),
    parameters=MAP_RESOURCES_TO_MEDIA_SOURCES_SCHEMA,
)
async def map_resources_to_media_sources(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Map resource identifiers to media source IDs."""
    from homeassistant.components import media_source

    resources: list[str] = arguments["resources"]
    default_source_dir: str | None = arguments.get("default_source_dir")
    target_media_player: str | None = arguments.get("target_media_player")
    include_resolved_url: bool = arguments["include_resolved_url"]

    media_dirs = _get_media_dirs(hass)
    media_source_loaded = media_source.DOMAIN in hass.data
    if include_resolved_url and not media_source_loaded:
        raise HomeAssistantError(
            "media_source component is not loaded; cannot resolve resource URLs"
        )

    results: list[dict[str, Any]] = []
    for resource in resources:
        mapping = _map_single_resource(hass, resource, media_dirs, default_source_dir)

        media_source_id = mapping.get("media_source_id")
        if (
            include_resolved_url
            and isinstance(media_source_id, str)
            and media_source_loaded
        ):
            try:
                resolved = await media_source.async_resolve_media(
                    hass,
                    media_source_id,
                    target_media_player=target_media_player,
                )
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(
                    "Failed to resolve mapped media source "
                    f"'{media_source_id}' for resource '{resource}': {err}"
                ) from err
            else:
                mapping["resolved_url"] = resolved.url
                mapping["resolved_mime_type"] = resolved.mime_type

        results.append(mapping)

    mapped_count = sum(1 for item in results if item.get("mapped") is True)
    return {
        "count": len(results),
        "mapped": mapped_count,
        "unmapped": len(results) - mapped_count,
        "results": normalize_data(results),
    }
