# -*- coding: utf-8 -*-
"""
Unified Arabic & Urdu Orthography Normalizer, Diacritic Stripper, and Numeral Converter
for Al-Bahith Al-Hadithi (الباحث الحديثي — اردو، عربی).
"""

import html
import re
from typing import List

TASHKEEL_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
NON_WORD_RE = re.compile(r"[^\w\s\u0600-\u06FF]")
MULTI_SPACE_RE = re.compile(r"\s+")

TO_EASTERN_ARABIC = str.maketrans("0123456789۰۱۲۳۴۵۶۷۸۹", "٠١٢٣٤٥٦٧٨٩٠١٢٣٤٥٦٧٨٩")
TO_EASTERN_URDU = str.maketrans("0123456789٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹")
TO_ASCII_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def strip_html_tags(text: str) -> str:
    if not text:
        return ""
    cleaned = HTML_TAG_RE.sub(" ", text)
    cleaned = html.unescape(cleaned)
    return MULTI_SPACE_RE.sub(" ", cleaned).strip()


def strip_tashkeel(text: str) -> str:
    if not text:
        return ""
    return TASHKEEL_RE.sub("", text)


import unicodedata

PRESENTATION_FORMS_RE = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")


def decompose_presentation_forms(text: str) -> str:
    """
    Decomposes legacy Arabic/Urdu Presentation Forms-A/B (e.g. ligature `ﻻ` U+FEFB -> `ل+ا`,
    `ﷲ` -> `الله`, isolated/final glyphs `ﻲ`, `ﻛ`) ONLY for search indexing & querying,
    never mutating canonical vocalized display text (`matn_vocalized`).
    """
    if not text or not PRESENTATION_FORMS_RE.search(text):
        return text or ""
    return PRESENTATION_FORMS_RE.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), text)


def normalize_arabic_search(text: str) -> str:
    """Normalizes Arabic text for diacritic-insensitive, presentation-form-safe, hamza-insensitive search."""
    if not text:
        return ""
    s = strip_html_tags(text)
    s = decompose_presentation_forms(s)
    s = TASHKEEL_RE.sub("", s)
    s = re.sub(r"[أإآٱٲٳ]", "ا", s)
    s = s.replace("ؤ", "و").replace("ئ", "ي")
    s = s.replace("ک", "ك").replace("گ", "ك")
    s = re.sub(r"[یےى]", "ي", s)
    s = re.sub(r"[ہھۀۂۃة]", "ه", s)
    s = s.replace("ں", "ن")
    s = s.translate(TO_ASCII_DIGITS)
    s = NON_WORD_RE.sub(" ", s)
    return MULTI_SPACE_RE.sub(" ", s).strip()


def normalize_urdu_search(text: str) -> str:
    """Normalizes Urdu & Arabic text into unified Urdu search orthography (preserving canonical display fields)."""
    if not text:
        return ""
    s = strip_html_tags(text)
    s = decompose_presentation_forms(s)
    s = TASHKEEL_RE.sub("", s)
    s = re.sub(r"[أإآٱٲٳ]", "ا", s)
    s = s.replace("ك", "ک")
    s = re.sub(r"[يیى]", "ی", s)
    s = re.sub(r"[هہھۀۂةۃ]", "ہ", s)
    s = s.replace("ؤ", "و").replace("ئ", "ی")
    s = s.translate(TO_ASCII_DIGITS)
    s = NON_WORD_RE.sub(" ", s)
    return MULTI_SPACE_RE.sub(" ", s).strip()


def normalize_bilingual(text: str) -> str:
    """Produces a universal consonant-normalized search form matching both Arabic and Urdu queries."""
    return normalize_arabic_search(text)


def to_ar_digits(val: object) -> str:
    return str(val if val is not None else "").translate(TO_EASTERN_ARABIC)


def to_ur_digits(val: object) -> str:
    return str(val if val is not None else "").translate(TO_EASTERN_URDU)


def to_ascii_digits(val: object) -> str:
    return str(val if val is not None else "").translate(TO_ASCII_DIGITS)


def build_arabic_highlight_regex(query: str) -> List[re.Pattern]:
    """Builds diacritic-tolerant regexes to highlight query words inside vocalized Arabic or Urdu text."""
    q_clean = strip_tashkeel(query or "").strip()
    if not q_clean:
        return []
    tash = r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]*"
    char_map = {
        "ا": "[اأإآٱ]",
        "أ": "[اأإآٱ]",
        "إ": "[اأإآٱ]",
        "آ": "[اأإآٱ]",
        "ه": "[هةہھۃ]",
        "ة": "[هةہھۃ]",
        "ہ": "[هةہھۃ]",
        "ي": "[يىیئے]",
        "ى": "[يىیئے]",
        "ی": "[يىیئے]",
        "ك": "[كک]",
        "ک": "[كک]",
    }
    patterns: List[re.Pattern] = []
    for token in q_clean.split():
        token = re.sub(r"[^\u0621-\u06D3a-zA-Z0-9]", "", token)
        if len(token) < 2:
            continue
        pieces = [char_map.get(ch, re.escape(ch)) + tash for ch in token]
        try:
            patterns.append(re.compile("".join(pieces), re.IGNORECASE))
        except re.error:
            continue
    return patterns


def highlight_text_html(text: str, query: str, css_class: str = "search-keys") -> str:
    """Highlights matching query tokens inside vocalized Arabic or Urdu text without breaking diacritics."""
    if not text or not query:
        return text or ""
    if "<span" in text or "<mark" in text:
        return text
    out = text
    for pat in build_arabic_highlight_regex(query)[:6]:
        out = pat.sub(lambda m: f'<span class="{css_class}">{m.group(0)}</span>', out)
    return out
