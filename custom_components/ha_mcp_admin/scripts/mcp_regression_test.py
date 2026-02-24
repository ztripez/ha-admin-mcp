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

from _mcp_client import (
    MCPClientError,
    MCPHttpClient,
    PROTOCOL_VERSIONS,
    extract_tool_json,
    initialize_mcp,
)


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

        discovered: set[str] = set()
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = tool.get("name")
            if isinstance(name, str):
                discovered.add(name)

        self._tools = discovered
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
        except MCPClientError as err:
            self._fail(check_name, err)

    def _run_optional_tool_check(
        self,
        check_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        required_keys: tuple[str, ...] = (),
    ) -> None:
        """Run one optional tool call and skip for unavailable components."""
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
        except MCPClientError as err:
            if self._is_component_unavailable_error(err):
                self._record(check_name, "skip", str(err))
                return
            self._fail(check_name, err)

    def _run_voice_read_only_suite(self) -> None:
        """Run optional read-only checks for voice setup tools."""
        self._run_optional_tool_check(
            "tool.get_voice_setup_status",
            "get_voice_setup_status",
            {},
            ("assist_pipeline", "assist_satellite"),
        )
        self._run_optional_tool_check(
            "tool.get_preferred_assist_pipeline",
            "get_preferred_assist_pipeline",
            {},
            ("preferred_pipeline_id", "pipeline"),
        )

        if "list_assist_pipelines" not in self._tools:
            self._record(
                "tool.list_assist_pipelines",
                "skip",
                "tool not available: list_assist_pipelines",
            )
        else:
            try:
                payload = self._call_tool("list_assist_pipelines", {})
                pipelines = payload.get("pipelines", [])
                if not isinstance(pipelines, list):
                    raise MCPClientError(
                        "Invalid response type for list_assist_pipelines.pipelines"
                    )
                self._record("tool.list_assist_pipelines", "ok")

                if "get_assist_pipeline" not in self._tools:
                    self._record(
                        "tool.get_assist_pipeline",
                        "skip",
                        "tool not available: get_assist_pipeline",
                    )
                else:
                    first_pipeline = pipelines[0] if pipelines else None
                    pipeline_id = (
                        first_pipeline.get("id")
                        if isinstance(first_pipeline, dict)
                        else None
                    )
                    if not isinstance(pipeline_id, str):
                        self._record(
                            "tool.get_assist_pipeline",
                            "skip",
                            "no pipeline id available for direct lookup",
                        )
                    else:
                        self._run_optional_tool_check(
                            "tool.get_assist_pipeline",
                            "get_assist_pipeline",
                            {"pipeline_id": pipeline_id},
                            ("pipeline",),
                        )
            except MCPClientError as err:
                if self._is_component_unavailable_error(err):
                    self._record("tool.list_assist_pipelines", "skip", str(err))
                else:
                    self._fail("tool.list_assist_pipelines", err)

        if "list_assist_satellites" not in self._tools:
            self._record(
                "tool.list_assist_satellites",
                "skip",
                "tool not available: list_assist_satellites",
            )
            return

        try:
            payload = self._call_tool("list_assist_satellites", {})
            satellites = payload.get("satellites", [])
            if not isinstance(satellites, list):
                raise MCPClientError(
                    "Invalid response type for list_assist_satellites.satellites"
                )
            self._record("tool.list_assist_satellites", "ok")

            if "get_assist_satellite_configuration" not in self._tools:
                self._record(
                    "tool.get_assist_satellite_configuration",
                    "skip",
                    "tool not available: get_assist_satellite_configuration",
                )
                return

            first_satellite = satellites[0] if satellites else None
            satellite_id = (
                first_satellite.get("entity_id")
                if isinstance(first_satellite, dict)
                else None
            )
            if not isinstance(satellite_id, str):
                self._record(
                    "tool.get_assist_satellite_configuration",
                    "skip",
                    "no assist satellite available for config lookup",
                )
                return

            self._run_optional_tool_check(
                "tool.get_assist_satellite_configuration",
                "get_assist_satellite_configuration",
                {"entity_id": satellite_id},
                ("configuration",),
            )
        except MCPClientError as err:
            if self._is_component_unavailable_error(err):
                self._record("tool.list_assist_satellites", "skip", str(err))
                return
            self._fail("tool.list_assist_satellites", err)

    def _run_media_source_read_only_suite(self) -> None:
        """Run optional read-only checks for media source mapping tools."""
        self._run_optional_tool_check(
            "tool.list_media_source_directories",
            "list_media_source_directories",
            {},
            ("directories",),
        )

        if "map_resources_to_media_sources" not in self._tools:
            self._record(
                "tool.map_resources_to_media_sources",
                "skip",
                "tool not available: map_resources_to_media_sources",
            )
            return

        sample_resource = "/media/local"
        if "list_media_source_directories" in self._tools:
            try:
                directories_payload = self._call_tool(
                    "list_media_source_directories",
                    {},
                )
                directories = directories_payload.get("directories", [])
                first_directory = directories[0] if directories else None
                source_dir_id = (
                    first_directory.get("source_dir_id")
                    if isinstance(first_directory, dict)
                    else None
                )
                if isinstance(source_dir_id, str):
                    sample_resource = f"/media/{source_dir_id}"
            except MCPClientError as err:
                if self._is_component_unavailable_error(err):
                    self._record("tool.list_media_source_directories", "skip", str(err))
                else:
                    self._fail("tool.list_media_source_directories", err)

        try:
            payload = self._call_tool(
                "map_resources_to_media_sources",
                {"resources": [sample_resource]},
            )
            results = payload.get("results")
            count = payload.get("count")
            mapped = payload.get("mapped")
            unmapped = payload.get("unmapped")

            if not isinstance(results, list):
                raise MCPClientError(
                    "Invalid response type for map_resources_to_media_sources.results"
                )
            if not all(isinstance(item, dict) for item in results):
                raise MCPClientError(
                    "Invalid response items for map_resources_to_media_sources.results"
                )
            if (
                not isinstance(count, int)
                or not isinstance(mapped, int)
                or not isinstance(unmapped, int)
            ):
                raise MCPClientError(
                    "Invalid count values for map_resources_to_media_sources"
                )
            if count != mapped + unmapped:
                raise MCPClientError(
                    "Inconsistent count values for map_resources_to_media_sources"
                )
            if len(results) != count:
                raise MCPClientError(
                    "Result list length does not match count for map_resources_to_media_sources"
                )
            if not any(item.get("mapped") is True for item in results):
                raise MCPClientError(
                    "Expected at least one mapped resource in map_resources_to_media_sources"
                )

            self._record("tool.map_resources_to_media_sources", "ok")
        except MCPClientError as err:
            if self._is_component_unavailable_error(err):
                self._record("tool.map_resources_to_media_sources", "skip", str(err))
                return
            self._fail("tool.map_resources_to_media_sources", err)

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
            "tool.list_categories", "list_categories", {}, ("categories",)
        )
        self._run_tool_check(
            "tool.list_config_entries",
            "list_config_entries",
            {},
            ("entries",),
        )
        self._run_voice_read_only_suite()
        self._run_media_source_read_only_suite()

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
                raise MCPClientError(
                    f"Unexpected prompts/list response: {body['result']}"
                )
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
        except MCPClientError as err:
            self._fail("prompt-suite", err)

    def run_destructive_suite(self) -> None:
        """Run destructive create/update/delete lifecycle checks."""
        suffix = uuid.uuid4().hex[:8]

        self._test_automation_lifecycle(suffix)
        self._test_script_lifecycle(suffix)
        self._test_scene_lifecycle(suffix)
        self._test_label_lifecycle(suffix)
        self._test_category_lifecycle(suffix)
        self._test_floor_lifecycle(suffix)
        self._test_area_lifecycle(suffix)
        self._test_group_lifecycle(suffix)
        self._test_helper_lifecycle(suffix)
        self._test_assist_pipeline_lifecycle(suffix)

    @staticmethod
    def _is_component_unavailable_error(err: MCPClientError) -> bool:
        """Return True when the failure indicates missing integration support."""
        message = str(err).lower()
        skip_markers = (
            "service not found",
            "not loaded",
            "component not available",
            "not setup",
            "unsupported",
        )
        return any(marker in message for marker in skip_markers)

    def _test_automation_lifecycle(self, suffix: str) -> None:
        required = {"create_automation", "update_automation", "delete_automation"}
        if not required.issubset(self._tools):
            self._record("destructive.automation", "skip", "required tools unavailable")
            return

        automation_id = f"mcp_automation_{suffix}"
        category_id: str | None = None
        deleted = False
        create_config = {
            "alias": f"MCP Automation {suffix}",
            "trigger": [{"platform": "homeassistant", "event": "start"}],
            "action": [{"delay": "00:00:01"}],
            "mode": "single",
        }
        update_config = {
            "alias": f"MCP Automation Updated {suffix}",
            "trigger": [{"platform": "homeassistant", "event": "start"}],
            "action": [{"delay": "00:00:02"}],
            "mode": "single",
        }

        try:
            if {"create_category", "delete_category"}.issubset(self._tools):
                category = self._call_tool(
                    "create_category",
                    {
                        "scope": "automation",
                        "name": f"mcp_automation_category_{suffix}",
                    },
                )
                category_id = category["category"]["category_id"]

            create_args: dict[str, Any] = {
                "id": automation_id,
                "config": create_config,
            }
            update_args: dict[str, Any] = {
                "id": automation_id,
                "config": update_config,
            }
            if category_id is not None:
                create_args["category_id"] = category_id
                update_args["category_id"] = category_id

            self._call_tool("create_automation", create_args)
            self._call_tool("update_automation", update_args)
            self._call_tool("delete_automation", {"id": automation_id})
            deleted = True
            self._record("destructive.automation", "ok")
        except MCPClientError as err:
            if self._is_component_unavailable_error(err):
                self._record("destructive.automation", "skip", str(err))
                return
            self._fail("destructive.automation", err)
        finally:
            if not deleted:
                try:
                    self._call_tool("delete_automation", {"id": automation_id})
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for automation {automation_id}: {err}",
                        file=sys.stderr,
                    )
            if category_id is not None:
                try:
                    self._call_tool(
                        "delete_category",
                        {"scope": "automation", "category_id": category_id},
                    )
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for category {category_id}: {err}",
                        file=sys.stderr,
                    )

    def _test_script_lifecycle(self, suffix: str) -> None:
        required = {"create_script", "update_script", "delete_script"}
        if not required.issubset(self._tools):
            self._record("destructive.script", "skip", "required tools unavailable")
            return

        script_id = f"mcp_script_{suffix}"
        deleted = False
        create_config = {
            "alias": f"MCP Script {suffix}",
            "sequence": [{"delay": "00:00:01"}],
            "mode": "single",
        }
        update_config = {
            "alias": f"MCP Script Updated {suffix}",
            "sequence": [{"delay": "00:00:02"}],
            "mode": "single",
        }

        try:
            self._call_tool(
                "create_script",
                {"id": script_id, "config": create_config},
            )
            self._call_tool(
                "update_script",
                {"id": script_id, "config": update_config},
            )
            self._call_tool("delete_script", {"id": script_id})
            deleted = True
            self._record("destructive.script", "ok")
        except MCPClientError as err:
            if self._is_component_unavailable_error(err):
                self._record("destructive.script", "skip", str(err))
                return
            self._fail("destructive.script", err)
        finally:
            if not deleted:
                try:
                    self._call_tool("delete_script", {"id": script_id})
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for script {script_id}: {err}",
                        file=sys.stderr,
                    )

    def _test_scene_lifecycle(self, suffix: str) -> None:
        required = {"create_scene", "update_scene", "delete_scene"}
        if not required.issubset(self._tools):
            self._record("destructive.scene", "skip", "required tools unavailable")
            return

        scene_id = f"mcp_scene_{suffix}"
        deleted = False
        create_config = {
            "name": f"MCP Scene {suffix}",
            "entities": {"input_boolean.mcp_dummy": "off"},
        }
        update_config = {
            "name": f"MCP Scene Updated {suffix}",
            "entities": {"input_boolean.mcp_dummy": "on"},
            "icon": "mdi:palette",
        }

        try:
            self._call_tool(
                "create_scene",
                {"id": scene_id, "config": create_config},
            )
            self._call_tool(
                "update_scene",
                {"id": scene_id, "config": update_config},
            )
            self._call_tool("delete_scene", {"id": scene_id})
            deleted = True
            self._record("destructive.scene", "ok")
        except MCPClientError as err:
            if self._is_component_unavailable_error(err):
                self._record("destructive.scene", "skip", str(err))
                return
            self._fail("destructive.scene", err)
        finally:
            if not deleted:
                try:
                    self._call_tool("delete_scene", {"id": scene_id})
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for scene {scene_id}: {err}",
                        file=sys.stderr,
                    )

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
        except MCPClientError as err:
            self._fail("destructive.label", err)
        finally:
            if label_id is not None:
                try:
                    self._call_tool("delete_label", {"label_id": label_id})
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for label {label_id}: {err}",
                        file=sys.stderr,
                    )

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
            self._call_tool(
                "update_floor", {"floor_id": floor_id, "icon": "mdi:stairs"}
            )
            self._call_tool("delete_floor", {"floor_id": floor_id})
            floor_id = None
            self._record("destructive.floor", "ok")
        except MCPClientError as err:
            self._fail("destructive.floor", err)
        finally:
            if floor_id is not None:
                try:
                    self._call_tool("delete_floor", {"floor_id": floor_id})
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for floor {floor_id}: {err}",
                        file=sys.stderr,
                    )

    def _test_category_lifecycle(self, suffix: str) -> None:
        required = {"create_category", "update_category", "delete_category"}
        if not required.issubset(self._tools):
            self._record("destructive.category", "skip", "required tools unavailable")
            return

        scope = "automation"
        category_id: str | None = None
        try:
            created = self._call_tool(
                "create_category",
                {
                    "scope": scope,
                    "name": f"mcp_category_{suffix}",
                },
            )
            category_id = created["category"]["category_id"]
            self._call_tool(
                "update_category",
                {
                    "scope": scope,
                    "category_id": category_id,
                    "icon": "mdi:shape",
                },
            )
            self._call_tool(
                "delete_category",
                {"scope": scope, "category_id": category_id},
            )
            category_id = None
            self._record("destructive.category", "ok")
        except MCPClientError as err:
            self._fail("destructive.category", err)
        finally:
            if category_id is not None:
                try:
                    self._call_tool(
                        "delete_category",
                        {"scope": scope, "category_id": category_id},
                    )
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for category {category_id}: {err}",
                        file=sys.stderr,
                    )

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
        except MCPClientError as err:
            self._fail("destructive.area", err)
        finally:
            if area_id is not None:
                try:
                    self._call_tool("delete_area", {"area_id": area_id})
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for area {area_id}: {err}",
                        file=sys.stderr,
                    )

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
        except MCPClientError as err:
            self._fail("destructive.group", err)
        finally:
            if not deleted:
                try:
                    self._call_tool("delete_group", {"object_id": object_id})
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for group {object_id}: {err}",
                        file=sys.stderr,
                    )

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
        except MCPClientError as err:
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
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for helper {helper_id}: {err}",
                        file=sys.stderr,
                    )

    def _test_assist_pipeline_lifecycle(self, suffix: str) -> None:
        required = {
            "create_assist_pipeline",
            "update_assist_pipeline",
            "delete_assist_pipeline",
        }
        if not required.issubset(self._tools):
            self._record(
                "destructive.assist_pipeline",
                "skip",
                "required tools unavailable",
            )
            return

        pipeline_id: str | None = None
        original_preferred_id: str | None = None
        try:
            source_pipeline_id: str | None = None
            if "list_assist_pipelines" in self._tools:
                list_payload = self._call_tool("list_assist_pipelines", {})
                pipelines = list_payload.get("pipelines", [])
                if isinstance(pipelines, list) and pipelines:
                    first = pipelines[0]
                    if isinstance(first, dict) and isinstance(first.get("id"), str):
                        source_pipeline_id = first["id"]

            if "get_preferred_assist_pipeline" in self._tools:
                preferred_payload = self._call_tool("get_preferred_assist_pipeline", {})
                preferred_id = preferred_payload.get("preferred_pipeline_id")
                if isinstance(preferred_id, str):
                    original_preferred_id = preferred_id

            create_args: dict[str, Any] = {
                "name": f"MCP Voice Pipeline {suffix}",
            }
            if source_pipeline_id is not None:
                create_args["source_pipeline_id"] = source_pipeline_id

            created = self._call_tool("create_assist_pipeline", create_args)
            created_pipeline = created.get("pipeline", {})
            if not isinstance(created_pipeline, dict) or not isinstance(
                created_pipeline.get("id"), str
            ):
                raise MCPClientError(
                    "Missing pipeline.id in create_assist_pipeline response"
                )

            pipeline_id = created_pipeline["id"]
            self._call_tool(
                "update_assist_pipeline",
                {
                    "pipeline_id": pipeline_id,
                    "name": f"MCP Voice Pipeline Updated {suffix}",
                },
            )

            if {
                "set_preferred_assist_pipeline",
                "get_preferred_assist_pipeline",
            }.issubset(self._tools):
                self._call_tool(
                    "set_preferred_assist_pipeline",
                    {"pipeline_id": pipeline_id},
                )
                preferred_payload = self._call_tool(
                    "get_preferred_assist_pipeline",
                    {},
                )
                preferred_id = preferred_payload.get("preferred_pipeline_id")
                if preferred_id != pipeline_id:
                    raise MCPClientError(
                        "Preferred pipeline did not update to created pipeline"
                    )

                if original_preferred_id is not None:
                    self._call_tool(
                        "set_preferred_assist_pipeline",
                        {"pipeline_id": original_preferred_id},
                    )

            self._call_tool("delete_assist_pipeline", {"pipeline_id": pipeline_id})
            pipeline_id = None
            self._record("destructive.assist_pipeline", "ok")
        except MCPClientError as err:
            if self._is_component_unavailable_error(err):
                self._record("destructive.assist_pipeline", "skip", str(err))
                return
            self._fail("destructive.assist_pipeline", err)
        finally:
            if pipeline_id is not None:
                if (
                    original_preferred_id is not None
                    and "set_preferred_assist_pipeline" in self._tools
                ):
                    try:
                        self._call_tool(
                            "set_preferred_assist_pipeline",
                            {"pipeline_id": original_preferred_id},
                        )
                    except MCPClientError as err:
                        print(
                            f"[warn] failed to restore preferred pipeline {original_preferred_id}: {err}",
                            file=sys.stderr,
                        )
                try:
                    self._call_tool(
                        "delete_assist_pipeline",
                        {"pipeline_id": pipeline_id},
                    )
                except MCPClientError as err:
                    print(
                        f"[warn] cleanup failed for assist pipeline {pipeline_id}: {err}",
                        file=sys.stderr,
                    )


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
    except MCPClientError as err:
        print(f"[error] {err}", file=sys.stderr)
        return 1

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
