"""Deterministic pronunciation transforms preserve text order, values and negation."""
import re
import unicodedata
from datetime import date

VERSION = "domain-pronunciation-2"
_SMALL = ("शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
"बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस "
"चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ "
"साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्नासी "
"अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सतासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे").split()
_MONTHS = "जनवरी फरवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर".split()
LEXICON = {
    "IIIT Naya Raipur": "आईआईआईटी नया रायपुर", "IIIT-NR": "आईआईआईटी नया रायपुर",
    "IIIT": "आईआईआईटी", "Naya Raipur": "नया रायपुर", "B.Tech": "बीटेक", "BTech": "बीटेक",
    "JEE": "जेईई", "Main": "मेन", "JoSAA": "जोसा", "CSAB": "सीसैब", "CRL": "सीआरएल",
    "OBC-NCL": "ओबीसी एनसीएल", "GEN-EWS": "जनरल ईडब्ल्यूएस", "SC": "एससी", "ST": "एसटी",
    "OBC": "ओबीसी", "EWS": "ईडब्ल्यूएस", "PwD": "पीडब्ल्यूडी", "NTPC": "एनटीपीसी", "CG": "सीजी",
    "CSE": "सीएसई", "ECE": "ईसीई", "DSAI": "डीएसएआई", "PCM": "पीसीएम", "PM": "पीएम",
    "Vidyalaxmi": "विद्यालक्ष्मी", "Fee": "शुल्क", "Fees": "शुल्क", "GST": "जीएसटी",
    "OTR": "ओटीआर", "January": "जनवरी", "February": "फरवरी", "March": "मार्च", "April": "अप्रैल",
    "May": "मई", "June": "जून", "July": "जुलाई", "August": "अगस्त", "September": "सितंबर",
    "October": "अक्टूबर", "November": "नवंबर", "December": "दिसंबर",
    "non-refundable": "गैर-वापसी योग्य", "refundable": "वापसी योग्य", "excluding": "को छोड़कर",
    "including": "सहित", "not applicable": "लागू नहीं", "applicable": "लागू", "M.Tech": "एमटेक",
    "MTech": "एमटेक", "Ph.D": "पीएचडी", "PhD": "पीएचडी", "MBA": "एमबीए", "MSc": "एमएससी",
    "NIRF": "एनआईआरएफ", "NIT": "एनआईटी", "IIT": "आईआईटी", "AI": "एआई", "Hostel": "छात्रावास",
    "Mess": "मेस", "Semester": "सेमेस्टर", "Tuition": "ट्यूशन", "Scholarship": "छात्रवृत्ति",
    "Campus": "कैंपस", "Placement": "प्लेसमेंट", "Placements": "प्लेसमेंट", "Admission": "प्रवेश",
    "Admissions": "प्रवेश", "Eligibility": "पात्रता", "Gender-Neutral": "जेंडर-न्यूट्रल",
    "Gender Neutral": "जेंडर न्यूट्रल", "Female-only": "केवल महिला", "Supernumerary": "अतिरिक्त",
    "Moratorium": "मोरेटोरियम", "Interest": "ब्याज", "Subsidy": "सब्सिडी", "Waiver": "छूट",
    "Reimbursement": "प्रतिपूर्ति", "Domicile": "अधिवास"
}
HINGLISH = {"nahi":"नहीं", "nahin":"नहीं", "mat":"मत", "bina":"बिना", "sirf":"सिर्फ",
    "keval":"केवल", "agar":"अगर", "lekin":"लेकिन", "aur":"और", "ya":"या", "hai":"है",
    "hain":"हैं", "tha":"था", "thi":"थी", "hoga":"होगा", "hogi":"होगी", "liye":"लिए",
    "ke":"के", "ki":"की", "ka":"का", "mein":"में", "se":"से", "tak":"तक", "par":"पर",
    "aap":"आप", "aapko":"आपको", "yeh":"यह", "woh":"वह", "chahiye":"चाहिए",
    "jama":"जमा", "rupaye":"रुपये", "saal":"साल", "mahine":"महीने", "baad":"बाद",
    "pehle":"पहले", "alag":"अलग", "sath":"साथ", "saath":"साथ", "milta":"मिलता",
    "milti":"मिलती", "sakta":"सकता", "sakti":"सकती", "hote":"होते", "hoti":"होती"}
NEGATION = {
    "not": "नहीं", "cannot": "नहीं कर सकते", "don't": "नहीं", "doesn't": "नहीं",
    "won't": "नहीं", "isn't": "नहीं है", "aren't": "नहीं हैं", "no": "नहीं",
    "without": "बिना", "neither": "न", "nor": "न"
}


def cardinal(number):
    """Read cardinal amounts using Indian units; never turn money into isolated digits."""
    number = int(number)
    if number < 0:
        return "ऋण " + cardinal(-number)
    if number < 100:
        return _SMALL[number]
    for unit, label in ((10000000,"करोड़"),(100000,"लाख"),(1000,"हजार"),(100,"सौ")):
        if number >= unit:
            whole, remainder = divmod(number,unit)
            return cardinal(whole)+" "+label+(" "+cardinal(remainder) if remainder else "")


def _words(text, lexicon):
    for original in sorted(lexicon,key=len,reverse=True):
        text = re.sub(r"(?<![A-Za-z])"+re.escape(original)+r"(?![A-Za-z])",lexicon[original],text,flags=re.I)
    return text


def normalize(text, language):
    """Transform only known tokens; leave all other words and semantic operators intact."""
    text = unicodedata.normalize("NFC",text)
    text = "".join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in text)
    text = re.sub(r"[*_`#]", "", text)
    if language == "english":
        text = re.sub(r"₹\s*(-?\d+(?:,\d+)*(?:\.\d+)?)",r"\1 rupees",text)
        return text.replace("₹"," rupees ").replace("%"," percent ")
    text = re.sub(r"₹\s*(-?\d+(?:,\d+)*(?:\.\d+)?)",r"\1 रुपये",text)
    text = _words(text, LEXICON)
    if language == "hindi":
        text = _words(text, NEGATION)
    if language == "hinglish":
        text = _words(text,HINGLISH)
    def calendar_date(year,month,day):
        year,month,day = map(int,(year,month,day))
        date(year,month,day)
        return f"{cardinal(day)} {_MONTHS[month-1]} {cardinal(year)}"
    text = re.sub(r"\b(20\d{2})-(\d{2})-(\d{2})\b",lambda m:calendar_date(*m.groups()),text)
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b",
        lambda m:calendar_date(m[3],m[2],m[1]),text)
    text = re.sub(r"(?<![\w\d])-(?=\d)","ऋण ",text)
    text = re.sub(r"(?<=\d)\s*[-–]\s*(?=\d)"," से ",text)
    def number(match):
        value = match.group().replace(",", "")
        parts = value.split(".")
        result = cardinal(parts[0])
        return result + (" दशमलव " + " ".join(_SMALL[int(c)] for c in parts[1]) if len(parts)>1 else "")
    # Restrict grouping to common Indian/Western forms; punctuation stays outside the number.
    text = re.sub(r"\d+(?:,\d+)*(?:\.\d+)?",number,text)
    text = text.replace("₹"," रुपये ").replace("%"," प्रतिशत ").replace("/"," स्लैश ")
    text = text.translate(str.maketrans({"“":'"',"”":'"',"’":"'","–":"-","—":"-"}))
    return re.sub(r"\s+"," ",text).strip()
