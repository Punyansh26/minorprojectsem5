"""Real stdio MCP adapter; stdout is reserved for JSON-RPC protocol messages."""

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from config import CONFIRM_TOKEN, STATE_PATH, MAX_QUANTITY, SESSION_ID, TURN_ID
from shop import Shop, error, result

server = FastMCP("Farmer Shopping Demo")
shop = Shop(STATE_PATH, SESSION_ID, TURN_ID)
Count = Annotated[int, Field(strict=True, ge=1, le=MAX_QUANTITY)]
ProductID = Annotated[str, Field(min_length=1, max_length=40)]
Mention = Annotated[str, Field(min_length=1, max_length=200)]
READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@server.tool(annotations=READ)
def search_products(query: str = "", category: Literal["all", "seeds", "fertilizers", "tools"] = "all") -> dict:
    """Search demo products by English, Hindi, Chhattisgarhi or Romanized aliases. Returns IDs and sellable units."""
    return shop.search_products(query, category)


@server.tool(annotations=READ)
def resolve_product(mention: Mention) -> dict:
    """Resolve a spoken product mention. Multiple matches require clarification, never guessing."""
    return shop.resolve_product(mention)


@server.tool(annotations=READ)
def get_product_details(product_id: ProductID) -> dict:
    """Read grounded product name, package size, price, stock, and synthetic description."""
    return shop.get_product_details(product_id)


@server.tool(annotations=READ)
def check_price(product_id: ProductID, quantity: Count = 1, unit: str = "") -> dict:
    """Calculate cost for a number of sellable packs, bags, pieces or pairs; not an application rate."""
    return shop.check_price(product_id, quantity, unit)


@server.tool(annotations=READ)
def view_cart() -> dict:
    """Read this session's cart, line IDs, package quantities, and total."""
    return shop.view_cart()


@server.tool(annotations=WRITE)
def add_to_cart(product_id: ProductID, quantity: Count, unit: Literal["pack", "bag", "piece", "pair"]) -> dict:
    """Add the explicitly requested count of sellable units. Resolve product first; ask if count/unit is missing."""
    return shop.add_to_cart(product_id, quantity, unit)


@server.tool(annotations=WRITE)
def remove_from_cart(cart_item_id: ProductID, quantity: Count | None = None) -> dict:
    """Remove a verified cart line; optional quantity reduces its sellable-unit count. Read cart first."""
    return shop.remove_from_cart(cart_item_id, quantity)


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
def checkout() -> dict:
    """Prepare a SIMULATED checkout preview. A separate explicit user confirmation is required to create an order."""
    return shop.checkout()


@server.tool(annotations=WRITE)
def confirm_checkout() -> dict:
    """Host-only confirmation. Requires a capability supplied by the application, unavailable to the model."""
    return shop.confirm_checkout(CONFIRM_TOKEN) if CONFIRM_TOKEN else error("confirmation_required")


@server.tool(annotations=READ)
def calculate_required_quantity(product_id: ProductID,
                                area_value: Annotated[float, Field(gt=0, le=10000)],
                                area_unit: Literal["acre", "hectare"]) -> dict:
    """Field-quantity requests must use this tool. Demo metadata is unverified, so it refuses with no numeric rate."""
    return shop.calculate_required_quantity(product_id, area_value, area_unit)


@server.tool(annotations=READ)
def request_clarification(reason: Literal["product", "quantity", "unit", "shopping_only", "repeat"]) -> dict:
    """Ask a short fixed question when a shopping request is ambiguous, incomplete, or out of scope."""
    return result("clarification", reason=reason)


@server.tool(annotations=READ)
def refuse_and_refer() -> dict:
    """Refuse crop diagnosis, treatment selection, pesticide dosage, or application advice; refer to local KVK."""
    return result("referral")


@server.resource("shopping://demo/about")
def about() -> str:
    """Expose demo scope and data provenance for MCP inspectors."""
    return "shopping.demo.v1: synthetic catalogue and prices; simulated orders; no verified rates; session identity injected by host."


if __name__ == "__main__":
    server.run(transport="stdio")
