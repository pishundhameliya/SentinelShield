"""Multi-lingual threat translation and fusion scoring."""
from __future__ import annotations

from typing import Any

LANG: dict[str, dict[str, str]] = {
    "en": {
        "watchlist": "Watchlist / stolen vehicle",
        "tamper": "Camera tamper",
        "threat": "Threat detected",
        "weapon": "Weapon / dangerous object",
        "panic": "Panic / fight / rush",
        "abandoned": "Abandoned object",
        "cyber": "Cyber attack on camera",
    },
    "hi": {
        "watchlist": "वॉचलिस्ट / चोरी का वाहन",
        "tamper": "कैमरा छेड़छाड़",
        "threat": "खतरा पाया गया",
        "weapon": "हथियार मिला है",
        "panic": "हाथापाई / भगदड़",
        "abandoned": "छोड़ा हुआ संदिग्ध सामान",
        "cyber": "कैमरा पर साइबर हमला",
    },
    "gu": {
        "watchlist": "વોચલિસ્ટ / ચોરાયેલ વાહન",
        "tamper": "કૅમેરા છેડછાડ",
        "threat": "જોખમ મળ્યું",
        "weapon": "હથિયાર મળી આવ્યું",
        "panic": "મારામારી / ભાગીદોડ",
        "abandoned": "છોડી દીધેલ શંકાસ્પદ વસ્તુ",
        "cyber": "કૅમેરા પર સાયબર હુમલો",
    },
}


def translate_alert(alert_dict: dict[str, Any], lang: str = "en") -> dict[str, Any]:
    """Decorate alert dictionary with multi-lingual Hindi and Gujarati translations."""
    pack = LANG.get(lang) or LANG["en"]
    kind = alert_dict.get("kind") or ""
    title = alert_dict.get("title") or ""
    key = kind
    if "weapon" in title.lower() or "long object" in title.lower():
        key = "weapon"

    out = dict(alert_dict)
    out["title_i18n"] = pack.get(key) or pack.get("threat") or title
    out["title_en"] = title
    out["hi"] = LANG["hi"].get(key) or title
    out["gu"] = LANG["gu"].get(key) or title
    return out
