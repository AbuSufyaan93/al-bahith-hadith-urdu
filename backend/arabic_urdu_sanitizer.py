# -*- coding: utf-8 -*-
"""
Dirty Copy-Paste Query Sanitizer, Bilingual Script Detector & Cross-Lingual Hadith Stemmer
for Arabic & Salafi Urdu Hadith Search.
Modeled on الباحث القرآني (قرآن سرچ) + Nuqayah paste cleaner + Rekhta/Hadith bilingual glossary.
"""

import re
from typing import Dict, List, Set
from pipeline.normalizer import normalize_arabic_search, normalize_urdu_search, strip_tashkeel

BRACKET_NUMS_RE = re.compile(r"[\[\(\{«﴿]\s*[\d٠-٩۰-۹/:؛،\-]+\s*[\]\)\}»﴾]")
ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]")
HONORIFIC_NOISE_RE = re.compile(
    r"(?:صلى الله عليه وسلم|صلی اللہ علیہ وسلم|رضي الله عنه(?:ما|م|ا)?|رضی اللہ عنہ(?:ما|م|ا)?|رحمه الله|رحمہ اللہ|ﷺ|ﷻ|عزوجل|تعالى|تعالیٰ)"
)

# Letters that ONLY exist in Urdu (never in Arabic keyboards/orthography)
STRICT_URDU_ONLY_RE = re.compile(r"[\u0679\u0688\u0691\u06BA\u06D2\u06D3\u06AF\u067E\u0686\u0698\u06BE]")
# Letters emitted by standard Urdu keyboards (`ی` U+06CC, `ہ` U+06C1, `ک` U+06A9, `ۃ` U+06C3, `ۂ` U+06C2 + strict Urdu)
URDU_KEYBOARD_CHARS_RE = re.compile(
    r"[\u0679\u0688\u0691\u06BA\u06D2\u06D3\u06AF\u067E\u0686\u0698\u06BE\u06C1\u06C2\u06C3\u06A9\u06CC]"
)

ISNAD_NOISE_WORDS = {
    "حدثنا", "اخبرنا", "حدثني", "سمعت", "عن", "ان", "قال", "قالت", "يقول",
    "رسول", "الله", "النبي", "روایت", "روايت", "ہے", "ہیں", "تھا", "تھی", "تھے",
    "کہ", "فرمایا", "فرمايا", "سے", "نے", "کی", "کا", "کے", "میں", "پر", "کو", "اور", "بھی", "ہو", "کر",
}

URDU_GRAMMAR_MARKERS: Set[str] = {
    "کا", "کی", "کے", "کو", "نے", "سے", "میں", "پر", "اور", "بھی", "نہیں", "والا", "والے", "والی",
    "کرنا", "ہونا", "کیا", "کیوں", "کیسے", "کون", "جب", "تب", "تک", "لیے", "لئے", "ساتھ", "اپنے", "اپنی",
}

