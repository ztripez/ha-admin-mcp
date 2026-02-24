# HA MCP Admin

A Home Assistant custom component that exposes a comprehensive admin MCP (Model Context Protocol) server over Streamable HTTP.

## Features

This component provides MCP tools for complete Home Assistant administration:

- **Automations** - Create, read, update, and delete automations
- **Scripts** - Full CRUD operations for scripts
- **Scenes** - Manage scenes
- **Helpers** - Manage input helpers (`input_boolean`, `input_number`, `input_select`, `input_text`, `input_datetime`, `counter`, `timer`)
- **Groups** - Create and manage groups
- **Entity Registry** - List, update, and manage entities
- **Device Registry** - Access device information
- **Areas, Floors, Labels & Categories** - Manage organization structures
- **Services** - List and call Home Assistant services
- **States** - Read entity states
- **Config Entries** - List, reload, and delete integration config entries
- **Voice Assistants** - Manage Assist pipelines, preferred pipeline selection, Assist satellite wake words, and satellite pipeline assignment
- **Media Sources** - Map resource paths and URLs into media-source IDs for playback and automation

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right and select "Custom repositories"
4. Add this repository URL: `https://github.com/ztripez/ha-admin-mcp`
5. Select category: "Integration"
6. Click "Add"
7. Find "HA MCP Admin" in the integration list and install it
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/ha_mcp_admin` directory to your Home Assistant configuration directory under `custom_components/`
2. Restart Home Assistant

## Configuration

No configuration is required. The component automatically registers the MCP endpoint when Home Assistant starts.

## Authentication

Create a long-lived access token in your Home Assistant profile:

1. Navigate to your profile in Home Assistant
2. Scroll to "Long-Lived Access Tokens"
3. Click "Create Token"
4. Give it a descriptive name (e.g., "MCP Admin")
5. Copy and save the token securely

## MCP Endpoint

- **URL**: `POST http://your-homeassistant:8123/api/mcp_admin`
- **Authentication**: Bearer token (use your long-lived access token)
- **Transport**: MCP Streamable HTTP (stateless)

## Client Configuration

### Claude Desktop

Add to your Claude Desktop MCP settings file:

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

### Cursor

Add to your Cursor MCP settings:

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

## Testing

### Smoke Test

Verify basic MCP connectivity and tool execution:

```bash
python custom_components/ha_mcp_admin/scripts/mcp_smoke_test.py \
  --url http://homeassistant.local:8123/api/mcp_admin \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN
```

Test a specific tool:

```bash
python custom_components/ha_mcp_admin/scripts/mcp_smoke_test.py \
  --url http://homeassistant.local:8123/api/mcp_admin \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN \
  --tool get_state \
  --tool-args '{"entity_id":"sun.sun"}'
```

### Regression Tests

Run read-only regression tests across all tool categories:

```bash
python custom_components/ha_mcp_admin/scripts/mcp_regression_test.py \
  --url http://homeassistant.local:8123/api/mcp_admin \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN
```

Run full lifecycle tests (includes create/update/delete operations):

```bash
python custom_components/ha_mcp_admin/scripts/mcp_regression_test.py \
  --url http://homeassistant.local:8123/api/mcp_admin \
  --token YOUR_LONG_LIVED_ACCESS_TOKEN \
  --allow-destructive
```

## Security Considerations

⚠️ **This component exposes high-privilege administrative tools**

- Keep your access tokens **secure and private**
- Use network security measures:
  - VPN access for remote connections
  - Local network only deployment
  - Reverse proxy with ACLs
  - Firewall rules
- Rotate tokens periodically
- Only grant access to trusted MCP clients

## Requirements

- Home Assistant 2024.1.0 or newer
- Python 3.12+

## Dependencies

- `mcp==1.26.0` - Model Context Protocol SDK
- `anyio==4.10.0` - Async I/O support

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
