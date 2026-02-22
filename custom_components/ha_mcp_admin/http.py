"""Streamable HTTP transport for HA MCP Admin."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http import HTTPStatus

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp import JSONRPCRequest, types
from mcp.shared.message import SessionMessage

from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.core import HomeAssistant, callback

from .const import API_ENDPOINT, DOMAIN, TIMEOUT_SECONDS
from .server import create_server

CONTENT_TYPE_JSON = "application/json"


@dataclass
class Streams:
    """Pairs of streams for MCP server communication."""

    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]


def _create_streams() -> Streams:
    """Create stream pairs for MCP SDK interaction."""
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
    return Streams(
        read_stream=read_stream,
        read_stream_writer=read_stream_writer,
        write_stream=write_stream,
        write_stream_reader=write_stream_reader,
    )


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register HTTP endpoint for MCP admin server."""
    hass.http.register_view(ModelContextProtocolAdminView())


class ModelContextProtocolAdminView(HomeAssistantView):
    """MCP Streamable HTTP endpoint."""

    name = f"{DOMAIN}:streamable"
    url = API_ENDPOINT

    @require_admin
    async def get(self, request: web.Request) -> web.StreamResponse:
        """Reject unsupported methods."""
        return web.Response(
            status=HTTPStatus.METHOD_NOT_ALLOWED,
            text="Only POST method is supported",
        )

    @require_admin
    async def post(self, request: web.Request) -> web.StreamResponse:
        """Process JSON-RPC messages over Streamable HTTP."""
        hass = request.app[KEY_HASS]

        if CONTENT_TYPE_JSON not in request.headers.get("accept", ""):
            raise HTTPBadRequest(text=f"Client must accept {CONTENT_TYPE_JSON}")
        if request.content_type != CONTENT_TYPE_JSON:
            raise HTTPBadRequest(text=f"Content-Type must be {CONTENT_TYPE_JSON}")

        try:
            payload = await request.json()
            message = types.JSONRPCMessage.model_validate(payload)
        except ValueError as err:
            raise HTTPBadRequest(text="Request must be a JSON-RPC message") from err

        if not isinstance(message.root, JSONRPCRequest):
            return web.Response(status=HTTPStatus.ACCEPTED)

        server = await create_server(hass)
        options = await hass.async_add_executor_job(server.create_initialization_options)
        streams = _create_streams()

        async def run_server() -> None:
            await server.run(
                streams.read_stream,
                streams.write_stream,
                options,
                stateless=True,
            )

        async with asyncio.timeout(TIMEOUT_SECONDS), anyio.create_task_group() as tg:
            tg.start_soon(run_server)
            await streams.read_stream_writer.send(SessionMessage(message))
            session_message = await anext(streams.write_stream_reader)
            tg.cancel_scope.cancel()

        return web.json_response(
            data=session_message.message.model_dump(by_alias=True, exclude_none=True)
        )
