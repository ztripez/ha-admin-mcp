"""The HA MCP Admin custom component."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .http import async_register


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HA MCP Admin custom component."""
    async_register(hass)
    return True
