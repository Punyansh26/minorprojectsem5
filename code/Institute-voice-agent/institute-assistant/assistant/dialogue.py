"""Consistent short replies for branches that must not invent institute information."""
import re

COPY = {
    "welcome": (
        "Hello! I’m the IIIT Naya Raipur helpdesk assistant. How can I help with admissions, fees, hostel, or academics?",
        "नमस्ते! मैं IIIT नया रायपुर का हेल्पडेस्क सहायक हूँ। प्रवेश, फीस, हॉस्टल या पढ़ाई के बारे में क्या जानना चाहेंगे?",
        "Namaste! Main IIIT Naya Raipur ka helpdesk assistant hoon. Admissions, fees, hostel ya academics mein kya madad chahiye?",
    ),
    "thanks": ("You’re welcome. Is there anything else about the institute I can help with?", "आपका स्वागत है। संस्थान के बारे में और कोई मदद चाहिए?", "Aapka swagat hai. Institute ke baare mein aur koi madad chahiye?"),
    "out_of_scope": (
        "I can help with IIIT Naya Raipur admissions, fees, hostel, academics, and campus services. What would you like to know about the institute?",
        "मैं IIIT नया रायपुर के प्रवेश, फीस, हॉस्टल, पढ़ाई और परिसर की सेवाओं में मदद कर सकता हूँ। संस्थान के बारे में क्या जानना चाहेंगे?",
        "Main IIIT Naya Raipur ke admissions, fees, hostel, academics aur campus services mein madad kar sakta hoon. Institute ke baare mein kya jaanna chahenge?",
    ),
    "clarify": ("What would you like to know about IIIT Naya Raipur? Please name the topic or process you need help with.", "IIIT नया रायपुर के बारे में क्या जानना चाहेंगे? कृपया विषय या प्रक्रिया बताइए।", "IIIT Naya Raipur ke baare mein kya jaanna chahenge? Topic ya process bataiye."),
    "unavailable": ("The helpdesk service is busy at the moment, so I couldn’t finish checking that. Please ask again in a few seconds, or rephrase your question.", "हेल्पडेस्क सेवा अभी व्यस्त है, इसलिए मैं इसे पूरी तरह जाँच नहीं सका। कृपया कुछ सेकंड बाद फिर पूछें, या अपना सवाल दूसरे शब्दों में पूछें।", "Helpdesk service abhi busy hai, isliye main ise poora check nahi kar saka. Kuch second baad phir poochein, ya sawaal doosre shabdon mein poochein."),
    "rate_limited": (
        "The helpdesk’s answer service is temporarily rate-limited, so I couldn’t finish checking your question. Please wait before trying again.",
        "हेल्पडेस्क की उत्तर सेवा फिलहाल अनुरोधों की सीमा तक पहुँच गई है, इसलिए आपका सवाल जाँच नहीं सका। कृपया कुछ समय बाद फिर कोशिश करें।",
        "Helpdesk ki answer service ki request limit abhi poori ho gayi hai, isliye aapka sawaal check nahi kar saka. Thoda ruk kar phir try karein.",
    ),
    "missing": (
        "I couldn’t verify that from the available institute documents. Would you like me to save your question for staff review?",
        "उपलब्ध संस्थान दस्तावेज़ों से इसकी पुष्टि नहीं हो सकी। क्या मैं आपका सवाल स्टाफ की समीक्षा के लिए सहेज दूँ?",
        "Available institute documents se iski pushti nahi ho saki. Kya main aapka sawaal staff review ke liye save kar doon?",
    ),
    "cancelled": ("Okay, I haven’t created a ticket or reminder. What else can I help with?", "ठीक है, कोई टिकट या रिमाइंडर नहीं बनाया गया। और क्या मदद चाहिए?", "Theek hai, koi ticket ya reminder nahi banaya. Aur kya madad chahiye?"),
    "ticket": (
        "Your question is saved as ticket #{ticket_id}, pending staff review. No email has been sent yet.",
        "आपका सवाल टिकट #{ticket_id} में सहेजा गया है और स्टाफ की समीक्षा बाकी है। अभी कोई ईमेल नहीं भेजा गया है।",
        "Aapka sawaal ticket #{ticket_id} mein save hai, staff review abhi baaki hai. Abhi koi email nahi bheja gaya hai.",
    ),
    "action_failed": ("I couldn’t save that request. Please try again.", "अनुरोध सहेजा नहीं जा सका। कृपया फिर कोशिश करें।", "Request save nahi ho paayi. Phir try karein."),
    "reminders_disabled": ("Email reminders are not enabled for this helpdesk yet. Please set a reminder on your phone.", "इस हेल्पडेस्क पर ईमेल रिमाइंडर अभी चालू नहीं हैं। कृपया अपने फोन पर रिमाइंडर लगाएँ।", "Is helpdesk par email reminders abhi enabled nahi hain. Apne phone par reminder laga lein."),
    "reminder_date": ("What date should the reminder be for? Please include the day, month, and year.", "रिमाइंडर किस तारीख के लिए चाहिए? कृपया दिन, महीना और साल बताइए।", "Reminder kis date ke liye chahiye? Din, mahina aur saal bataiye."),
    "reminder_email": ("What email address should receive the reminder?", "रिमाइंडर किस ईमेल पते पर भेजना है?", "Reminder kis email address par bhejna hai?"),
    "reminder_confirm": ("Save an email reminder for {date}: {message}, to {email}? Please say yes or no.", "{date} को {message} का ईमेल रिमाइंडर {email} के लिए सहेज दूँ? हाँ या नहीं बताइए।", "{date} ko {message} ka email reminder {email} ke liye save kar doon? Haan ya nahi bataiye."),
    "reminder_saved": ("Reminder #{reminder_id} is saved for {date}. Email delivery depends on the reminder service running.", "रिमाइंडर #{reminder_id}, {date} के लिए सहेजा गया। ईमेल भेजने के लिए रिमाइंडर सेवा का चालू होना ज़रूरी है।", "Reminder #{reminder_id}, {date} ke liye save ho gaya. Email delivery ke liye reminder service chalna zaroori hai."),
}


def say(key: str, language: str = "english", **values) -> str:
    """Use stable translations for operational claims and confirmations."""
    index = {"english": 0, "hindi": 1, "hinglish": 2}.get(language, 0)
    return COPY[key][index].format(**values)


def language_hint(text: str) -> str | None:
    """Keep Roman Hindi replies in Roman script even if the router labels them Hindi."""
    if re.search(r"[\u0900-\u097f]", text):
        return "hindi"
    words = set(re.findall(r"[a-z]+", text.casefold()))
    hindi_words = {"kya", "kaise", "mein", "hai", "hain", "ke", "ka", "ki", "aur", "batao", "chahiye", "kitna", "kab", "kahan", "mujhe", "hota", "hoti", "liye"}
    if len(words & hindi_words) >= 2:
        return "hinglish"
    return None


def valid_email(value: str) -> bool:
    """Reject malformed/header-injection input before storing reminder recipients."""
    return len(value) <= 254 and bool(re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value))


def normalize_category(value: str) -> str:
    """Normalize CLI aliases; admission category is self-reported context, not authentication."""
    value = value.strip().casefold()
    if value in {"cg", "chhattisgarh", "chattisgarh"}:
        return "CG"
    if value in {"", "general", "gen"}:
        return "general"
    raise ValueError("Choose general (gen) or CG.")
