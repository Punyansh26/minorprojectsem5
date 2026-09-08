"""Speak catalogue numbers explicitly because the local VITS vocabulary lacks Latin digits."""

import re

_SMALL = (
    "शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
    "बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस "
    "चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ "
    "साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उनासी "
    "अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे"
).split()


def number_words(value: int) -> str:
    """Preserve whole-number quantities and prices in words supported by the voice."""
    if value < 100:
        return _SMALL[value]
    for size, label in ((10000000, "करोड़"), (100000, "लाख"), (1000, "हजार"), (100, "सौ")):
        if value >= size:
            quotient, remainder = divmod(value, size)
            return number_words(quotient) + " " + label + (" " + number_words(remainder) if remainder else "")
    raise ValueError("Invalid spoken number")


def prepare_speech_text(text: str) -> str:
    """Keep displayed facts unchanged while expanding money and stripping screen-only IDs."""
    def currency(match):
        rupees = int(match[1].replace(",", ""))
        paise = int(match[2] or "0")
        return number_words(rupees) + " रुपये" + (" " + number_words(paise) + " पैसे" if paise else "")
    text = re.sub(r"₹([0-9,]+)(?:\.([0-9]{2}))?", currency, text)
    text = re.sub(r"\s*\([A-Z]+[0-9]+\)", "", text)
    text = re.sub(r"DEMO-[A-F0-9]+", "पहचान स्क्रीन पर देखिए", text)
    text = re.sub(r"[0-9]+", lambda m: number_words(int(m[0])), text)
    return text.replace("×", "गुना").replace(";", "।")
