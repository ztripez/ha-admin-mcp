"""Service tools."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import register_tool
from .common import normalize_data

CALL_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): cv.string,
        vol.Required("service"): cv.string,
        vol.Optional("service_data", default={}): dict,
        vol.Optional("target"): dict,
        vol.Optional("blocking", default=True): cv.boolean,
        vol.Optional("return_response", default=False): cv.boolean,
    }
)

LIST_SERVICES_SCHEMA = vol.Schema(
    {
        vol.Optional("domain"): cv.string,
        vol.Optional("include_schema", default=True): cv.boolean,
    }
)


@register_tool(
    name="call_service",
    description="Call a Home Assistant service",
    parameters=CALL_SERVICE_SCHEMA,
)
async def call_service(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a Home Assistant service and return response metadata."""
    domain: str = arguments["domain"].lower()
    service: str = arguments["service"].lower()
    services = hass.services.async_services()

    if domain not in services or service not in services[domain]:
        raise HomeAssistantError(f"Service not found: {domain}.{service}")

    response = await hass.services.async_call(
        domain,
        service,
        service_data=arguments["service_data"],
        target=arguments.get("target"),
        blocking=arguments["blocking"],
        return_response=arguments["return_response"],
    )

    return {
        "called": f"{domain}.{service}",
        "response": normalize_data(response),
    }


@register_tool(
    name="list_services",
    description="List Home Assistant services by domain",
    parameters=LIST_SERVICES_SCHEMA,
)
async def list_services(hass: HomeAssistant, arguments: dict[str, Any]) -> dict[str, Any]:
    """List registered services and optionally schemas."""
    requested_domain: str | None = arguments.get("domain")
    include_schema: bool = arguments["include_schema"]
    all_services = hass.services.async_services()

    result: dict[str, dict[str, Any]] = {}
    for domain, service_map in all_services.items():
        if requested_domain is not None and domain != requested_domain:
            continue

        domain_data: dict[str, Any] = {}
        for service_name, service_obj in service_map.items():
            entry: dict[str, Any] = {
                "supports_response": str(service_obj.supports_response),
            }

            if include_schema and service_obj.schema is not None:
                try:
                    entry["schema"] = convert(service_obj.schema)
                except vol.Invalid as err:
                    entry["schema_error"] = str(err)

            domain_data[service_name] = entry

        result[domain] = domain_data

    return {"domains": result}
