"""History and statistics tools."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from . import register_tool
from .common import normalize_data

# Constants for component domains
RECORDER_DOMAIN = "recorder"
HISTORY_DOMAIN = "history"


def _check_recorder_loaded(hass: HomeAssistant) -> None:
    """Check if recorder component is loaded."""
    if RECORDER_DOMAIN not in hass.config.components:
        raise HomeAssistantError(
            "Recorder component is not loaded. History and statistics require the recorder."
        )


def _check_history_loaded(hass: HomeAssistant) -> None:
    """Check if history component is loaded."""
    if HISTORY_DOMAIN not in hass.config.components:
        raise HomeAssistantError(
            "History component is not loaded."
        )


def _parse_datetime(value: str | None, default: datetime | None = None) -> datetime | None:
    """Parse an ISO datetime string to a datetime object."""
    if value is None:
        return default
    try:
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            raise HomeAssistantError(f"Invalid datetime format: {value}")
        return dt_util.as_utc(parsed)
    except (ValueError, TypeError) as err:
        raise HomeAssistantError(f"Invalid datetime format: {value}") from err


def _serialize_state(state: Any) -> dict[str, Any]:
    """Serialize a state object to a dictionary."""
    if hasattr(state, "as_dict"):
        return normalize_data(state.as_dict())
    if isinstance(state, dict):
        return normalize_data(state)
    return normalize_data({"state": str(state)})


# Schemas
GET_ENTITY_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("entity_ids"): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional("start_time"): cv.string,
        vol.Optional("end_time"): cv.string,
        vol.Optional("minimal_response", default=False): cv.boolean,
        vol.Optional("significant_changes_only", default=True): cv.boolean,
        vol.Optional("no_attributes", default=False): cv.boolean,
    }
)

GET_STATISTICS_SCHEMA = vol.Schema(
    {
        vol.Required("statistic_ids"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("start_time"): cv.string,
        vol.Optional("end_time"): cv.string,
        vol.Optional("period", default="hour"): vol.In(
            ["5minute", "hour", "day", "week", "month"]
        ),
        vol.Optional("types"): vol.All(
            cv.ensure_list,
            [vol.In(["change", "last_reset", "max", "mean", "min", "state", "sum"])],
        ),
    }
)

LIST_STATISTIC_IDS_SCHEMA = vol.Schema(
    {
        vol.Optional("statistic_type"): vol.In(["mean", "sum"]),
    }
)

GET_RECORDER_INFO_SCHEMA = vol.Schema({})


@register_tool(
    name="get_entity_history",
    description="Get state history for entity(s). Returns historical state changes within a time range.",
    parameters=GET_ENTITY_HISTORY_SCHEMA,
)
async def get_entity_history(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get state history for one or more entities."""
    _check_recorder_loaded(hass)
    _check_history_loaded(hass)

    # Import here to avoid import errors if recorder not available
    from homeassistant.components.recorder import get_instance, history

    entity_ids: list[str] = arguments["entity_ids"]
    minimal_response: bool = arguments.get("minimal_response", False)
    significant_changes_only: bool = arguments.get("significant_changes_only", True)
    no_attributes: bool = arguments.get("no_attributes", False)

    # Parse time range
    now = dt_util.utcnow()
    default_start = now - timedelta(hours=24)

    start_time = _parse_datetime(arguments.get("start_time"), default_start)
    end_time = _parse_datetime(arguments.get("end_time"), now)

    if start_time and end_time and start_time > end_time:
        raise HomeAssistantError("start_time must be before end_time")

    # Validate entity IDs exist
    for entity_id in entity_ids:
        if not hass.states.get(entity_id):
            # Entity doesn't exist currently, but may have historical data
            pass

    # Get history from recorder
    instance = get_instance(hass)

    def _get_history() -> dict[str, list[Any]]:
        """Fetch history in executor."""
        return history.get_significant_states(
            hass,
            start_time,
            end_time,
            entity_ids,
            filters=None,
            include_start_time_state=True,
            significant_changes_only=significant_changes_only,
            minimal_response=minimal_response,
            no_attributes=no_attributes,
            compressed_state_format=False,
        )

    result = await instance.async_add_executor_job(_get_history)

    # Serialize the result
    serialized: dict[str, list[dict[str, Any]]] = {}
    for entity_id, states in result.items():
        serialized[entity_id] = [_serialize_state(state) for state in states]

    return {
        "entity_ids": entity_ids,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None,
        "history": serialized,
        "total_states": sum(len(states) for states in serialized.values()),
    }


