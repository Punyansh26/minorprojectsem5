"""Observable cart, money, stock, and confirmation invariants."""

import concurrent.futures
import json

import pytest

from shop import Shop


@pytest.fixture
def shop(tmp_path):
    return Shop(tmp_path / "test.json", "alice", "turn-1")


def test_aliases_and_ambiguity(shop):
    assert shop.resolve_product("मोला धान बीज चाही")["product"]["product_id"] == "SEED01"
    assert shop.resolve_product("khurpi")["product"]["product_id"] == "TOOL02"
    assert shop.resolve_product("जैविक खाद")["response_template_id"] == "ambiguous"
    assert shop.search_products("not-a-product")["products"] == []


def test_idempotency_and_money(shop):
    first = shop.add_to_cart("SEED01", 2, "pack")
    assert first == shop.add_to_cart("SEED01", 2, "pack")
    assert first["total_paise"] == 90000
    assert first["total_display"] == "₹900.00"
    shop.turn_id = "turn-2"
    assert shop.add_to_cart("SEED01", 1, "pack")["item_count"] == 3


@pytest.mark.parametrize("quantity", [0, -2, 1.5, True, 101])
def test_invalid_quantities_do_not_mutate(shop, quantity):
    assert not shop.add_to_cart("SEED01", quantity, "pack")["ok"]
    assert shop.view_cart()["items"] == []


def test_unknown_product_units_stock(shop):
    assert shop.add_to_cart("FAKE", 1, "pack")["error"] == "unknown_product"
    assert shop.add_to_cart("SEED01", 2, "kg")["error"] == "unit_mismatch"
    assert shop.add_to_cart("TOOL04", 1, "pair")["error"] == "insufficient_stock"
    assert shop.view_cart()["items"] == []


def test_session_ownership_and_partial_removal(shop):
    shop.add_to_cart("SEED01", 3, "pack")
    bob = Shop(shop.path, "bob", "turn-1")
    assert bob.view_cart()["items"] == []
    assert bob.remove_from_cart("SEED01")["error"] == "unknown_cart_item"
    assert shop.remove_from_cart("SEED01", 1)["item_count"] == 2
    assert shop.remove_from_cart("SEED01", 1)["item_count"] == 2


def test_price_locked_at_addition(shop):
    shop.add_to_cart("SEED01", 1, "pack")
    with shop.connection() as state:
        state["products"]["SEED01"]["price_paise"] = 50000
    shop.turn_id = "turn-2"
    assert shop.add_to_cart("SEED01", 1, "pack")["total_paise"] == 90000


def test_checkout_confirmation_and_replay(shop):
    shop.add_to_cart("SEED01", 2, "pack")
    preview = shop.checkout()
    assert shop.view_cart()["item_count"] == 2
    assert not shop.confirm_checkout("forged")["ok"]
    order = shop.confirm_checkout(preview["confirmation_token"])
    assert order["simulated"] and order["cart"]["total_paise"] == 90000
    assert shop.view_cart()["items"] == []
    shop.turn_id = "new-turn"
    assert shop.confirm_checkout(preview["confirmation_token"]) == order
    assert shop.get_product_details("SEED01")["product"]["stock"] == 38


def test_stale_preview_rejected(shop):
    shop.add_to_cart("SEED01", 1, "pack")
    preview = shop.checkout()
    shop.remove_from_cart("SEED01")
    assert shop.confirm_checkout(preview["confirmation_token"])["error"] == "stale_checkout"


def test_stock_contention_does_not_oversell(shop):
    shops = [Shop(shop.path, name, "turn") for name in ("a", "b")]
    tokens = []
    for buyer in shops:
        assert buyer.add_to_cart("TOOL03", 10, "piece")["ok"]
        tokens.append(buyer.checkout()["confirmation_token"])
    with concurrent.futures.ThreadPoolExecutor() as pool:
        futures = [pool.submit(buyer.confirm_checkout, token) for buyer, token in zip(shops, tokens)]
        outputs = [f.result() for f in futures]
    assert sum(o["ok"] for o in outputs) == 1
    assert shop.get_product_details("TOOL03")["product"]["stock"] == 0


def test_no_unsourced_agricultural_rate(shop):
    assert shop.calculate_required_quantity("SEED01", 2, "acre")["error"] == "unverified_rate_metadata"


def test_json_persists_without_database(shop):
    shop.add_to_cart("SEED01", 2, "pack")
    state = json.loads(shop.path.read_text())
    assert state["carts"]["alice"]["SEED01"]["quantity"] == 2
    assert Shop(shop.path, "alice", "new-turn").view_cart()["total_paise"] == 90000


def test_failed_write_leaves_original_json(shop, monkeypatch):
    import shop as module
    original = shop.path.read_bytes()
    def failed_replace(*args):
        raise OSError("disk full")
    monkeypatch.setattr(module.os, "replace", failed_replace)
    with pytest.raises(OSError):
        shop.add_to_cart("SEED01", 1, "pack")
    assert shop.path.read_bytes() == original
    assert not list(shop.path.parent.glob("*.tmp"))


def test_corrupt_json_is_not_silently_reset(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{broken")
    with pytest.raises(ValueError):
        Shop(path, "a", "b")
    assert path.read_text() == "{broken"
