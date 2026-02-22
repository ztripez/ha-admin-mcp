#!/usr/bin/env python3
"""Smoke-test client for the HA MCP Admin endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys

from _mcp_client import (
    MCPClientError,
    MCPHttpClient,
    PROTOCOL_VERSIONS,
    extract_tool_json,
    initialize_mcp,
)

DEFAULT_TOOL_ARGS = {"include_attributes": False}


def run(args: argparse.Namespace) -> int:
    """Execute smoke test flow."""
    token: str | None = args.token or os.environ.get("HA_MCP_ADMIN_TOKEN")
    if not token:
        print("Missing token. Set --token or HA_MCP_ADMIN_TOKEN", file=sys.stderr)
        return 2

    client = MCPHttpClient(args.url, token, args.timeout)

    protocol_version = initialize_mcp(client, PROTOCOL_VERSIONS)
    print(f"[ok] initialize protocol={protocol_version}")

    client.notify("notifications/initialized")
    print("[ok] notifications/initialized")

    tools_response = client.request("tools/list", {})
    tools = tools_response["result"].get("tools", [])
    if not isinstance(tools, list):
        raise MCPClientError(
            f"Unexpected tools/list result: {tools_response['result']}"
        )
    print(f"[ok] tools/list count={len(tools)}")

    requested_tool = args.tool
    if requested_tool not in {
        tool.get("name") for tool in tools if isinstance(tool, dict)
    }:
        raise MCPClientError(f"Requested tool is not available: {requested_tool}")

    tool_args = json.loads(args.tool_args)
    tool_call = client.request(
        "tools/call",
        {
            "name": requested_tool,
            "arguments": tool_args,
        },
    )
    tool_payload = extract_tool_json(tool_call["result"])
    print(f"[ok] tools/call name={requested_tool}")
    print(json.dumps(tool_payload, indent=2, ensure_ascii=False))

    return 0


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Smoke test for /api/mcp_admin")
    parser.add_argument(
        "--url",
        default="http://homeassistant.local:8123/api/mcp_admin",
        help="MCP endpoint URL",
    )
    parser.add_argument(
        "--token",
        help="Home Assistant long-lived access token (or set HA_MCP_ADMIN_TOKEN)",
    )
    parser.add_argument(
        "--tool",
        default="get_states",
        help="Tool name to call after listing tools",
    )
    parser.add_argument(
        "--tool-args",
        default=json.dumps(DEFAULT_TOOL_ARGS),
        help="JSON string with tool arguments",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except MCPClientError as err:
        print(f"[error] {err}", file=sys.stderr)
        raise SystemExit(1)
