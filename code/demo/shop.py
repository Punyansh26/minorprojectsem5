"""Shopping facts persisted as locked, atomically replaced JSON; no database."""

import hashlib
import json
import os
import unicodedata
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from filelock import FileLock
from rapidfuzz import fuzz

from config import MAX_QUANTITY, ROOT


def money(paise: int) -> str:
    """Format integer money without introducing floating-point arithmetic."""
    return f"₹{paise // 100:,}.{paise % 100:02d}"


def result(template: str, **data) -> dict:
    """Keep tool results structured so speech is assembled from grounded slots."""
    return {"ok": True, "schema_version": "shopping.demo.v1", "response_template_id": template, **data}


def error(code: str) -> dict:
    """Expose stable recoverable failures without leaking internal exceptions."""
    return {"ok": False, "schema_version": "shopping.demo.v1", "response_template_id": "error", "error": code}


def normalize(value: str) -> str:
    """Keep Devanagari marks intact during alias matching."""
    return unicodedata.normalize("NFC", value).casefold().strip()


# Minimum rapidfuzz score (0-100) to count as a match.  70 is lenient enough
# to forgive typical STT errors (dhan→dhaan, tomater→tamatar, hansiya→hasiya)
# while still rejecting unrelated terms.
FUZZY_THRESHOLD = 70


def fuzzy_match(query: str, term: str) -> bool:
    """Return True if query approximately matches term, tolerating transcription noise."""
    if not query or not term:
        return False
    # Exact substring is always a hit (fast path).
    nq, nt = normalize(query), normalize(term)
    if nq in nt or nt in nq:
        return True
    # Use the better of full-ratio (overall similarity) and
    # token-sort-ratio (handles word-order differences).
    # Partial-ratio is deliberately excluded: it produces false positives
    # when short queries appear as anagrams inside longer terms
    # (e.g. "dhan" inside "hand sickle").
    score = max(fuzz.ratio(nq, nt), fuzz.token_sort_ratio(nq, nt))
    return score >= FUZZY_THRESHOLD


