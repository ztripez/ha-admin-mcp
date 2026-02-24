"""Voice assistant setup and diagnostics tools."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.collection import ItemNotFound

from . import register_tool
from .common import normalize_data, state_to_dict

PIPELINE_MUTABLE_FIELDS = (
    "name",
    "conversation_engine",
    "conversation_language",
    "language",
    "stt_engine",
    "stt_language",
    "tts_engine",
    "tts_language",
    "tts_voice",
    "wake_word_entity",
    "wake_word_id",
    "prefer_local_intents",
)

PIPELINE_NULLABLE_STRING_FIELDS = (
    "stt_engine",
    "stt_language",
    "tts_engine",
    "tts_language",
    "tts_voice",
    "wake_word_entity",
    "wake_word_id",
)

LIST_ASSIST_PIPELINES_SCHEMA = vol.Schema({})

GET_ASSIST_PIPELINE_SCHEMA = vol.Schema({vol.Required("pipeline_id"): cv.string})

CREATE_ASSIST_PIPELINE_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("source_pipeline_id"): cv.string,
        vol.Optional("conversation_engine"): cv.string,
        vol.Optional("conversation_language"): cv.string,
        vol.Optional("language"): cv.string,
        vol.Optional("stt_engine"): vol.Any(None, cv.string),
        vol.Optional("stt_language"): vol.Any(None, cv.string),
        vol.Optional("tts_engine"): vol.Any(None, cv.string),
        vol.Optional("tts_language"): vol.Any(None, cv.string),
        vol.Optional("tts_voice"): vol.Any(None, cv.string),
        vol.Optional("wake_word_entity"): vol.Any(None, cv.string),
        vol.Optional("wake_word_id"): vol.Any(None, cv.string),
        vol.Optional("prefer_local_intents"): cv.boolean,
    }
)

UPDATE_ASSIST_PIPELINE_SCHEMA = vol.Schema(
    {
        vol.Required("pipeline_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("conversation_engine"): cv.string,
        vol.Optional("conversation_language"): cv.string,
        vol.Optional("language"): cv.string,
        vol.Optional("stt_engine"): vol.Any(None, cv.string),
        vol.Optional("stt_language"): vol.Any(None, cv.string),
        vol.Optional("tts_engine"): vol.Any(None, cv.string),
        vol.Optional("tts_language"): vol.Any(None, cv.string),
        vol.Optional("tts_voice"): vol.Any(None, cv.string),
        vol.Optional("wake_word_entity"): vol.Any(None, cv.string),
        vol.Optional("wake_word_id"): vol.Any(None, cv.string),
        vol.Optional("prefer_local_intents"): cv.boolean,
    }
)

DELETE_ASSIST_PIPELINE_SCHEMA = vol.Schema({vol.Required("pipeline_id"): cv.string})

GET_PREFERRED_ASSIST_PIPELINE_SCHEMA = vol.Schema({})

SET_PREFERRED_ASSIST_PIPELINE_SCHEMA = vol.Schema(
    {vol.Required("pipeline_id"): cv.string}
)

LIST_ASSIST_SATELLITES_SCHEMA = vol.Schema({})

GET_ASSIST_SATELLITE_CONFIGURATION_SCHEMA = vol.Schema(
    {vol.Required("entity_id"): cv.entity_domain("assist_satellite")}
)

SET_ASSIST_SATELLITE_WAKE_WORDS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_domain("assist_satellite"),
        vol.Required("wake_word_ids"): [cv.string],
    }
)

SET_ASSIST_SATELLITE_PIPELINE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_domain("assist_satellite"),
        vol.Optional("pipeline_id"): cv.string,
        vol.Optional("use_preferred", default=False): cv.boolean,
    }
)

GET_VOICE_SETUP_STATUS_SCHEMA = vol.Schema({})


def _check_component_loaded(hass: HomeAssistant, domain: str, label: str) -> None:
    """Ensure a Home Assistant component is loaded before use."""
    if domain not in hass.config.components:
        raise HomeAssistantError(
            f"{label} integration is not loaded. "
            f"Please configure {label} in Home Assistant first."
        )


def _serialize_pipeline(pipeline: Any) -> dict[str, Any]:
    """Serialize one assist pipeline object."""
    if hasattr(pipeline, "to_json"):
        data = pipeline.to_json()
    else:
        data = {
            "id": getattr(pipeline, "id", None),
            "name": getattr(pipeline, "name", None),
            "language": getattr(pipeline, "language", None),
            "conversation_engine": getattr(pipeline, "conversation_engine", None),
            "conversation_language": getattr(
                pipeline,
                "conversation_language",
                None,
            ),
            "stt_engine": getattr(pipeline, "stt_engine", None),
            "stt_language": getattr(pipeline, "stt_language", None),
            "tts_engine": getattr(pipeline, "tts_engine", None),
            "tts_language": getattr(pipeline, "tts_language", None),
            "tts_voice": getattr(pipeline, "tts_voice", None),
            "wake_word_entity": getattr(pipeline, "wake_word_entity", None),
            "wake_word_id": getattr(pipeline, "wake_word_id", None),
            "prefer_local_intents": getattr(pipeline, "prefer_local_intents", False),
        }
    return normalize_data(data)


def _pipeline_updates(arguments: dict[str, Any]) -> dict[str, Any]:
    """Extract mutable pipeline fields from tool arguments."""
    return {key: arguments[key] for key in PIPELINE_MUTABLE_FIELDS if key in arguments}


def _get_assist_pipeline_runtime(hass: HomeAssistant) -> dict[str, Any]:
    """Resolve assist pipeline runtime helpers and storage."""
    _check_component_loaded(hass, "assist_pipeline", "Assist pipeline")

    try:
        from homeassistant.components.assist_pipeline import (  # noqa: PLC0415
            async_get_pipeline,
            async_get_pipelines,
        )
        from homeassistant.components.assist_pipeline.pipeline import (  # noqa: PLC0415
            KEY_ASSIST_PIPELINE,
        )
    except ImportError as err:
        raise HomeAssistantError(
            "Assist pipeline component is unavailable in this Home Assistant version"
        ) from err

    pipeline_data = hass.data.get(KEY_ASSIST_PIPELINE)
    if pipeline_data is None:
        raise HomeAssistantError("Assist pipeline runtime data is unavailable")

    pipeline_store = getattr(pipeline_data, "pipeline_store", None)
    if pipeline_store is None:
        raise HomeAssistantError("Assist pipeline storage is unavailable")

    return {
        "async_get_pipeline": async_get_pipeline,
        "async_get_pipelines": async_get_pipelines,
        "pipeline_store": pipeline_store,
    }


def _get_assist_satellite_runtime(hass: HomeAssistant) -> tuple[Any, str]:
    """Resolve assist satellite component runtime."""
    _check_component_loaded(hass, "assist_satellite", "Assist satellite")

    try:
        from homeassistant.components.assist_satellite.const import (  # noqa: PLC0415
            DATA_COMPONENT,
            DOMAIN,
        )
    except ImportError as err:
        raise HomeAssistantError(
            "Assist satellite component is unavailable in this Home Assistant version"
        ) from err

    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError("Assist satellite runtime data is unavailable")

    return component, DOMAIN


def _get_assist_satellite_entity(hass: HomeAssistant, entity_id: str) -> Any:
    """Resolve one assist satellite entity object."""
    component, domain = _get_assist_satellite_runtime(hass)

    if not entity_id.startswith(f"{domain}."):
        raise HomeAssistantError(f"Invalid assist satellite entity ID: {entity_id}")

    satellite = component.get_entity(entity_id)
    if satellite is None:
        raise HomeAssistantError(f"Assist satellite entity not found: {entity_id}")

    return satellite


def _serialize_satellite_configuration(config: Any) -> dict[str, Any]:
    """Serialize assist satellite wake-word configuration."""
    return {
        "available_wake_words": [
            {
                "id": wake_word.id,
                "wake_word": wake_word.wake_word,
                "trained_languages": list(wake_word.trained_languages),
            }
            for wake_word in config.available_wake_words
        ],
        "active_wake_words": list(config.active_wake_words),
        "max_active_wake_words": config.max_active_wake_words,
    }


@register_tool(
    name="list_assist_pipelines",
    description="List all configured Assist voice pipelines and preferred selection",
    parameters=LIST_ASSIST_PIPELINES_SCHEMA,
)
async def list_assist_pipelines(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List Assist pipelines managed by Home Assistant."""
    runtime = _get_assist_pipeline_runtime(hass)
    store = runtime["pipeline_store"]

    pipelines = [
        _serialize_pipeline(pipeline)
        for pipeline in runtime["async_get_pipelines"](hass)
    ]

    return {
        "count": len(pipelines),
        "preferred_pipeline_id": store.async_get_preferred_item(),
        "pipelines": pipelines,
    }


