"""Exercise the actual child process and MCP JSON-RPC transport without Groq."""

import asyncio

from mcp_client import connect, invoke


def test_real_mcp_flow(tmp_path):
    async def flow():
        async with connect("alice", "first", tmp_path / "mcp.json") as (session, tools, schemas, init):
            assert init.serverInfo.name == "Farmer Shopping Demo"
            assert len(tools) == 12
            assert "session_id" not in schemas["add_to_cart"]["properties"]
            traces = []
            p = await invoke(session, schemas, "resolve_product", {"mention": "धान"}, traces)
            assert p["product"]["product_id"] == "SEED01"
            args = {"product_id": "SEED01", "quantity": 2, "unit": "pack"}
            assert not (await invoke(session, schemas, "add_to_cart", {**args, "price": 1}, traces))["ok"]
            assert not (await invoke(session, schemas, "add_to_cart", {**args, "quantity": True}, traces))["ok"]
            first = await invoke(session, schemas, "add_to_cart", args, traces)
            assert first["total_paise"] == 90000
            assert await invoke(session, schemas, "add_to_cart", args, traces) == first
            preview = await invoke(session, schemas, "checkout", {}, traces)
            assert "confirmation_token" not in traces[-1]["result"]
            assert (await invoke(session, schemas, "confirm_checkout", {}, traces))["error"] == "confirmation_required"
            resources = await session.list_resources()
            assert str(resources.resources[0].uri) == "shopping://demo/about"
        async with connect("alice", "confirm", tmp_path / "mcp.json", preview["confirmation_token"]) as (session, _, schemas, _):
            output = await invoke(session, schemas, "confirm_checkout", {}, [])
            assert output["response_template_id"] == "order"
            assert (await invoke(session, schemas, "view_cart", {}, []))["items"] == []
    asyncio.run(flow())


def test_parallel_mcp_processes_preserve_json_writes(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from mcp_client import direct
    from shop import Shop
    path = tmp_path / "concurrent.json"
    def add(turn):
        return direct("same-session", str(turn), "add_to_cart",
                      {"product_id": "SEED01", "quantity": 1, "unit": "pack"}, state_path=path)[0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(add, range(4)))
    assert all(o["ok"] for o in outputs)
    assert Shop(path, "same-session", "inspect").view_cart()["item_count"] == 4