@register_tool(
    name="get_statistics",
    description="Get long-term statistics for sensors. Returns aggregated data (mean, min, max, sum) over time periods.",
    parameters=GET_STATISTICS_SCHEMA,
)
async def get_statistics(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get long-term statistics for statistic IDs."""
    _check_recorder_loaded(hass)

    # Import here to avoid import errors if recorder not available
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import statistics_during_period

    statistic_ids: list[str] = arguments["statistic_ids"]
    period: Literal["5minute", "hour", "day", "week", "month"] = arguments.get(
        "period", "hour"
    )

    # Parse time range
    now = dt_util.utcnow()
    default_start = now - timedelta(days=7)

    start_time = _parse_datetime(arguments.get("start_time"), default_start)
    end_time = _parse_datetime(arguments.get("end_time"), now)

    if start_time and end_time and start_time > end_time:
        raise HomeAssistantError("start_time must be before end_time")

    # Default types if not specified
    types_list = arguments.get("types")
    if types_list:
        types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]] = set(types_list)
    else:
        types = {"mean", "min", "max", "sum", "state", "change"}

    instance = get_instance(hass)

    def _get_statistics() -> dict[str, list[dict[str, Any]]]:
        """Fetch statistics in executor."""
        return statistics_during_period(
            hass,
            start_time,
            end_time,
            set(statistic_ids),
            period,
            units=None,
            types=types,
        )

    result = await instance.async_add_executor_job(_get_statistics)

    # Normalize timestamps in result
    normalized_result: dict[str, list[dict[str, Any]]] = {}
    for stat_id, stat_list in result.items():
        normalized_stats = []
        for stat in stat_list:
            normalized_stat = dict(stat)
            # Convert timestamps to ISO format
            if "start" in normalized_stat:
                # start is a float timestamp
                start_ts = normalized_stat["start"]
                if isinstance(start_ts, (int, float)):
                    # Convert from milliseconds if needed
                    if start_ts > 1e12:  # Likely milliseconds
                        start_ts = start_ts / 1000
                    normalized_stat["start"] = datetime.fromtimestamp(
                        start_ts, tz=dt_util.UTC
                    ).isoformat()
            if "end" in normalized_stat:
                end_ts = normalized_stat["end"]
                if isinstance(end_ts, (int, float)):
                    if end_ts > 1e12:
                        end_ts = end_ts / 1000
                    normalized_stat["end"] = datetime.fromtimestamp(
                        end_ts, tz=dt_util.UTC
                    ).isoformat()
            if "last_reset" in normalized_stat and normalized_stat["last_reset"]:
                lr_ts = normalized_stat["last_reset"]
                if isinstance(lr_ts, (int, float)):
                    if lr_ts > 1e12:
                        lr_ts = lr_ts / 1000
                    normalized_stat["last_reset"] = datetime.fromtimestamp(
                        lr_ts, tz=dt_util.UTC
                    ).isoformat()
            normalized_stats.append(normalized_stat)
        normalized_result[stat_id] = normalized_stats

    return {
        "statistic_ids": statistic_ids,
        "period": period,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None,
        "statistics": normalize_data(normalized_result),
        "total_records": sum(len(stats) for stats in normalized_result.values()),
    }


@register_tool(
    name="list_statistic_ids",
    description="List available statistics IDs with metadata. Shows what long-term statistics are being tracked.",
    parameters=LIST_STATISTIC_IDS_SCHEMA,
)
async def list_statistic_ids(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List all available statistic IDs."""
    _check_recorder_loaded(hass)

    # Import here to avoid import errors if recorder not available
    from homeassistant.components.recorder.statistics import (
        list_statistic_ids as recorder_list_statistic_ids,
    )

    statistic_type: Literal["mean", "sum"] | None = arguments.get("statistic_type")

    # list_statistic_ids is a sync function that needs to run in executor
    from homeassistant.components.recorder import get_instance

    instance = get_instance(hass)

    def _list_ids() -> list[dict[str, Any]]:
        """Fetch statistic IDs in executor."""
        return recorder_list_statistic_ids(
            hass,
            statistic_ids=None,
            statistic_type=statistic_type,
        )

    result = await instance.async_add_executor_job(_list_ids)

    return {
        "statistic_type": statistic_type,
        "count": len(result),
        "statistic_ids": normalize_data(result),
    }


@register_tool(
    name="get_recorder_info",
    description="Get recorder status and database information. Shows database engine, path, and recording status.",
    parameters=GET_RECORDER_INFO_SCHEMA,
)
async def get_recorder_info(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get recorder status and information."""
    _check_recorder_loaded(hass)

    # Import here to avoid import errors if recorder not available
    from homeassistant.components.recorder import get_instance

    instance = get_instance(hass)

    # Gather recorder information
    info: dict[str, Any] = {
        "running": instance.is_running,
        "recording": instance.recording,
        "thread_alive": instance.is_alive() if hasattr(instance, "is_alive") else None,
    }

    # Database information
    if hasattr(instance, "db_url"):
        db_url = instance.db_url
        # Redact password from URL if present
        if "@" in db_url and "://" in db_url:
            # Simple redaction - replace password
            parts = db_url.split("://", 1)
            if len(parts) == 2 and "@" in parts[1]:
                user_pass, rest = parts[1].split("@", 1)
                if ":" in user_pass:
                    user = user_pass.split(":")[0]
                    db_url = f"{parts[0]}://{user}:*****@{rest}"
        info["database_url"] = db_url

    if hasattr(instance, "database_engine"):
        engine = instance.database_engine
        if engine:
            info["database_engine"] = {
                "dialect": str(engine.dialect.name) if hasattr(engine, "dialect") else None,
            }

    if hasattr(instance, "dialect_name"):
        info["dialect_name"] = instance.dialect_name

    # Configuration
    if hasattr(instance, "keep_days"):
        info["keep_days"] = instance.keep_days
    if hasattr(instance, "commit_interval"):
        info["commit_interval"] = instance.commit_interval

    # Get oldest recorded data timestamp if available
    def _get_recorder_stats() -> dict[str, Any]:
        """Get additional recorder stats in executor."""
        stats: dict[str, Any] = {}
        try:
            from homeassistant.components.recorder.util import session_scope
            from homeassistant.components.recorder.db_schema import States
            from sqlalchemy import func

            with session_scope(hass=hass, read_only=True) as session:
                # Get oldest state
                oldest = session.query(func.min(States.last_updated_ts)).scalar()
                if oldest:
                    stats["oldest_state_ts"] = datetime.fromtimestamp(
                        oldest, tz=dt_util.UTC
                    ).isoformat()

                # Get state count (approximate)
                count = session.query(func.count(States.state_id)).scalar()
                stats["total_states_count"] = count
        except Exception:
            # If we can't get stats, that's okay
            pass
        return stats

    try:
        extra_stats = await instance.async_add_executor_job(_get_recorder_stats)
        info.update(extra_stats)
    except Exception:
        # Ignore errors getting extra stats
        pass

    return normalize_data(info)
