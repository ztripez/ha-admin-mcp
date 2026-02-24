# HA MCP Admin

`ha_mcp_admin` is a Home Assistant custom component that exposes a full admin MCP server over Streamable HTTP.

## Endpoint

- URL: `POST /api/mcp_admin`
- Auth: Home Assistant bearer token
- Transport: MCP Streamable HTTP (stateless)

## Features

- Automations CRUD
- Scripts CRUD
- Scenes CRUD
- Helpers CRUD (`input_boolean`, `input_number`, `input_select`, `input_text`, `input_datetime`, `counter`, `timer`)
- Groups CRUD
- Entity and device registry tools
- Area, floor, label, and category registry tools
- Service call and service listing tools
- State read tools
- Config entry listing/reload/delete
- Assist pipeline and Assist satellite setup tools

## Install

1. Copy `custom_components/ha_mcp_admin` into your Home Assistant config directory under `custom_components`.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and search for **HA MCP Admin**.

## Authentication

Create a long-lived access token in your Home Assistant profile and use it as a bearer token.

## Claude Desktop MCP config example

```json
{
  "mcpServers": {
    "homeassistant-admin": {
      "transport": {
        "type": "streamable-http",
        "url": "http://homeassistant.local:8123/api/mcp_admin",
        "headers": {
          "Authorization": "Bearer YOUR_LONG_LIVED_ACCESS_TOKEN"
        }
      }
    }
  }
}
```

## Cursor MCP config example

```json
{
  "mcpServers": {
    "homeassistant-admin": {
      "url": "http://homeassistant.local:8123/api/mcp_admin",
      "headers": {
        "Authorization": "Bearer YOUR_LONG_LIVED_ACCESS_TOKEN"
      },
      "transport": "streamable-http"
    }
  }
}
```

## Smoke test script

Run the bundled smoke test to verify end-to-end MCP connectivity and one tool call:

```bash
python custom_components/ha_mcp_admin/scripts/mcp_smoke_test.py \
  --url http://homeassistant.local:8123/api/mcp_admin \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN
```

Optional custom tool call:

```bash
python custom_components/ha_mcp_admin/scripts/mcp_smoke_test.py \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN \
  --tool get_state \
  --tool-args '{"entity_id":"sun.sun"}'
```

## Regression suite

Run a read-only regression pass across all tool categories:

```bash
python custom_components/ha_mcp_admin/scripts/mcp_regression_test.py \
  --url http://homeassistant.local:8123/api/mcp_admin \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN
```

Run full lifecycle checks (includes create/update/delete):

```bash
python custom_components/ha_mcp_admin/scripts/mcp_regression_test.py \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN \
  --allow-destructive
```

## Security

- This component exposes high-privilege admin tools.
- Keep tokens secret.
- Use a network boundary (VPN, local network, reverse proxy ACLs) to protect Home Assistant.
