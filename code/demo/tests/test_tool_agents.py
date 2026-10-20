"""Task 08 — deterministic tool-agent optimizations.

Cover the LLM-free layers added for tool calling: rule-based tool retrieval
(§b), deterministic single-product add slot filling (§e), read-only parallel
batch execution (§c), and the content-free acknowledgement (§h). The pure
helpers need no provider; loop behaviour uses the FakeGroq pattern so the real
MCP transport still runs.
"""

import asyncio
import json
from types import SimpleNamespace

from groq.types.chat import ChatCompletionMessage

from assistant import (
    ACKNOWLEDGEMENTS,
    acknowledgement,
    add_intent,
    run_async,
    select_tools,
)
from shop import Shop


# Full tool set the server exposes to the model (confirm_checkout is excluded).
AVAILABLE = {
    "search_products", "resolve_product", "get_product_details", "check_price",
    "view_cart", "add_to_cart", "remove_from_cart", "checkout",
    "calculate_required_quantity", "request_clarification", "refuse_and_refer",
}


class FakeGroq:
    """Replay scripted tool calls (or a batch) while real MCP executes them."""

    def __init__(self, steps):
        self.steps = iter(steps)
        self.chat = SimpleNamespace(completions=self)
        self.exposed_counts = []

    async def create(self, **kwargs):
        self.exposed_counts.append(len(kwargs["tools"]))
        assert all(t["function"]["name"] != "confirm_checkout" for t in kwargs["tools"])
        step = next(self.steps)
        if isinstance(step, Exception):
            raise step
        if step is None:
            message = ChatCompletionMessage(role="assistant", content="prose never shown")
        else:
            # A step may be one (name, args) tuple or a list of them (a batch).
            pairs = step if isinstance(step, list) else [step]
            tool_calls = [{"id": f"call-{i}", "type": "function",
                           "function": {"name": n, "arguments": json.dumps(a)}}
                          for i, (n, a) in enumerate(pairs)]
            message = ChatCompletionMessage(role="assistant", tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# --- §b: tool retrieval ----------------------------------------------------

def test_select_tools_narrows_on_add_intent():
    chosen = select_tools("धान के दो पैकेट डालो", AVAILABLE)
    assert "add_to_cart" in chosen and "resolve_product" in chosen
    # Safety/clarify are always retained for any matched turn.
    assert {"refuse_and_refer", "request_clarification"} <= chosen
    # Unrelated writes are dropped from the exposed set.
    assert "remove_from_cart" not in chosen
    assert chosen < AVAILABLE


def test_select_tools_price_intent():
    chosen = select_tools("dhaan ka daam kitna hai", AVAILABLE)
    assert {"check_price", "resolve_product"} <= chosen
    assert "add_to_cart" not in chosen


def test_select_tools_falls_back_to_full_set_on_low_confidence():
    # A turn no rule recognises must keep every tool (never lose the needed one).
    assert select_tools("blargh zxcv qwerty", AVAILABLE) == AVAILABLE


def test_select_tools_result_is_subset_of_available():
    # Rules may propose tools the server does not expose; never leak them.
    small = {"view_cart", "refuse_and_refer"}
    assert select_tools("checkout karo", small) <= small


# --- §e: deterministic add intent -----------------------------------------

def test_add_intent_parses_spoken_and_digit_counts():
    assert add_intent("धान बीज दो पैकेट डालो") == 2
    assert add_intent("add 3 paddy packs") == 3
    assert add_intent("dhaan beej daal do") == 1  # verb present, no count → 1


def test_add_intent_rejects_non_add_turns():
    assert add_intent("dhaan ka daam kitna hai") is None      # question/price
    assert add_intent("टोकरी दिखाओ") is None                   # cart query
    assert add_intent("धान बीज मत डालो") is None                # negation
    assert add_intent("don't add paddy") is None               # negation (en)
    assert add_intent("remove paddy") is None                  # removal
    assert add_intent("फसल की बीमारी की दवाई डालो") is None     # safety precedence


# --- §e end-to-end: zero LLM calls on an unambiguous add -------------------

def test_deterministic_add_uses_no_llm(tmp_path):
    fake = FakeGroq([])  # no steps: any model call would raise StopIteration
    output = asyncio.run(run_async("धान बीज दो पैकेट डालो", "hi", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    assert output["used_llm"] is False
    assert fake.exposed_counts == []                       # provider never called
    assert [t["tool"] for t in output["traces"]] == ["resolve_product", "add_to_cart"]
    assert output["cart"]["total_paise"] == 90000          # 2 × ₹450
    assert "Added" in output["text"] or "जोड़" in output["text"]


def test_deterministic_add_defaults_to_one(tmp_path):
    fake = FakeGroq([])
    output = asyncio.run(run_async("khurpi daal do", "en", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    assert output["used_llm"] is False
    assert output["cart"]["item_count"] == 1
    assert output["cart"]["items"][0]["product_id"] == "TOOL02"


def test_ambiguous_add_falls_through_to_model(tmp_path):
    # "जैविक खाद" matches two products → resolve is ambiguous → model handles it.
    fake = FakeGroq([("search_products", {"query": "जैविक खाद"}), None])
    output = asyncio.run(run_async("जैविक खाद डालो", "hi", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    assert output["used_llm"] is True
    assert fake.exposed_counts            # the model was consulted
    assert output["cart"]["items"] == []  # nothing added without disambiguation


def test_deterministic_add_never_fires_on_safety(tmp_path):
    fake = FakeGroq([])  # safety path is pre-LLM; no model call expected
    output = asyncio.run(run_async("फसल की बीमारी की दवाई डालो", "hne", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    assert [t["tool"] for t in output["traces"]] == ["refuse_and_refer"]
    assert output["cart"]["items"] == []


# --- §c: read-only parallel batch -----------------------------------------

def test_read_only_batch_runs_in_parallel(tmp_path):
    # Two independent reads in one batch are allowed and both execute.
    batch = [("check_price", {"product_id": "SEED01", "quantity": 1}),
             ("check_price", {"product_id": "SEED02", "quantity": 1})]
    fake = FakeGroq([batch])
    output = asyncio.run(run_async("dhaan aur gehu ka daam batao", "en", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    tools = [t["tool"] for t in output["traces"] if t["tool"] == "check_price"]
    assert len(tools) == 2
    assert output["warning"] is None


def test_write_in_batch_is_rejected_without_mutation(tmp_path):
    # A batch mixing a read and a write keeps the single-write invariant.
    batch = [("view_cart", {}),
             ("add_to_cart", {"product_id": "SEED01", "quantity": 1, "unit": "pack"})]
    fake = FakeGroq([batch])
    output = asyncio.run(run_async("add paddy and show cart", "en", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    assert "parallel" in (output["warning"] or "")
    assert output["cart"]["items"] == []            # nothing was written
    assert Shop(tmp_path / "t.json", "a", "1").view_cart()["items"] == []


def test_parallel_writes_are_rejected(tmp_path):
    batch = [("add_to_cart", {"product_id": "SEED01", "quantity": 1, "unit": "pack"}),
             ("add_to_cart", {"product_id": "SEED02", "quantity": 1, "unit": "pack"})]
    fake = FakeGroq([batch])
    output = asyncio.run(run_async("add paddy and wheat", "en", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    assert "parallel" in (output["warning"] or "")
    assert output["cart"]["items"] == []


# --- §h: acknowledgement ---------------------------------------------------

def test_acknowledgement_is_content_free():
    for lang in ("en", "hi", "hne"):
        text = acknowledgement(lang)
        assert text == ACKNOWLEDGEMENTS[lang]
        # Must not assert any shopping fact (no price/stock/product claim).
        lowered = text.casefold()
        for forbidden in ("₹", "stock", "price", "रुपय", "available", "दाम"):
            assert forbidden not in lowered
    assert acknowledgement("zz") == ACKNOWLEDGEMENTS["hi"]  # safe default


def test_run_async_returns_acknowledgement(tmp_path):
    fake = FakeGroq([])
    output = asyncio.run(run_async("टोकरी दिखाओ", "hne", "unused", "a", "1",
                                   state_path=tmp_path / "t.json", client=fake))
    assert output["acknowledgement"] == ACKNOWLEDGEMENTS["hne"]