class Shop:
    """Bind session identity outside model arguments and serialize cross-process writes."""

    def __init__(self, path: Path, session_id: str, turn_id: str):
        self.path = Path(path).resolve()
        self.session_id, self.turn_id = session_id, turn_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection():
            pass

    @contextmanager
    def connection(self):
        """Lock a separate file across replacement; leave the original intact on failure."""
        with FileLock(str(self.path) + ".lock", timeout=10):
            exists = self.path.exists()
            if exists:
                state = json.loads(self.path.read_text(encoding="utf-8"))
                if state.get("version") != 1 or any(not isinstance(state.get(k), dict) for k in
                        ("products", "carts", "requests", "previews", "orders")):
                    raise ValueError("Invalid shop JSON state; restore a valid file or choose DEMO_STATE_PATH.")
            else:
                products = json.loads((ROOT / "data/catalogue.json").read_text(encoding="utf-8"))
                state = {"version": 1, "products": {p["product_id"]: p for p in products},
                         "carts": {}, "requests": {}, "previews": {}, "orders": {}}
            original = deepcopy(state)
            yield state
            if exists and state == original:
                return
            temporary = None
            try:
                with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                        prefix=self.path.name + ".", suffix=".tmp", delete=False) as out:
                    temporary = Path(out.name)
                    json.dump(state, out, ensure_ascii=False, indent=2)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    def _product(self, product):
        return {**product, "price_display": money(product["price_paise"])}

    def search_products(self, query: str = "", category: str = "all") -> dict:
        """Use fuzzy multilingual aliases over the small synthetic catalogue."""
        if category not in {"all", "seeds", "fertilizers", "tools"}:
            return error("invalid_category")
        q = normalize(query)
        group_aliases = {"बीज": "seeds", "beej": "seeds", "seed": "seeds", "seeds": "seeds",
                         "खाद": "fertilizers", "khaad": "fertilizers", "fertilizer": "fertilizers",
                         "औजार": "tools", "tools": "tools"}
        matched_group = group_aliases.get(q)
        if not matched_group and q:
            for alias, group in group_aliases.items():
                if fuzz.ratio(q, normalize(alias)) >= 75:
                    matched_group = group
                    break
        with self.connection() as state:
            products = [self._product(p) for _, p in sorted(state["products"].items())]
        scored = []
        q_words = q.split()
        for p in products:
            if category != "all" and p["category"] != category:
                continue
            if not q:
                scored.append((100, p))
                continue
            if matched_group and matched_group == p["category"]:
                scored.append((88, p))
                continue
            terms = [p["product_id"], p["name"], p["name_hi"], *p["aliases"]]
            norm_terms = [normalize(t) for t in terms if t]
            best_score = 0
            for nt in norm_terms:
                if q == nt:
                    best_score = 100
                    break
                if nt in q:
                    q_padded = f" {q} "
                    if f" {nt} " in q_padded:
                        score = 95
                    else:
                        score = 85
                    best_score = max(best_score, score)
                if len(q) >= 3 and q in nt:
                    best_score = max(best_score, 90)
                best_score = max(best_score, fuzz.ratio(q, nt), fuzz.token_sort_ratio(q, nt))
                if len(q_words) > 1:
                    nt_words_count = len(nt.split())
                    min_k = max(1, nt_words_count - 1)
                    max_k = min(len(q_words), nt_words_count + 1)
                    for k in range(min_k, max_k + 1):
                        for i in range(len(q_words) - k + 1):
                            ngram = " ".join(q_words[i:i+k])
                            best_score = max(best_score, fuzz.ratio(ngram, nt), fuzz.token_sort_ratio(ngram, nt))
            if best_score >= FUZZY_THRESHOLD:
                scored.append((best_score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] >= 90:
            top = scored[0][0]
            scored = [item for item in scored if item[0] >= top - 5]
        matches = [p for _, p in scored]
        return result("products", products=matches, match_count=len(matches))

    def resolve_product(self, mention: str) -> dict:
        """Expose ambiguity instead of choosing a plausible product silently."""
        found = self.search_products(mention)["products"]
        if not found:
            return error("unknown_product")
        if len(found) != 1:
            return result("ambiguous", products=found)
        return result("product", product=found[0])

    def get_product_details(self, product_id: str) -> dict:
        """Read product facts by a verified identifier."""
        with self.connection() as state:
            p = state["products"].get(product_id)
            return result("product", product=self._product(p)) if p else error("unknown_product")

    def check_price(self, product_id: str, quantity: int = 1, unit: str = "") -> dict:
        """Compute package cost, never a field application rate."""
        output = self.get_product_details(product_id)
        if not output["ok"]:
            return output
        p = output["product"]
        if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
            return error("invalid_quantity")
        if unit and unit != p["unit"]:
            return error("unit_mismatch")
        return result("price", product=p, quantity=quantity, total_paise=p["price_paise"] * quantity,
                      total_display=money(p["price_paise"] * quantity))

    def _cart(self, state) -> dict:
        items = []
        for product_id, line in sorted(state["carts"].get(self.session_id, {}).items()):
            p = state["products"][product_id]
            total = line["quantity"] * line["price_paise"]
            items.append({"cart_item_id": product_id, "product_id": product_id,
                          "name": p["name"], "name_hi": p["name_hi"], "unit": p["unit"],
                          **line, "price_display": money(line["price_paise"]),
                          "line_total_paise": total, "line_total_display": money(total)})
        total = sum(p["line_total_paise"] for p in items)
        return result("cart", items=items, total_paise=total, total_display=money(total),
                      item_count=sum(p["quantity"] for p in items))

    def view_cart(self) -> dict:
        """Return confirmed session facts with prices locked on first addition."""
        with self.connection() as state:
            return self._cart(state)

    def _write(self, name: str, args: dict, action, *, request_id=None) -> dict:
        key = hashlib.sha256(json.dumps([self.session_id, request_id or self.turn_id, name, args],
                                       sort_keys=True).encode()).hexdigest()
        with self.connection() as state:
            if key in state["requests"]:
                return state["requests"][key]
            output = action(state)
            state["requests"][key] = output
            return output

    def add_to_cart(self, product_id: str, quantity: int, unit: str) -> dict:
        """Add sellable packages atomically and deduplicate retries within a turn."""
        def action(state):
            p = state["products"].get(product_id)
            if not p:
                return error("unknown_product")
            if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
                return error("invalid_quantity")
            if unit != p["unit"]:
                return error("unit_mismatch")
            cart = state["carts"].get(self.session_id, {})
            current = cart.get(product_id, {"quantity": 0, "price_paise": p["price_paise"]})
            total = quantity + current["quantity"]
            if total > p["stock"] or total > MAX_QUANTITY:
                return error("insufficient_stock")
            cart[product_id] = {**current, "quantity": total}
            state["carts"][self.session_id] = cart
            state["previews"].pop(self.session_id, None)
            return {**self._cart(state), "response_template_id": "added"}
        return self._write("add_to_cart", {"product_id": product_id, "quantity": quantity, "unit": unit}, action)

    def remove_from_cart(self, cart_item_id: str, quantity: int | None = None) -> dict:
        """Remove only a line owned by this session; optionally reduce package count."""
        def action(state):
            cart = state["carts"].get(self.session_id, {})
            if cart_item_id not in cart:
                return error("unknown_cart_item")
            current = cart[cart_item_id]["quantity"]
            if quantity is not None and (type(quantity) is not int or not 1 <= quantity <= current):
                return error("invalid_quantity")
            remaining = current - (quantity if quantity is not None else current)
            if remaining:
                cart[cart_item_id]["quantity"] = remaining
            else:
                del cart[cart_item_id]
            state["previews"].pop(self.session_id, None)
            return {**self._cart(state), "response_template_id": "removed"}
        return self._write("remove_from_cart", {"cart_item_id": cart_item_id, "quantity": quantity}, action)

    def checkout(self) -> dict:
        """Prepare a cart-bound preview; this tool cannot create an order."""
        with self.connection() as state:
            cart = self._cart(state)
            if not cart["items"]:
                return error("empty_cart")
            token = str(uuid4())
            state["previews"][self.session_id] = {"token": token, "snapshot": cart}
            return result("checkout_preview", cart=cart, confirmation_token=token, simulated=True)

    def confirm_checkout(self, token: str) -> dict:
        """Commit only the host-confirmed preview and preserve confirmation replay identity."""
        def action(state):
            preview = state["previews"].get(self.session_id)
            cart = self._cart(state)
            if not preview or preview["token"] != token or preview["snapshot"] != cart:
                return error("stale_checkout")
            if any(state["products"][i["product_id"]]["stock"] < i["quantity"] for i in cart["items"]):
                return error("insufficient_stock")
            order = result("order", order_id="DEMO-" + uuid4().hex[:10].upper(), cart=cart, simulated=True)
            for item in cart["items"]:
                state["products"][item["product_id"]]["stock"] -= item["quantity"]
            state["orders"][order["order_id"]] = {"session": self.session_id, "payload": order,
                                                   "created_at": datetime.now(timezone.utc).isoformat()}
            state["carts"].pop(self.session_id, None)
            state["previews"].pop(self.session_id, None)
            return order
        return self._write("confirm_checkout", {"token": token}, action, request_id="checkout:" + token)

    def calculate_required_quantity(self, product_id: str, area_value: float, area_unit: str) -> dict:
        """Refuse field-rate arithmetic because demo fixtures contain no verified rates."""
        if not self.get_product_details(product_id)["ok"]:
            return error("unknown_product")
        return error("unverified_rate_metadata")