@register_tool(
    name="get_assist_pipeline",
    description="Get one Assist pipeline by ID",
    parameters=GET_ASSIST_PIPELINE_SCHEMA,
)
async def get_assist_pipeline(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get one Assist pipeline."""
    runtime = _get_assist_pipeline_runtime(hass)
    pipeline_id: str = arguments["pipeline_id"]

    try:
        pipeline = runtime["async_get_pipeline"](hass, pipeline_id=pipeline_id)
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(str(err)) from err

    return {"pipeline": _serialize_pipeline(pipeline)}


@register_tool(
    name="create_assist_pipeline",
    description="Create a new Assist pipeline, inheriting defaults from another pipeline",
    parameters=CREATE_ASSIST_PIPELINE_SCHEMA,
)
async def create_assist_pipeline(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create one Assist pipeline."""
    runtime = _get_assist_pipeline_runtime(hass)
    store = runtime["pipeline_store"]
    source_pipeline_id: str | None = arguments.get("source_pipeline_id")

    try:
        source_pipeline = runtime["async_get_pipeline"](
            hass, pipeline_id=source_pipeline_id
        )
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(str(err)) from err

    create_data = _serialize_pipeline(source_pipeline)
    create_data.pop("id", None)
    create_data.update(_pipeline_updates(arguments))
    create_data["name"] = arguments["name"]

    for key in PIPELINE_NULLABLE_STRING_FIELDS:
        if key in create_data and create_data[key] == "":
            create_data[key] = None

    try:
        created = await store.async_create_item(create_data)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {
        "pipeline": _serialize_pipeline(created),
        "preferred_pipeline_id": store.async_get_preferred_item(),
    }


@register_tool(
    name="update_assist_pipeline",
    description="Update one Assist pipeline",
    parameters=UPDATE_ASSIST_PIPELINE_SCHEMA,
)
async def update_assist_pipeline(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Update one Assist pipeline."""
    runtime = _get_assist_pipeline_runtime(hass)
    store = runtime["pipeline_store"]
    pipeline_id: str = arguments["pipeline_id"]

    updates = _pipeline_updates(arguments)
    if not updates:
        raise HomeAssistantError("No assist pipeline fields provided for update")

    try:
        existing_pipeline = runtime["async_get_pipeline"](hass, pipeline_id=pipeline_id)
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(str(err)) from err

    update_data = _serialize_pipeline(existing_pipeline)
    update_data.pop("id", None)
    update_data.update(updates)

    for key in PIPELINE_NULLABLE_STRING_FIELDS:
        if key in update_data and update_data[key] == "":
            update_data[key] = None

    try:
        updated = await store.async_update_item(pipeline_id, update_data)
    except ItemNotFound as err:
        raise HomeAssistantError(f"Assist pipeline not found: {pipeline_id}") from err
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {"pipeline": _serialize_pipeline(updated)}


@register_tool(
    name="delete_assist_pipeline",
    description="Delete one Assist pipeline by ID",
    parameters=DELETE_ASSIST_PIPELINE_SCHEMA,
)
async def delete_assist_pipeline(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Delete one Assist pipeline."""
    runtime = _get_assist_pipeline_runtime(hass)
    store = runtime["pipeline_store"]
    pipeline_id: str = arguments["pipeline_id"]

    if pipeline_id == store.async_get_preferred_item():
        raise HomeAssistantError("Cannot delete the preferred Assist pipeline")

    try:
        await store.async_delete_item(pipeline_id)
    except ItemNotFound as err:
        raise HomeAssistantError(f"Assist pipeline not found: {pipeline_id}") from err
    except HomeAssistantError:
        raise
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    return {
        "deleted": pipeline_id,
        "preferred_pipeline_id": store.async_get_preferred_item(),
    }


@register_tool(
    name="get_preferred_assist_pipeline",
    description="Get the currently preferred Assist pipeline",
    parameters=GET_PREFERRED_ASSIST_PIPELINE_SCHEMA,
)
async def get_preferred_assist_pipeline(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get the preferred Assist pipeline."""
    runtime = _get_assist_pipeline_runtime(hass)
    store = runtime["pipeline_store"]
    preferred_id = store.async_get_preferred_item()

    pipeline = runtime["async_get_pipeline"](hass, pipeline_id=preferred_id)
    return {
        "preferred_pipeline_id": preferred_id,
        "pipeline": _serialize_pipeline(pipeline),
    }


@register_tool(
    name="set_preferred_assist_pipeline",
    description="Set the preferred Assist pipeline",
    parameters=SET_PREFERRED_ASSIST_PIPELINE_SCHEMA,
)
async def set_preferred_assist_pipeline(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Set the preferred Assist pipeline."""
    runtime = _get_assist_pipeline_runtime(hass)
    store = runtime["pipeline_store"]
    pipeline_id: str = arguments["pipeline_id"]

    try:
        store.async_set_preferred_item(pipeline_id)
    except ItemNotFound as err:
        raise HomeAssistantError(f"Assist pipeline not found: {pipeline_id}") from err

    pipeline = runtime["async_get_pipeline"](hass, pipeline_id=pipeline_id)
    return {
        "preferred_pipeline_id": pipeline_id,
        "pipeline": _serialize_pipeline(pipeline),
    }


@register_tool(
    name="list_assist_satellites",
    description="List Assist satellite entities and current assignment state",
    parameters=LIST_ASSIST_SATELLITES_SCHEMA,
)
async def list_assist_satellites(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """List Assist satellite entities."""
    component, domain = _get_assist_satellite_runtime(hass)
    entity_ids = sorted(hass.states.async_entity_ids(domain))

    satellites: list[dict[str, Any]] = []
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        payload = (
            state_to_dict(state) if state is not None else {"entity_id": entity_id}
        )

        satellite = component.get_entity(entity_id)
        if satellite is not None:
            payload["pipeline_entity_id"] = satellite.pipeline_entity_id
            payload["vad_entity_id"] = satellite.vad_sensitivity_entity_id

        satellites.append(normalize_data(payload))

    return {"count": len(satellites), "satellites": satellites}


@register_tool(
    name="get_assist_satellite_configuration",
    description="Get wake-word and pipeline configuration for one Assist satellite",
    parameters=GET_ASSIST_SATELLITE_CONFIGURATION_SCHEMA,
)
async def get_assist_satellite_configuration(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Get one Assist satellite configuration."""
    entity_id: str = arguments["entity_id"]
    satellite = _get_assist_satellite_entity(hass, entity_id)

    try:
        config_payload = _serialize_satellite_configuration(
            satellite.async_get_configuration()
        )
    except NotImplementedError:
        config_payload = {
            "available_wake_words": [],
            "active_wake_words": [],
            "max_active_wake_words": 0,
        }

    pipeline_entity_id = satellite.pipeline_entity_id
    vad_entity_id = satellite.vad_sensitivity_entity_id
    config_payload["pipeline_entity_id"] = pipeline_entity_id
    config_payload["vad_entity_id"] = vad_entity_id

    if (
        pipeline_entity_id is not None
        and (pipeline_state := hass.states.get(pipeline_entity_id)) is not None
    ):
        config_payload["pipeline_state"] = pipeline_state.state
        config_payload["pipeline_options"] = normalize_data(
            pipeline_state.attributes.get("options")
        )

    if (
        vad_entity_id is not None
        and (vad_state := hass.states.get(vad_entity_id)) is not None
    ):
        config_payload["vad_state"] = vad_state.state
        config_payload["vad_options"] = normalize_data(
            vad_state.attributes.get("options")
        )

    return {
        "entity_id": entity_id,
        "configuration": normalize_data(config_payload),
    }


@register_tool(
    name="set_assist_satellite_wake_words",
    description="Set active wake words for one Assist satellite",
    parameters=SET_ASSIST_SATELLITE_WAKE_WORDS_SCHEMA,
)
async def set_assist_satellite_wake_words(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Set active wake words for one Assist satellite."""
    entity_id: str = arguments["entity_id"]
    wake_word_ids: list[str] = arguments["wake_word_ids"]
    satellite = _get_assist_satellite_entity(hass, entity_id)

    try:
        config = satellite.async_get_configuration()
    except NotImplementedError as err:
        raise HomeAssistantError(
            f"Assist satellite does not support wake-word configuration: {entity_id}"
        ) from err

    max_active = config.max_active_wake_words
    if max_active > 0 and len(wake_word_ids) > max_active:
        raise HomeAssistantError(f"Maximum number of active wake words is {max_active}")

    available_ids = {wake_word.id for wake_word in config.available_wake_words}
    unsupported = [
        wake_word_id
        for wake_word_id in wake_word_ids
        if wake_word_id not in available_ids
    ]
    if unsupported:
        raise HomeAssistantError(
            f"Wake word IDs are not supported: {', '.join(sorted(set(unsupported)))}"
        )

    await satellite.async_set_configuration(
        replace(config, active_wake_words=wake_word_ids)
    )

    updated_config = satellite.async_get_configuration()
    return {
        "entity_id": entity_id,
        "configuration": normalize_data(
            _serialize_satellite_configuration(updated_config)
        ),
    }


@register_tool(
    name="set_assist_satellite_pipeline",
    description="Assign a specific Assist pipeline (or preferred) to one satellite",
    parameters=SET_ASSIST_SATELLITE_PIPELINE_SCHEMA,
)
async def set_assist_satellite_pipeline(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Set the pipeline selection for one Assist satellite."""
    entity_id: str = arguments["entity_id"]
    pipeline_id: str | None = arguments.get("pipeline_id")
    use_preferred: bool = arguments["use_preferred"]
    satellite = _get_assist_satellite_entity(hass, entity_id)

    if use_preferred and pipeline_id is not None:
        raise HomeAssistantError(
            "Provide either pipeline_id or use_preferred=true, not both"
        )

    if not use_preferred and pipeline_id is None:
        raise HomeAssistantError(
            "Missing pipeline selection: set pipeline_id or use_preferred=true"
        )

    pipeline_entity_id = satellite.pipeline_entity_id
    if pipeline_entity_id is None:
        raise HomeAssistantError(
            f"Assist satellite does not expose a pipeline selector: {entity_id}"
        )

    selected_option: str
    selected_pipeline: dict[str, Any] | None = None

    if use_preferred:
        try:
            from homeassistant.components.assist_pipeline import (
                OPTION_PREFERRED,
            )  # noqa: PLC0415
        except ImportError as err:
            raise HomeAssistantError(
                "Assist pipeline constants are unavailable in this Home Assistant version"
            ) from err

        selected_option = OPTION_PREFERRED
    else:
        runtime = _get_assist_pipeline_runtime(hass)
        try:
            pipeline = runtime["async_get_pipeline"](hass, pipeline_id=pipeline_id)
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(str(err)) from err

        selected_pipeline = _serialize_pipeline(pipeline)
        selected_option = pipeline.name

    await hass.services.async_call(
        domain="select",
        service="select_option",
        service_data={"option": selected_option},
        target={"entity_id": pipeline_entity_id},
        blocking=True,
    )

    selector_state = hass.states.get(pipeline_entity_id)

    return {
        "entity_id": entity_id,
        "pipeline_entity_id": pipeline_entity_id,
        "selected_option": selected_option,
        "selected_pipeline": selected_pipeline,
        "current_selector_state": selector_state.state if selector_state else None,
    }


@register_tool(
    name="get_voice_setup_status",
    description="Get a one-shot status report for voice assistant setup readiness",
    parameters=GET_VOICE_SETUP_STATUS_SCHEMA,
)
async def get_voice_setup_status(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Return a summarized voice setup diagnostics snapshot."""
    integration_domains = (
        "assist_pipeline",
        "assist_satellite",
        "conversation",
        "stt",
        "tts",
        "wake_word",
        "wyoming",
        "piper",
        "whisper",
        "openai_conversation",
        "cloud",
        "esphome",
    )

    integrations: dict[str, Any] = {}
    for domain in integration_domains:
        entries = hass.config_entries.async_entries(domain=domain)
        if not entries:
            continue
        integrations[domain] = [
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "state": str(entry.state),
            }
            for entry in entries
        ]

    entity_domains = (
        "assist_satellite",
        "conversation",
        "stt",
        "tts",
        "wake_word",
        "select",
    )
    entity_counts = {
        domain: len(hass.states.async_entity_ids(domain)) for domain in entity_domains
    }

    assist_pipeline_status: dict[str, Any] = {"available": False}
    try:
        runtime = _get_assist_pipeline_runtime(hass)
    except HomeAssistantError as err:
        assist_pipeline_status["reason"] = str(err)
    else:
        pipelines = [
            _serialize_pipeline(pipeline)
            for pipeline in runtime["async_get_pipelines"](hass)
        ]
        assist_pipeline_status = {
            "available": True,
            "count": len(pipelines),
            "preferred_pipeline_id": runtime[
                "pipeline_store"
            ].async_get_preferred_item(),
            "pipelines": pipelines,
        }

    assist_satellite_status: dict[str, Any] = {"available": False}
    try:
        _, satellite_domain = _get_assist_satellite_runtime(hass)
    except HomeAssistantError as err:
        assist_satellite_status["reason"] = str(err)
    else:
        assist_satellite_status = {
            "available": True,
            "count": len(hass.states.async_entity_ids(satellite_domain)),
        }

    all_services = hass.services.async_services()
    service_domains = ("assist_pipeline", "assist_satellite", "conversation", "select")
    services = {
        domain: sorted(service_map.keys())
        for domain, service_map in all_services.items()
        if domain in service_domains
    }

    return {
        "integrations": normalize_data(integrations),
        "entity_counts": entity_counts,
        "assist_pipeline": assist_pipeline_status,
        "assist_satellite": assist_satellite_status,
        "services": services,
    }
