"""Grounded, concise templates; draft Chhattisgarhi needs native-speaker review."""

LANGUAGES = {"छत्तीसगढ़ी (प्रयोगात्मक)": "hne", "हिन्दी": "hi", "English": "en"}


def render(output: dict, language: str) -> str:
    """Speak backend facts without letting free-form LLM prose invent advice or prices."""
    en, cg = language == "en", language == "hne"
    template = output.get("response_template_id", "error")
    def choose(english, hindi, chhattisgarhi=None):
        return english if en else (chhattisgarhi if cg and chhattisgarhi else hindi)
    def product(p):
        return f"{p['name'] if en else p['name_hi']} ({p['product_id']}), {p['price_display']}" + (
            choose(" — out of stock", " — उपलब्ध नहीं", " — अभी नइ हे") if p.get("stock", 1) == 0 else "")
    def cart_text(cart):
        lines = [f"{p['quantity']} × {p['name'] if en else p['name_hi']}: {p['line_total_display']}" for p in cart["items"]]
        return "; ".join(lines) + choose(". Total: ", "। कुल: ", "। कुल दाम: ") + cart["total_display"]
    if template == "error" or not output.get("ok"):
        code = output.get("error")
        messages = {
            "unknown_product": ("I couldn't find that product. Please give its name again.", "वह सामान नहीं मिला। नाम फिर से बताइए।"),
            "unknown_cart_item": ("That item is not in your cart.", "वह सामान आपकी टोकरी में नहीं है।"),
            "insufficient_stock": ("Not enough stock. Please choose fewer packages or another item.", "इतना सामान उपलब्ध नहीं है। कम पैकेट या दूसरा सामान चुनिए।"),
            "invalid_quantity": ("Please give a valid whole number of packages.", "कृपया पैकेट की सही पूरी संख्या बताइए।"),
            "unit_mismatch": ("Please use the package unit shown for this product.", "इस सामान के लिए दिखाया गया पैकेट या बोरी वाला माप बताइए।"),
            "empty_cart": ("Your cart is empty.", "आपकी टोकरी खाली है।"),
            "stale_checkout": ("The cart changed. Please review checkout again.", "टोकरी बदल गई है। ऑर्डर फिर से देखकर पुष्टि करें।"),
            "unverified_rate_metadata": ("I have no verified field application rate for this product. Please ask your local KVK. I can help with package prices.", "इस सामान की खेत में उपयोग मात्रा का सत्यापित डेटा नहीं है। स्थानीय कृषि विज्ञान केंद्र से पूछिए। मैं पैकेट का दाम बता सकता हूँ।"),
        }
        pair = messages.get(code, ("That action could not be completed. Check your cart and try a clearer request.", "काम पूरा नहीं हुआ। टोकरी देखिए और बात फिर से साफ बताइए।"))
        return choose(*pair)
    if template in {"products", "ambiguous"}:
        products = output["products"]
        if not products:
            return choose("No matching demo products found.", "इस नाम का सामान नहीं मिला।", "ये नाम के सामान नइ मिलिस।")
        prefix = choose("Which one do you mean? ", "आप कौन सा सामान चाहते हैं? ", "तुमन कऊन सामान चाहथव? ") if template == "ambiguous" else ""
        return prefix + "; ".join(product(p) for p in products[:5]) + (
            choose(". More items are shown in the catalogue.", "। बाकी सामान सूची में देखिए।") if len(products) > 5 else "")
    if template in {"product", "price"}:
        text = product(output["product"])
        if template == "price":
            text += choose(f". {output['quantity']} unit(s): ", f"। {output['quantity']} इकाई का दाम: ") + output["total_display"]
        return text
    if template in {"cart", "added", "removed"}:
        prefix = {"cart": "", "added": choose("Added. ", "जोड़ दिया। ", "टोकरी म जोड़ दे हवं। "),
                  "removed": choose("Removed. ", "हटा दिया। ", "टोकरी ले हटा दे हवं। ")}[template]
        return prefix + (cart_text(output) if output["items"] else choose("Your cart is empty.", "टोकरी खाली है।", "टोकरी खाली हे।"))
    if template == "checkout_preview":
        return cart_text(output["cart"]) + choose(
            '. This is a demo order. Press confirm, or say "confirm demo order".',
            '। यह डेमो ऑर्डर है। पुष्टि बटन दबाएँ या बोलें: "डेमो ऑर्डर पक्का करो"।',
            '। ये डेमो ऑर्डर हे। पुष्टि बटन दबावव या बोलव: "डेमो ऑर्डर पक्का करो"।')
    if template == "order":
        return choose("Demo order created: ", "डेमो ऑर्डर बन गया: ", "डेमो ऑर्डर बन गे: ") + output["order_id"] + ". " + cart_text(output["cart"]) + choose(". No payment or delivery.", "। कोई भुगतान या डिलीवरी नहीं होगी।")
    if template == "referral":
        return choose("I can help you shop, but cannot diagnose crops or recommend treatments or doses. Please ask your local Krishi Vigyan Kendra.",
                      "मैं खरीदारी में मदद कर सकता हूँ, लेकिन फसल की बीमारी, इलाज या दवा की मात्रा नहीं बता सकता। स्थानीय कृषि विज्ञान केंद्र से सलाह लीजिए।",
                      "मैं सामान खरीदे म मदद कर सकथंव। फसल के बीमारी, इलाज अउ दवाई के मात्रा नइ बता सकंव। अपन नजदीक के कृषि विज्ञान केंद्र म सलाह लेवव।")
    questions = {
        "product": ("Which product do you want? Please name it.", "कौन सा सामान चाहिए? उसका नाम बताइए।"),
        "quantity": ("How many packs, bags, pieces, or pairs do you want?", "कितने पैकेट, बोरी, नग या जोड़ी चाहिए?"),
        "unit": ("Do you mean packs, bags, pieces, or pairs?", "आपका मतलब पैकेट, बोरी, नग या जोड़ी है?"),
        "shopping_only": ("I can find products, tell prices, manage your cart, and create demo orders.", "मैं सामान, दाम, टोकरी और डेमो ऑर्डर में मदद कर सकता हूँ।"),
        "repeat": ("Please repeat your shopping request.", "खरीदारी की बात फिर से बताइए।"),
    }
    return choose(*questions.get(output.get("reason"), questions["repeat"]))
