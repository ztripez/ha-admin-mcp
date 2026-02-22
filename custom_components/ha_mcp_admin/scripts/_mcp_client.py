"""Small MCP Streamable HTTP client helpers for test scripts."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MCPClientError(Exception):
    """Raised when the MCP HTTP client encounters an error."""


class MCPHttpClient:
    """Very small JSON-RPC over Streamable HTTP client."""

    def __init__(self, endpoint: str, token: str, timeout: float) -> None:
        self._endpoint = endpoint
        self._token = token
        self._timeout = timeout
        self._next_id = 1

    def _request(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
        )

        try:
            with urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                raw = response.read()
                if not raw:
                    return response.status, None
                return response.status, json.loads(raw.decode("utf-8"))
        except HTTPError as err:
            detail = err.read().decode("utf-8", errors="replace")
            raise MCPClientError(
                f"HTTP {err.code} error calling MCP endpoint: {detail}"
            ) from err
        except URLError as err:
            raise MCPClientError(f"Could not reach MCP endpoint: {err.reason}") from err

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request and return parsed response body."""
        request_id = self._next_id
        self._next_id += 1

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        status, body = self._request(payload)
        if status != 200 or body is None:
            raise MCPClientError(
                f"Expected HTTP 200 for request {method}, got {status}"
            )

        if "error" in body:
            raise MCPClientError(f"MCP error for {method}: {body['error']}")

        if "result" not in body:
            raise MCPClientError(f"Malformed MCP response for {method}: {body}")

        return body

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification."""
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        status, _ = self._request(payload)
        if status not in (200, 202):
            raise MCPClientError(
                f"Expected HTTP 200/202 for notification {method}, got {status}"
            )


def extract_tool_json(result: dict[str, Any]) -> dict[str, Any]:
    """Extract and decode first text content from tools/call result."""
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise MCPClientError(f"Unexpected tools/call result payload: {result}")

    text = content[0].get("text")
    if not isinstance(text, str):
        raise MCPClientError(f"Missing text content in tools/call response: {result}")

    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise MCPClientError(f"Tool response was not valid JSON text: {text}") from err


def initialize_mcp(client: MCPHttpClient, versions: tuple[str, ...]) -> str:
    """Try known protocol versions and return selected version."""
    for version in versions:
        try:
            response = client.request(
                "initialize",
                {
                    "protocolVersion": version,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ha-mcp-admin-test-client",
                        "version": "0.1.0",
                    },
                },
            )
            result = response["result"]
            if isinstance(result, dict) and result.get("protocolVersion"):
                return str(result["protocolVersion"])
        except MCPClientError:
            continue

    raise MCPClientError("Failed to initialize MCP session with known protocol versions")
