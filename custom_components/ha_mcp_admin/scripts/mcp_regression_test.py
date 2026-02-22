#!/usr/bin/env python3
"""Regression test suite for the HA MCP Admin endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any

from _mcp_client import MCPClientError, MCPHttpClient, extract_tool_json, initialize_mcp

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


@dataclass(slots=True)
class CheckResult:
    """One check result."""

    name: str
    status: str
    detail: str = ""


class RegressionRunner:
    """Runs read-only and optional destructive MCP checks."""

    def __init__(
        self,
        client: MCPHttpClient,
        *,
        continue_on_error: bool,
    ) -> None:
        self._client = client
        self._continue_on_error = continue_on_error
        self._results: list[CheckResult] = []
        self._tools: set[str] = set()

    @property
    def results(self) -> list[CheckResult]:
        """Expose accumulated results."""
        return self._results

    def _record(self, name: str, status: str, detail: str = "") -> None:
        self._results.append(CheckResult(name=name, status=status, detail=detail))
        if detail:
            print(f"[{status}] {name}: {detail}")
        else:
            print(f"[{status}] {name}")

    def _fail(self, name: str, err: Exception) -> None:
        self._record(name, "fail", str(err))
        if not self._continue_on_error:
            raise err

    def initialize(self) -> None:
        """Run MCP initialize and discover tools."""
        protocol = initialize_mcp(self._client, PROTOCOL_VERSIONS)
        self._record("initialize", "ok", f"protocol={protocol}")

        self._client.notify("notifications/initialized")
        self._record("notifications/initialized", "ok")

        body = self._client.request("tools/list", {})
        tools = body["result"].get("tools", [])
        if not isinstance(tools, list):
            raise MCPClientError(f"Unexpected tools/list result: {body['result']}")

        self._tools = {
            tool.get("name")
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("name"), str)
        }
        self._record("tools/list", "ok", f"count={len(self._tools)}")

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one tool and decode JSON payload."""
        body = self._client.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        return extract_tool_json(body["result"])

    def _run_tool_check(
        self,
        check_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        required_keys: tuple[str, ...] = (),
    ) -> None:
        """Run one tool call and validate required top-level keys."""
        if tool_name not in self._tools:
            self._record(check_name, "skip", f"tool not available: {tool_name}")
            return

        try:
            payload = self._call_tool(tool_name, arguments)
            for key in required_keys:
                if key not in payload:
                    raise MCPClientError(
                        f"Missing expected key '{key}' in {tool_name} response"
                    )
            self._record(check_name, "ok")
        except Exception as err:  # noqa: BLE001
            self._fail(check_name, err)

    def run_read_only_suite(self, entity_id: str | None) -> None:
        """Run read-only checks across major categories."""
        self._run_tool_check(
            "tool.get_states",
            "get_states",
            {"include_attributes": False},
            ("states",),
        )
        self._run_tool_check("tool.list_services", "list_services", {}, ("domains",))
        self._run_tool_check(
            "tool.list_automations", "list_automations", {}, ("automations",)
        )
        self._run_tool_check("tool.list_scripts", "list_scripts", {}, ("scripts",))
        self._run_tool_check("tool.list_scenes", "list_scenes", {}, ("scenes",))
        self._run_tool_check("tool.list_helpers", "list_helpers", {}, ("helpers",))
        self._run_tool_check("tool.list_groups", "list_groups", {}, ("groups",))
        self._run_tool_check("tool.list_entities", "list_entities", {}, ("entities",))
        self._run_tool_check("tool.list_devices", "list_devices", {}, ("devices",))
        self._run_tool_check("tool.list_areas", "list_areas", {}, ("areas",))
        self._run_tool_check("tool.list_floors", "list_floors", {}, ("floors",))
        self._run_tool_check("tool.list_labels", "list_labels", {}, ("labels",))
        self._run_tool_check(
            "tool.list_config_entries",
            "list_config_entries",
            {},
            ("entries",),
        )

        if entity_id:
            self._run_tool_check(
                "tool.get_state",
                "get_state",
                {"entity_id": entity_id},
                ("entity_id", "state"),
            )

        try:
            body = self._client.request("prompts/list", {})
            prompts = body["result"].get("prompts", [])
            if not isinstance(prompts, list):
                raise MCPClientError(f"Unexpected prompts/list response: {body['result']}")
            self._record("prompts/list", "ok", f"count={len(prompts)}")

            prompt_name = "home-assistant-admin"
            if prompts:
                first = prompts[0]
                if isinstance(first, dict) and isinstance(first.get("name"), str):
                    prompt_name = first["name"]

            body = self._client.request(
                "prompts/get",
                {"name": prompt_name, "arguments": {}},
            )
            if "result" not in body:
                raise MCPClientError("Missing result in prompts/get response")
            self._record("prompts/get", "ok", f"name={prompt_name}")
        except Exception as err:  # noqa: BLE001
            self._fail("prompt-suite", err)

    def run_destructive_suite(self) -> None:
        """Run destructive create/update/delete lifecycle checks."""
        suffix = uuid.uuid4().hex[:8]

        self._test_label_lifecycle(suffix)
        self._test_floor_lifecycle(suffix)
        self._test_area_lifecycle(suffix)
        self._test_group_lifecycle(suffix)
        self._test_helper_lifecycle(suffix)

    def _test_label_lifecycle(self, suffix: str) -> None:
        if not {"create_label", "update_label", "delete_label"}.issubset(self._tools):
            self._record("destructive.label", "skip", "required tools unavailable")
            return

        label_id: str | None = None
        try:
            created = self._call_tool(
                "create_label",
                {
                    "name": f"mcp_label_{suffix}",
                    "description": "Created by MCP regression suite",
                },
            )
            label_id = created["label"]["label_id"]
            self._call_tool(
                "update_label",
                {
                    "label_id": label_id,
                    "description": "Updated by MCP regression suite",
                },
            )
            self._call_tool("delete_label", {"label_id": label_id})
            label_id = None
            self._record("destructive.label", "ok")
        except Exception as err:  # noqa: BLE001
            self._fail("destructive.label", err)
        finally:
            if label_id is not None:
                try:
                    self._call_tool("delete_label", {"label_id": label_id})
                except Exception:  # noqa: BLE001
                    pass

    def _test_floor_lifecycle(self, suffix: str) -> None:
        if not {"create_floor", "update_floor", "delete_floor"}.issubset(self._tools):
            self._record("destructive.floor", "skip", "required tools unavailable")
            return

        floor_id: str | None = None
        try:
            created = self._call_tool(
                "create_floor",
                {
                    "name": f"mcp_floor_{suffix}",
                    "level": 99,
                },
            )
            floor_id = created["floor"]["floor_id"]
            self._call_tool("update_floor", {"floor_id": floor_id, "icon": "mdi:stairs"})
            self._call_tool("delete_floor", {"floor_id": floor_id})
            floor_id = None
            self._record("destructive.floor", "ok")
        except Exception as err:  # noqa: BLE001
            self._fail("destructive.floor", err)
        finally:
            if floor_id is not None:
                try:
                    self._call_tool("delete_floor", {"floor_id": floor_id})
                except Exception:  # noqa: BLE001
                    pass

    def _test_area_lifecycle(self, suffix: str) -> None:
        if not {"create_area", "update_area", "delete_area"}.issubset(self._tools):
            self._record("destructive.area", "skip", "required tools unavailable")
            return

        area_id: str | None = None
        try:
            created = self._call_tool(
                "create_area",
                {
                    "name": f"mcp_area_{suffix}",
                },
            )
            area_id = created["area"]["area_id"]
            self._call_tool("update_area", {"area_id": area_id, "icon": "mdi:home"})
            self._call_tool("delete_area", {"area_id": area_id})
            area_id = None
            self._record("destructive.area", "ok")
        except Exception as err:  # noqa: BLE001
            self._fail("destructive.area", err)
        finally:
            if area_id is not None:
                try:
                    self._call_tool("delete_area", {"area_id": area_id})
                except Exception:  # noqa: BLE001
                    pass

    def _test_group_lifecycle(self, suffix: str) -> None:
        if not {"create_group", "update_group", "delete_group"}.issubset(self._tools):
            self._record("destructive.group", "skip", "required tools unavailable")
            return

        object_id = f"mcp_group_{suffix}"
        deleted = False
        try:
            self._call_tool(
                "create_group",
                {
                    "object_id": object_id,
                    "name": f"MCP Group {suffix}",
                    "entities": [],
                },
            )
            self._call_tool(
                "update_group",
                {
                    "object_id": object_id,
                    "icon": "mdi:group",
                },
            )
            self._call_tool("delete_group", {"object_id": object_id})
            deleted = True
            self._record("destructive.group", "ok")
        except Exception as err:  # noqa: BLE001
            self._fail("destructive.group", err)
        finally:
            if not deleted:
                try:
                    self._call_tool("delete_group", {"object_id": object_id})
                except Exception:  # noqa: BLE001
                    pass

    def _test_helper_lifecycle(self, suffix: str) -> None:
        required = {"create_helper", "update_helper", "delete_helper"}
        if not required.issubset(self._tools):
            self._record("destructive.helper", "skip", "required tools unavailable")
            return

        helper_id: str | None = None
        try:
            created = self._call_tool(
                "create_helper",
                {
                    "domain": "input_boolean",
                    "data": {"name": f"MCP Helper {suffix}"},
                },
            )
            helper_id = created["helper"]["id"]
            self._call_tool(
                "update_helper",
                {
                    "domain": "input_boolean",
                    "helper_id": helper_id,
                    "data": {"name": f"MCP Helper Updated {suffix}"},
                },
            )
            self._call_tool(
                "delete_helper",
                {
                    "domain": "input_boolean",
                    "helper_id": helper_id,
                },
            )
            helper_id = None
            self._record("destructive.helper", "ok")
        except Exception as err:  # noqa: BLE001
            message = str(err)
            if "unsupported" in message.lower() or "not loaded" in message.lower():
                self._record("destructive.helper", "skip", message)
                return
            self._fail("destructive.helper", err)
        finally:
            if helper_id is not None:
                try:
                    self._call_tool(
                        "delete_helper",
                        {
                            "domain": "input_boolean",
                            "helper_id": helper_id,
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Regression test for /api/mcp_admin")
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
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--entity-id",
        help="Optional entity ID for a direct get_state check",
    )
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Run create/update/delete lifecycle checks",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running checks after a failure",
    )
    return parser.parse_args()


def main() -> int:
    """Run regression checks and return an exit code."""
    args = parse_args()
    token: str | None = args.token or os.environ.get("HA_MCP_ADMIN_TOKEN")
    if not token:
        print("Missing token. Set --token or HA_MCP_ADMIN_TOKEN", file=sys.stderr)
        return 2

    client = MCPHttpClient(args.url, token, args.timeout)
    runner = RegressionRunner(client, continue_on_error=args.continue_on_error)

    try:
        runner.initialize()
        runner.run_read_only_suite(args.entity_id)
        if args.allow_destructive:
            runner.run_destructive_suite()
    except Exception as err:  # noqa: BLE001
        print(f"[error] {err}", file=sys.stderr)

    passed = sum(result.status == "ok" for result in runner.results)
    failed = sum(result.status == "fail" for result in runner.results)
    skipped = sum(result.status == "skip" for result in runner.results)

    print()
    print("Summary")
    print(f"- Passed: {passed}")
    print(f"- Failed: {failed}")
    print(f"- Skipped: {skipped}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