# Comprehensive Salafi Urdu -> Vocalized/Normalized Arabic Hadith Equivalents (140+ Core Terms)
URDU_TO_ARABIC_HADITH_TERMS: Dict[str, List[str]] = {
    "نماز": ["صلاه", "يصلي", "صلوا"],
    "نمازیں": ["صلوات", "صلاه"],
    "صلوۃ": ["صلاه"],
    "وضو": ["وضوء", "توضا", "يتوضا"],
    "غسل": ["غسل", "اغتسل", "جنابه"],
    "تیمم": ["تيمم", "صعيد"],
    "مسواک": ["سواك"],
    "اذان": ["اذان", "مؤذن", "نداء"],
    "اقامت": ["اقامه"],
    "فجر": ["فجر", "صبح"],
    "ظہر": ["ظهر"],
    "عصر": ["عصر"],
    "مغرب": ["مغرب"],
    "عشاء": ["عشاء", "عتمه"],
    "وتر": ["وتر", "اوتر"],
    "تہجد": ["تهجد", "قيام الليل"],
    "تراویح": ["رمضان", "قيام"],
    "جمعہ": ["جمعه"],
    "جنازہ": ["جنازه", "جنائز", "ميت"],
    "روزہ": ["صوم", "صيام", "صائم", "يصوم"],
    "روزے": ["صوم", "صيام"],
    "رمضان": ["رمضان"],
    "سحری": ["سحور", "تسحروا"],
    "افطار": ["فطر", "افطر"],
    "اعتکاف": ["اعتكاف", "يعتكف"],
    "زکوۃ": ["زكاه", "صدقه"],
    "زکاۃ": ["زكاه", "صدقه"],
    "زکات": ["زكاه", "صدقه"],
    "صدقہ": ["صدقه", "يتصدق"],
    "خیرات": ["صدقه", "انفاق"],
    "حج": ["حج", "حاج", "مبرور"],
    "عمرہ": ["عمره", "اعتمر"],
    "طواف": ["طواف", "طاف", "بيت"],
    "قربانی": ["اضحيه", "نحر", "نسك"],
    "نیت": ["نيه", "نيات", "نوي"],
    "نیتوں": ["نيات", "نيه"],
    "اخلاص": ["اخلاص", "مخلص"],
    "ایمان": ["ايمان", "مؤمن"],
    "اسلام": ["اسلام", "مسلم"],
    "احسان": ["احسان"],
    "توحید": ["توحيد", "يعبد", "لا اله الا الله"],
    "شرک": ["شرك", "مشرك", "يشرك"],
    "کفر": ["كفر", "كافر"],
    "نفاق": ["نفاق", "منافق"],
    "منافق": ["منافق"],
    "بدعت": ["بدعه", "محدثات", "احدث"],
    "سنت": ["سنه", "سنتي"],
    "علم": ["علم", "علماء", "عالم"],
    "علماء": ["علماء", "عالم"],
    "قرآن": ["قران", "كتاب الله"],
    "تلاوت": ["قراءه", "يقرا", "قران"],
    "درود": ["صلاه علي", "صلوا علي", "اللهم صل"],
    "دعا": ["دعاء", "يدعو", "اللهم"],
    "ذکر": ["ذكر", "يذكر", "سبحان"],
    "استغفار": ["استغفار", "استغفر", "يستغفر"],
    "توبہ": ["توبه", "يتوب", "تاب"],
    "صبر": ["صبر", "صابر", "يصبر"],
    "شکر": ["شكر", "شاكر", "يشكر"],
    "توکل": ["توكل", "يتوكل"],
    "تقوی": ["تقوي", "اتق", "متقين"],
    "تقویٰ": ["تقوي", "اتق"],
    "حیا": ["حياء", "يستحي"],
    "اخلاق": ["خلق", "اخلاق"],
    "سچ": ["صدق", "صادق"],
    "سچائی": ["صدق", "صادق"],
    "جھوٹ": ["كذب", "كاذب", "يكذب"],
    "غیبت": ["غيبه", "يغتاب"],
    "چغلی": ["نميمه", "قتات"],
    "حسد": ["حسد", "تحاسدوا"],
    "غصہ": ["غضب", "تغضب", "يغضب"],
    "تکبر": ["كبر", "متكبر"],
    "ظلم": ["ظلم", "ظالم", "مظلوم"],
    "رحم": ["رحم", "رحمه", "يرحم"],
    "رحمت": ["رحمه", "ارحم"],
    "امانت": ["امانه", "امين"],
    "خیانت": ["خيانه", "خائن", "يخون"],
    "وعدہ": ["وعد", "عهد", "اخلف"],
    "والدین": ["والدين", "بر", "امك", "اباك"],
    "ماں": ["ام", "امك", "امهات", "والدين"],
    "باپ": ["اب", "ابوك", "والد"],
    "اولاد": ["ولد", "اولاد"],
    "رشتہ": ["رحم", "صله الرحم"],
    "صلہ": ["صله", "رحم"],
    "پڑوسی": ["جار", "جيران"],
    "ہمسایہ": ["جار", "جيران"],
    "مہمان": ["ضيف"],
    "یتیم": ["يتيم", "كافل"],
    "بیوہ": ["ارمله", "مسكين"],
    "مسکین": ["مسكين", "فقير"],
    "مسلمان": ["مسلم", "مسلمون", "مسلمين"],
    "بھائی": ["اخ", "اخو", "اخوان"],
    "سلام": ["سلام", "يسلم", "افشوا"],
    "بیمار": ["مريض", "عياده"],
    "نکاح": ["نكاح", "تزوج", "ينكح"],
    "شادی": ["نكاح", "زواج", "تزوج"],
    "بیوی": ["مراه", "زوجه", "نساء"],
    "شوہر": ["زوج", "بعل"],
    "عورت": ["مراه", "نساء"],
    "طلاق": ["طلاق", "طلق"],
    "خلع": ["خلع", "اختلعت"],
    "عدت": ["عده", "تعتد"],
    "وراثت": ["فرائض", "ميراث", "يرث"],
    "وصیت": ["وصيه", "يوصي"],
    "تجارت": ["بيع", "تاجر", "اشترى"],
    "خرید": ["بيع", "اشترى"],
    "قرض": ["دين", "قرض", "اقترض"],
    "سود": ["ربا", "اكل الربا"],
    "رشوت": ["راشي", "مرتشي"],
    "حلال": ["حلال", "طيب"],
    "حرام": ["حرام", "حرم"],
    "شراب": ["خمر", "مسكر"],
    "زنا": ["زنا", "يزني"],
    "چوری": ["سرق", "سارق"],
    "قتل": ["قتل", "دم", "يقتل"],
    "جہاد": ["جهاد", "سبيل الله", "مجاهد"],
    "شہید": ["شهيد", "شهاده"],
    "فتنہ": ["فتن", "فتنه"],
    "دجال": ["دجال", "مسيح"],
    "قیامت": ["قيامه", "ساعه"],
    "آخرت": ["اخره"],
    "موت": ["موت", "يموت"],
    "قبر": ["قبر", "قبور"],
    "عذاب": ["عذاب"],
    "شفاعت": ["شفاعه", "يشفع"],
    "حوض": ["حوض", "كوثر"],
    "جنت": ["جنه", "فردوس"],
    "دوزخ": ["نار", "جهنم"],
    "جہنم": ["جهنم", "نار"],
    "فرشتے": ["ملائكه", "ملك"],
    "شیطان": ["شيطان", "ابليس"],
    "پانی": ["ماء"],
    "کھانا": ["طعام", "ياكل", "سم الله"],
    "لباس": ["لباس", "ثوب", "ازار"],
    "سونا": ["نوم", "ينام", "ذهب"],
    "سفر": ["سفر", "مسافر"],
}

