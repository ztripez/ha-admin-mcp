"""Config flow for HA MCP Admin."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class HaMcpAdminConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for HA MCP Admin."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="HA MCP Admin", data={})

        return self.async_show_form(step_id="user")
