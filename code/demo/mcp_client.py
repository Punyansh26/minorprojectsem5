"""Keep MCP transport lifetime in one async scope, including Streamlit reruns."""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from time import perf_counter

from jsonschema import ValidationError, validate
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import STATE_PATH, MCP_TIMEOUT, ROOT
from shop import error


@asynccontextmanager
async def connect(session_id: str, turn_id: str, state_path=STATE_PATH, confirmation_token=""):
    """Start an isolated server with trusted identity; never pass the Groq key to it."""
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")],
                                  cwd=str(ROOT), env={"DEMO_STATE_PATH": str(state_path),
                                  "DEMO_SESSION_ID": session_id, "DEMO_TURN_ID": turn_id,
                                  "DEMO_CONFIRM_TOKEN": confirmation_token})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=MCP_TIMEOUT)) as session:
            initialization = await session.initialize()
            discovery = await session.list_tools()
            schemas = {t.name: t.inputSchema for t in discovery.tools}
            for schema in schemas.values():
                schema["additionalProperties"] = False
            yield session, discovery.tools, schemas, initialization


async def invoke(session, schemas: dict, name: str, arguments: dict, traces: list) -> dict:
    """Reject invented fields before transmission and retain actual MCP result evidence."""
    start = perf_counter()
    try:
        if name not in schemas:
            output = error("unknown_tool")
        else:
            validate(arguments, schemas[name])
            reply = await session.call_tool(name, arguments=arguments)
            if reply.isError:
                output = error("tool_validation_failed")
            elif reply.structuredContent is not None:
                output = reply.structuredContent
            else:
                output = json.loads(next(c.text for c in reply.content if c.type == "text"))
    except (ValidationError, ValueError, StopIteration):
        output = error("tool_validation_failed")
    public_output = {k: v for k, v in output.items() if k != "confirmation_token"}
    traces.append({"transport": "MCP stdio", "tool": name, "arguments": arguments,
                   "result": public_output, "duration_ms": round((perf_counter() - start) * 1000, 1)})
    return output


async def direct_async(session_id, turn_id, name, arguments, state_path=STATE_PATH, confirmation_token=""):
    """Make manual shopping controls demonstrate the same protocol as Groq-selected tools."""
    traces = []
    async with connect(session_id, turn_id, state_path, confirmation_token) as (session, _, schemas, _):
        output = await invoke(session, schemas, name, arguments, traces)
    return output, traces


def direct(session_id, turn_id, name, arguments, state_path=STATE_PATH, confirmation_token=""):
    """Bridge synchronous Streamlit controls to a complete MCP session."""
    return asyncio.run(direct_async(session_id, turn_id, name, arguments, state_path, confirmation_token))


async def inspect_async(session_id, turn_id, state_path=STATE_PATH):
    """Verify initialization and enumerate actual server capabilities without an API key."""
    async with connect(session_id, turn_id, state_path) as (session, tools, schemas, init):
        catalogue = await invoke(session, schemas, "search_products", {}, [])
        cart = await invoke(session, schemas, "view_cart", {}, [])
        return {"server": init.serverInfo.name, "protocol_version": init.protocolVersion,
                "tools": [{"name": t.name, "description": t.description, "inputSchema": schemas[t.name]}
                          for t in tools], "catalogue": catalogue, "cart": cart}


def inspect_server(session_id, turn_id, state_path=STATE_PATH):
    """Provide a keyless startup health and discovery check."""
    return asyncio.run(inspect_async(session_id, turn_id, state_path))