ARABIC_PREFIXES = ("وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ل", "ك")
ARABIC_SUFFIXES = ("كموها", "تموها", "كم", "هم", "هن", "نا", "ها", "ان", "ون", "ين", "ات", "ة", "ه", "ي", "ك")


def sanitize_search_query(raw_query: str) -> str:
    """Cleans copy-pasted Whatsapp/PDF/Web hadith snippets into a crisp search query."""
    if not raw_query:
        return ""
    s = ZERO_WIDTH_RE.sub("", raw_query)
    s = BRACKET_NUMS_RE.sub(" ", s)
    s = HONORIFIC_NOISE_RE.sub(" ", s)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[^\w\s\u0600-\u06FF\"*]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:220]


def is_primarily_urdu_query(q: str) -> bool:
    """
    Accurately determines if a search query is Urdu:
    1. Contains strict Urdu-only letters (ٹ، ڈ، ڑ، ں، ے، گ، پ، چ، ژ، ھ).
    2. Contains Urdu grammar postpositions or known Salafi Urdu Hadith search vocabulary
       (even for shared-script words like وضو، غسل، سود، نیت، نکاح، طلاق، شفاعت، جنت!).
    3. Contains Urdu keyboard letters (`ی` U+06CC, `ہ` U+06C1, `ک` U+06A9, `ۃ` U+06C3) AND is not a
       vocalized Arabic phrase or `ال...` Arabic-article phrase.
    """
    if not q:
        return False
    if STRICT_URDU_ONLY_RE.search(q):
        return True
    words = normalize_urdu_search(q).split()
    if any(w in URDU_GRAMMAR_MARKERS or w in URDU_TO_ARABIC_HADITH_TERMS for w in words):
        return True
    # Also check raw Urdu words before normalization (e.g. تقویٰ, زکوۃ)
    raw_words = [w.strip() for w in q.split() if w.strip()]
    if any(w in URDU_TO_ARABIC_HADITH_TERMS or w in URDU_GRAMMAR_MARKERS for w in raw_words):
        return True
    if URDU_KEYBOARD_CHARS_RE.search(q):
        # If user typed Arabic with tashkeel or multiple `ال...` articles on an Urdu keyboard, allow bilingual handling
        has_tashkeel = bool(re.search(r"[\u064B-\u0652\u0670]", q))
        al_words = sum(1 for w in raw_words if w.startswith(("ال", "بال", "وال", "فال", "كال", "لل")) and len(w) >= 4)
        if not has_tashkeel and al_words == 0:
            return True
    return False


def build_fts5_match_expr(raw_query: str, for_urdu: bool = False) -> str:
    """Builds a safe, ranked FTS5 MATCH expression with prefix support on meaningful content words."""
    cleaned = sanitize_search_query(raw_query)
    norm = normalize_urdu_search(cleaned) if for_urdu else normalize_arabic_search(cleaned)
    tokens = [t for t in norm.split() if len(t) >= 2]
    if not tokens:
        return ""
    meaningful = [t for t in tokens if t not in ISNAD_NOISE_WORDS]
    chosen = meaningful[:8] if meaningful else tokens[:6]
    parts = []
    for tok in chosen:
        safe = re.sub(r'["\*\(\)\-\+\^:]', "", tok)
        if not safe:
            continue
        if len(safe) >= 3:
            parts.append(f'"{safe}"*')
        else:
            parts.append(f'"{safe}"')
    return " AND ".join(parts)


def build_crosslingual_arabic_fts_expr(raw_query: str) -> str:
    """
    Converts an Urdu Hadith query (single or multi-word, e.g. 'نماز کے اوقات' or 'سود کا گناہ' or 'نیت')
    into an Arabic FTS5 MATCH expression so Dorar's full 243,154 Arabic Hadith corpus & filters (m, s, rawy, d, t)
    can also be searched seamlessly in Urdu!
    """
    cleaned = sanitize_search_query(raw_query)
    if not cleaned:
        return ""
    raw_tokens = [t for t in cleaned.split() if len(t) >= 2]
    norm_tokens = [normalize_urdu_search(t) for t in raw_tokens]
    clause_groups: List[str] = []

    for rtok, ntok in zip(raw_tokens, norm_tokens):
        if ntok in ISNAD_NOISE_WORDS or ntok in URDU_GRAMMAR_MARKERS or rtok in URDU_GRAMMAR_MARKERS:
            continue
        ar_cands = URDU_TO_ARABIC_HADITH_TERMS.get(rtok) or URDU_TO_ARABIC_HADITH_TERMS.get(ntok)
        if ar_cands:
            or_terms = []
            for ac in ar_cands[:3]:
                ac_norm = normalize_arabic_search(ac)
                safe = re.sub(r'["\*\(\)\-\+\^:]', "", ac_norm)
                if not safe:
                    continue
                if " " in safe:
                    or_terms.append(f'"{safe}"')
                elif len(safe) >= 3:
                    or_terms.append(f'"{safe}"*')
                else:
                    or_terms.append(f'"{safe}"')
            if or_terms:
                clause_groups.append("(" + " OR ".join(or_terms) + ")" if len(or_terms) > 1 else or_terms[0])
        else:
            # Transliterated shared Islamic loanword (e.g. مسواک -> مسواك, شفاعت -> شفاعه, صدقہ -> صدقه)
            ar_guess = normalize_arabic_search(rtok)
            ar_guess2 = re.sub(r"ت$", "ه", ar_guess) if len(ar_guess) >= 4 and ar_guess.endswith("ت") else ""
            cands = []
            for g in (ar_guess, ar_guess2):
                safe = re.sub(r'["\*\(\)\-\+\^:]', "", g)
                if safe and len(safe) >= 3:
                    cands.append(f'"{safe}"*')
            if cands:
                clause_groups.append("(" + " OR ".join(dict.fromkeys(cands)) + ")" if len(cands) > 1 else cands[0])

    return " AND ".join(clause_groups[:5])


def generate_lexicon_candidates(word: str) -> List[str]:
    """
    Generates ordered morphological stem candidates for an Arabic or Urdu word
    so clicking any inflected word in a Hadith finds its exact Rekhta/Qari dictionary entry.
    """
    w = strip_tashkeel(word or "").strip()
    w = re.sub(r"[^\u0621-\u06D3]", "", w)
    if not w:
        return []

    seen: List[str] = []

    def _add(cand: str) -> None:
        if cand and len(cand) >= 2 and cand not in seen:
            seen.append(cand)
            ur_v = cand.replace("ك", "ک").replace("ي", "ی").replace("ى", "ی").replace("ة", "ہ").replace("ه", "ہ")
            ar_v = normalize_arabic_search(cand)
            if ur_v not in seen:
                seen.append(ur_v)
            if ar_v not in seen:
                seen.append(ar_v)

    _add(w)
    for pref in ARABIC_PREFIXES:
        if w.startswith(pref) and len(w) - len(pref) >= 3:
            stem = w[len(pref):]
            _add(stem)
            for suf in ARABIC_SUFFIXES:
                if stem.endswith(suf) and len(stem) - len(suf) >= 3:
                    _add(stem[:-len(suf)])

    for suf in ARABIC_SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            _add(w[:-len(suf)])

    return seen[:18]
