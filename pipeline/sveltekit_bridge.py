# -*- coding: utf-8 -*-
"""
SvelteKit `__data.json` Devalue Decoder, Live Upstream Cache Bridge, and Automatic
Salafi Urdu Enrichment Engine for ALL 45+ Encyclopedia Routes of https://hadeeth.com/.
"""

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional
import httpx

from pipeline.books_catalog import HADEETH_33_COLLECTIONS
from pipeline.normalizer import normalize_arabic_search, to_ascii_digits, to_ur_digits
from pipeline.salafi_urdu_engine import (
    CHAIN_TYPE_URDU_MAP,
    ENC_UI_TERM_URDU,
    GENERATION_URDU_MAP,
    IBN_HAJAR_RANK_URDU_MAP,
    classify_and_translate_grade,
    format_book_urdu,
    format_mohdith_urdu,
    format_rawi_urdu,
    translate_ar_to_salafi_urdu,
)


def decode_sveltekit_devalue(raw_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decodes SvelteKit's `devalue` serialized `__data.json` (`{"type":"data","nodes":[...]}`)
    into a clean, standard Python dictionary corresponding to the leaf `+page.server.ts` return object.
    """
    nodes = raw_json.get("nodes") or []
    decoded_nodes: List[Any] = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "data":
            decoded_nodes.append(node)
            continue
        arr = node.get("data") or []
        if not arr:
            decoded_nodes.append({})
            continue
        memo: Dict[int, Any] = {}

        def _resolve(idx: int) -> Any:
            if idx < 0 or idx >= len(arr):
                return None
            if idx in memo:
                return memo[idx]
            val = arr[idx]
            if isinstance(val, (str, int, float, bool)) or val is None:
                return val
            if isinstance(val, list):
                if (
                    len(val) >= 2
                    and isinstance(val[0], str)
                    and val[0] in ("Date", "Set", "Map", "RegExp", "BigInt", "URL")
                ):
                    return str(val[1])
                res_list: List[Any] = []
                memo[idx] = res_list
                for item in val:
                    res_list.append(_resolve(item) if isinstance(item, int) else item)
                return res_list
            if isinstance(val, dict):
                res_dict: Dict[str, Any] = {}
                memo[idx] = res_dict
                for k, v in val.items():
                    res_dict[k] = _resolve(v) if isinstance(v, int) else v
                return res_dict
            return val

        decoded_nodes.append(_resolve(0))

    for n in reversed(decoded_nodes):
        if isinstance(n, dict) and n:
            return n
    return decoded_nodes[-1] if decoded_nodes and isinstance(decoded_nodes[-1], dict) else {}


def encode_sveltekit_devalue(root: Any) -> List[Any]:
    """
    Serializes a Python dictionary/list into SvelteKit 2's exact `devalue` flat array
    compatible with `$e` (`devalue.unflatten`) in `/_app/immutable/chunks/DK9E1CDf.js`.
    """
    out: List[Any] = []
    prim_memo: Dict[Any, int] = {}

    def _add(val: Any) -> int:
        if val is None or isinstance(val, (bool, int, float, str)):
            key = (type(val), val)
            if key in prim_memo:
                return prim_memo[key]
            idx = len(out)
            out.append(val)
            prim_memo[key] = idx
            return idx
        if isinstance(val, (list, tuple)):
            idx = len(out)
            arr_slot: List[int] = []
            out.append(arr_slot)
            for item in val:
                arr_slot.append(_add(item))
            return idx
        if isinstance(val, dict):
            idx = len(out)
            dict_slot: Dict[str, int] = {}
            out.append(dict_slot)
            for k, v in val.items():
                if k == "__proto__":
                    continue
                dict_slot[str(k)] = _add(v)
            return idx
        return _add(str(val))

    _add(root)
    return out


def wrap_sveltekit_nodes_payload(data_obj: Dict[str, Any], invalidated: str = "") -> Dict[str, Any]:
    """
    Wraps a leaf page load dictionary into SvelteKit's `{"type":"data","nodes":[...]}` envelope
    for `/(site)/*` routes (layout 0, layout 2, leaf page node).
    """
    n0 = {"type": "skip"} if (len(invalidated) >= 1 and invalidated[0] == "0") else None
    n1 = {"type": "skip"} if (len(invalidated) >= 2 and invalidated[1] == "0") else None
    return {
        "type": "data",
        "nodes": [
            n0,
            n1,
            {
                "type": "data",
                "data": encode_sveltekit_devalue(data_obj),
            },
        ],
    }



def _lookup_local_urdu_hadith(
    conn: sqlite3.Connection,
    book_id: Optional[int],
    book_title: str,
    numbering_print1: Optional[str],
    numbering_harf: Optional[str],
    content_ar: str,
) -> Dict[str, str]:
    """
    Attempts to match an encyclopedia hadith against our 33,500+ human-translated `canonical_hadiths`,
    2,220 `hadeethenc_entries`, or 243,154 `dorar_hadiths` to provide verified Urdu matn & sharh!
    """
    out = {"matn_urdu": "", "sharh_urdu": "", "grade_ur": "", "urdu_source": ""}
    if not content_ar:
        return out

    # 1. Try exact (hadeeth_book_id, hadith_number) in canonical_hadiths for Kutub al-Sittah + Muwatta (1..7)
    if book_id in (1, 2, 3, 4, 5, 6, 7):
        for raw_num in (numbering_print1, numbering_harf):
            if not raw_num:
                continue
            num_clean = re.sub(r"[^\d]", "", to_ascii_digits(raw_num))
            if num_clean:
                row = conn.execute(
                    """
                    SELECT matn_urdu, primary_grade_ur, sharh_urdu
                    FROM canonical_hadiths
                    WHERE hadeeth_book_id = ? AND hadith_number = ? AND matn_urdu != ''
                    LIMIT 1
                    """,
                    (book_id, num_clean),
                ).fetchone()
                if row and row[0]:
                    # Verify reasonable consonant overlap or length so numbering differences don't mismatch
                    norm_ar = normalize_arabic_search(content_ar)
                    row_ar = conn.execute(
                        "SELECT matn_normalized FROM canonical_hadiths WHERE hadeeth_book_id = ? AND hadith_number = ? LIMIT 1",
                        (book_id, num_clean),
                    ).fetchone()
                    if row_ar and row_ar[0]:
                        words_a = set(norm_ar.split())
                        words_b = set(row_ar[0].split())
                        overlap = len(words_a & words_b) / max(1, min(len(words_a), len(words_b)))
                        if overlap >= 0.32:
                            return {
                                "matn_urdu": row[0],
                                "sharh_urdu": row[2] or "",
                                "grade_ur": row[1] or "",
                                "urdu_source": "صحاح ستہ مستند اردو ترجمہ",
                            }

    # 2. Try FTS5 match on the distinctive matn tail (stripping isnad prefix up to قال رسول الله / أن النبي)
    matn_core = content_ar
    m_split = re.search(r"(?:قَالَ\s+رَسُولُ|أَنَّ\s+رَسُولَ|عَنِ\s+النَّبِيِّ|يَقُولُ\s*:)(.+)", content_ar)
    if m_split and len(m_split.group(1)) > 25:
        matn_core = m_split.group(1)
    norm_tokens = [w for w in normalize_arabic_search(matn_core).split() if len(w) >= 3]
    if len(norm_tokens) >= 4:
        fts_q = " AND ".join(f'"{w}"' for w in norm_tokens[:6])
        try:
            row_he = conn.execute(
                """
                SELECT h.matn_urdu, h.explanation_ur, h.grade_ur
                FROM hadeethenc_entries h
                WHERE h.matn_normalized LIKE ?
                LIMIT 1
                """,
                (f"%{' '.join(norm_tokens[:5])}%",),
            ).fetchone()
            if row_he and row_he[0]:
                return {
                    "matn_urdu": row_he[0],
                    "sharh_urdu": row_he[1] or "",
                    "grade_ur": row_he[2] or "",
                    "urdu_source": "موسوعۃ الاحادیث النبویہ (اردو)",
                }
        except Exception:
            pass

        try:
            row_c = conn.execute(
                """
                SELECT c.matn_urdu, c.primary_grade_ur, c.sharh_urdu
                FROM canonical_hadiths_fts f
                JOIN canonical_hadiths c ON c.collection_slug = f.collection_slug AND c.hadith_number = f.hadith_number
                WHERE canonical_hadiths_fts MATCH ? AND c.matn_urdu != ''
                LIMIT 1
                """,
                (fts_q,),
            ).fetchone()
            if row_c and row_c[0]:
                return {
                    "matn_urdu": row_c[0],
                    "sharh_urdu": row_c[2] or "",
                    "grade_ur": row_c[1] or "",
                    "urdu_source": "مستند اردو ذخیرۂ حدیث",
                }
        except Exception:
            pass

    return out


def enrich_encyclopedia_payload_urdu(
    route_path: str,
    data: Dict[str, Any],
    conn: sqlite3.Connection,
    translate_live: bool = True,
) -> Dict[str, Any]:
    """
    Enriches any decoded `hadeeth.com` Encyclopedia payload with authentic Salafi Urdu
    titles, book names, narrator ranks, generations, rulings, and matn translations!
    """
    if not isinstance(data, dict):
        return data

    # 1. Collections (/collections)
    if "collections" in data and isinstance(data["collections"], list):
        for col in data["collections"]:
            cid = col.get("id")
            meta = HADEETH_33_COLLECTIONS.get(cid, {})
            col["title_ur"] = meta.get("title_ur") or format_book_urdu(col.get("title", ""))
            col["author_ur"] = meta.get("author_ur") or (
                format_mohdith_urdu(
                    (col.get("author") or {}).get("short_name") or (col.get("author") or {}).get("name", ""),
                    (col.get("author") or {}).get("death_date"),
                )
            )
            col["group_ur"] = meta.get("group_ur", "دیگر کتبِ سنت")

    # 2. Book Metadata (`book` object on /collections/[id], /hadith/[id], etc.)
    if "book" in data and isinstance(data["book"], dict):
        bid = data["book"].get("id")
        meta = HADEETH_33_COLLECTIONS.get(bid, {})
        data["book"]["title_ur"] = meta.get("title_ur") or format_book_urdu(data["book"].get("title", ""))
        if data["book"].get("author"):
            data["book"]["author"]["name_ur"] = meta.get("author_ur") or format_mohdith_urdu(
                data["book"]["author"].get("short_name") or data["book"]["author"].get("name", ""),
                data["book"]["author"].get("death_date"),
            )

    if "books" in data and isinstance(data["books"], list):
        for b in data["books"]:
            if isinstance(b, dict):
                bid = b.get("id")
                meta = HADEETH_33_COLLECTIONS.get(bid, {})
                b["title_ur"] = meta.get("title_ur") or format_book_urdu(b.get("title") or b.get("name") or "")

    # 3. Single Hadith Detail (/hadith/[id])
    if "hadith" in data and isinstance(data["hadith"], dict) and data["hadith"].get("content"):
        h = data["hadith"]
        bid = (data.get("book") or {}).get("id")
        btitle = (data.get("book") or {}).get("title", "")
        matched = _lookup_local_urdu_hadith(
            conn,
            bid,
            btitle,
            h.get("numbering_print1"),
            h.get("numbering_harf"),
            h.get("content", ""),
        )
        if matched["matn_urdu"]:
            h["content_urdu"] = matched["matn_urdu"]
            h["sharh_urdu"] = matched["sharh_urdu"]
            h["urdu_source"] = matched["urdu_source"]
        elif translate_live:
            h["content_urdu"] = translate_ar_to_salafi_urdu(h["content"], conn=conn, kind="matn")
            h["urdu_source"] = "سلفی اردو ترجمہ و مراجعہ"

        # Enrich chains narrators & rulings
        for ch in data.get("chains") or []:
            ch["types_ur"] = [CHAIN_TYPE_URDU_MAP.get(t, str(t)) for t in (ch.get("types") or [])]
            for nr in ch.get("narrators") or []:
                if nr.get("ibn_hajar_grade"):
                    g_ur, _, g_cls = classify_and_translate_grade(nr["ibn_hajar_grade"])
                    nr["ibn_hajar_grade_ur"] = g_ur
                    nr["grade_class"] = g_cls
        rel = data.get("related") or {}
        for gr in rel.get("gradings") or []:
            g_ur, _, g_cls = classify_and_translate_grade(gr.get("text", ""))
            gr["text_ur"] = g_ur
            gr["grade_class"] = g_cls

    # 4. Dorar Single Hadith (/dorar/hadith/[hash])
    if "hadith" in data and isinstance(data["hadith"], dict) and data["hadith"].get("hash"):
        dh = data["hadith"]
        row_d = conn.execute(
            "SELECT matn_urdu, sharh_urdu, rawi_ur, mohdith_ur, book_ur, grade_ur, grade_bucket FROM dorar_hadiths WHERE hadith_id = ? LIMIT 1",
            (dh["hash"],),
        ).fetchone()
        if row_d:
            if row_d[0]:
                dh["text_urdu"] = row_d[0]
            if row_d[1]:
                dh["sharh_urdu"] = row_d[1]
            dh["rawi_ur"] = row_d[2]
            dh["mohdith_ur"] = row_d[3]
            dh["book_ur"] = row_d[4]
            dh["hukm_ur"] = row_d[5]
        if not dh.get("text_urdu") and translate_live and dh.get("text"):
            rawi_name = (dh.get("rawi") or {}).get("name", "") if isinstance(dh.get("rawi"), dict) else ""
            dh["text_urdu"] = translate_ar_to_salafi_urdu(dh["text"], conn=conn, rawi_ar=rawi_name, kind="matn")
        if dh.get("hukm") and not dh.get("hukm_ur"):
            dh["hukm_ur"], _, dh["grade_class"] = classify_and_translate_grade(dh["hukm"])

    # 5. Paginated Hadiths List (on chapter, subject, narrator hadiths, controversial, proverb, quran ayah, search)
    if "hadiths" in data and isinstance(data["hadiths"], list):
        default_bid = (data.get("book") or {}).get("id")
        default_btitle = (data.get("book") or {}).get("title", "")
        for idx, h in enumerate(data["hadiths"]):
            if not isinstance(h, dict):
                continue
            c_ar = h.get("content") or h.get("text") or ""
            if not c_ar and isinstance(h.get("parts"), list):
                c_ar = "".join(h["parts"])
            if not c_ar:
                continue
            bid = h.get("book_id") or ((h.get("book") or {}).get("id") if isinstance(h.get("book"), dict) else default_bid)
            btitle = h.get("book_title") or ((h.get("book") or {}).get("title") if isinstance(h.get("book"), dict) else default_btitle) or ""
            if btitle:
                h["book_title_ur"] = format_book_urdu(btitle)
            matched = _lookup_local_urdu_hadith(
                conn,
                bid,
                btitle,
                h.get("numbering_print1"),
                h.get("numbering_harf"),
                c_ar,
            )
            if matched["matn_urdu"]:
                h["content_urdu"] = matched["matn_urdu"]
                h["urdu_source"] = matched["urdu_source"]
            elif translate_live and idx < 8:
                # Translate visible top items live & cache them in SQLite for zero latency!
                h["content_urdu"] = translate_ar_to_salafi_urdu(c_ar, conn=conn, kind="matn")
                h["urdu_source"] = "سلفی اردو ترجمہ"

    # 6. Narrators List & Narrator Profile (/narrators, /narrators/[id])
    if "narrators" in data and isinstance(data["narrators"], list):
        for nr in data["narrators"]:
            if isinstance(nr, dict):
                gen = nr.get("generation") or nr.get("generation_num")
                if gen in GENERATION_URDU_MAP:
                    nr["generation_ur"] = GENERATION_URDU_MAP[gen]
                if nr.get("ibn_hajar_grade"):
                    nr["ibn_hajar_grade_ur"], _, nr["grade_class"] = classify_and_translate_grade(nr["ibn_hajar_grade"])

    if "narrator" in data and isinstance(data["narrator"], dict):
        nr = data["narrator"]
        gen = nr.get("generation_num") or (data.get("facets") or {}).get("generation")
        if gen in GENERATION_URDU_MAP:
            nr["generation_ur"] = GENERATION_URDU_MAP[gen]
        gg = (data.get("facets") or {}).get("grade_group")
        if gg in IBN_HAJAR_RANK_URDU_MAP:
            nr["grade_group_ur"] = IBN_HAJAR_RANK_URDU_MAP[gg]
        if nr.get("ibn_hajar_grade"):
            nr["ibn_hajar_grade_ur"], _, nr["grade_class"] = classify_and_translate_grade(nr["ibn_hajar_grade"])

    # 7. Statistics (/statistics)
    if "generations" in data and isinstance(data["generations"], list):
        for g in data["generations"]:
            g["label_ur"] = GENERATION_URDU_MAP.get(g.get("value"), f"طبقہ {to_ur_digits(g.get('value'))}")
    if "grade_groups" in data and isinstance(data["grade_groups"], list):
        for gg in data["grade_groups"]:
            gg["label_ur"] = IBN_HAJAR_RANK_URDU_MAP.get(gg.get("value"), f"مرتبہ {to_ur_digits(gg.get('value'))}")
    if "chain_types" in data and isinstance(data["chain_types"], list):
        for ct in data["chain_types"]:
            val = ct.get("value")
            if val in CHAIN_TYPE_URDU_MAP:
                ct["label_ur"] = CHAIN_TYPE_URDU_MAP[val]

    # 8. Chain Defects (/chain-defects)
    if "types" in data and "relations" in data:
        for t in data.get("types") or []:
            t["name_ur"] = ENC_UI_TERM_URDU.get(t.get("name", ""), t.get("name", ""))
        for r in data.get("relations") or []:
            r["name_ur"] = ENC_UI_TERM_URDU.get(r.get("name", ""), r.get("name", ""))

    # 9. Lexicons (/lexicon)
    if "lexicons" in data and isinstance(data["lexicons"], list):
        for lx in data["lexicons"]:
            lx["name_ur"] = ENC_UI_TERM_URDU.get(lx.get("name", ""), lx.get("name", ""))

    return data


_URDU_SEARCH_GLOSSARY = {
    "نیت": "النيات",
    "نماز": "الصلاة",
    "روزہ": "الصيام",
    "زکوۃ": "الزكاة",
    "زکاۃ": "الزكاة",
    "حج": "الحج",
    "صدقہ": "الصدقة",
    "والدین": "الوالدين",
    "ماں باپ": "الوالدين",
    "توحید": "التوحيد",
    "ایمان": "الإيمان",
    "علم": "العلم",
    "اخلاق": "الخلق",
    "جنت": "الجنة",
    "جہنم": "النار",
    "دعا": "الدعاء",
    "ذکر": "الذكر",
    "توبہ": "التوبة",
    "صبر": "الصبر",
    "تقوی": "التقوى",
    "تقویٰ": "التقوى",
    "جہاد": "الجهاد",
    "نکاح": "النكاح",
    "طلاق": "الطلاق",
    "تجارت": "البيع",
    "سود": "الربا",
    "یتیم": "اليتيم",
    "پڑوسی": "الجار",
    "رحمت": "الرحمة",
    "قیامت": "القيامة",
    "قرآن": "القرآن",
    "سنت": "السنة",
    "بدعت": "البدعة",
    "شرک": "الشرك",
}


def _clean_sveltekit_query_string(query_string: str, clean_path: str, conn: sqlite3.Connection) -> str:
    from urllib.parse import parse_qsl, urlencode
    from backend.arabic_urdu_sanitizer import URDU_GRAMMAR_MARKERS, URDU_TO_ARABIC_HADITH_TERMS, is_primarily_urdu_query
    from pipeline.normalizer import normalize_urdu_search

    pairs = []
    for k, v in parse_qsl(query_string.lstrip("?"), keep_blank_values=False):
        if k.startswith("x-sveltekit-") or k in ("_lang", "lang"):
            continue
        if clean_path in ("/search", "/narrators", "/subjects", "/lexicon") and k == "q" and v:
            v_strip = v.strip()
            if v_strip in _URDU_SEARCH_GLOSSARY:
                v = _URDU_SEARCH_GLOSSARY[v_strip]
            elif is_primarily_urdu_query(v_strip):
                mapped_words = []
                for tok in v_strip.split():
                    ntok = normalize_urdu_search(tok)
                    if tok in URDU_GRAMMAR_MARKERS or ntok in URDU_GRAMMAR_MARKERS:
                        continue
                    if tok in _URDU_SEARCH_GLOSSARY:
                        mapped_words.append(_URDU_SEARCH_GLOSSARY[tok])
                    elif tok in URDU_TO_ARABIC_HADITH_TERMS:
                        mapped_words.append(URDU_TO_ARABIC_HADITH_TERMS[tok][0])
                    elif ntok in URDU_TO_ARABIC_HADITH_TERMS:
                        mapped_words.append(URDU_TO_ARABIC_HADITH_TERMS[ntok][0])
                    else:
                        mapped_words.append(tok.replace("ک", "ك").replace("ی", "ي").replace("ے", "ي").replace("ہ", "ه"))
                if mapped_words:
                    v = " ".join(mapped_words[:5])
        pairs.append((k, v))
    return urlencode(pairs)


async def fetch_or_get_encyclopedia_route(
    route_path: str,
    query_string: str,
    conn: sqlite3.Connection,
    http_client: httpx.AsyncClient,
    translate_live: bool = True,
) -> Dict[str, Any]:
    """
    Fetches any `hadeeth.com` Encyclopedia route (`/(site)/*`):
    1. Checks `hadeeth_route_cache` in SQLite first (sub-millisecond offline/cached response!).
    2. Resolves local Canonical (`c{id}`) and HadeethEnc (`he{id}`) Hadith detail routes directly from SQLite.
    3. Otherwise fetches `https://hadeeth.com{route_path}/__data.json?{query_string}` live,
       decodes SvelteKit's `devalue` payload, enriches it with Salafi Urdu translations & metadata,
       persists it into `hadeeth_route_cache`, and returns it!
    """
    clean_path = "/" + route_path.strip("/")
    q_str = _clean_sveltekit_query_string(query_string, clean_path, conn)
    cache_key = f"{clean_path}?{q_str}" if q_str else clean_path

    # Direct local resolution for `/dorar/hadith/c{id}` (Canonical) & `/dorar/hadith/he{id}` (HadeethEnc)
    m_local = re.match(r"^/dorar/hadith/(c\d+|he\d+)$", clean_path)
    if m_local:
        tok = m_local.group(1)
        if tok.startswith("c"):
            cid = int(tok[1:])
            cr = conn.execute("SELECT * FROM canonical_hadiths WHERE id = ? LIMIT 1", (cid,)).fetchone()
            if cr:
                return {
                    "hadith": {
                        "hash": tok,
                        "text": cr["matn_vocalized"],
                        "text_urdu": cr["matn_urdu"],
                        "sharh_urdu": cr["sharh_urdu"] or "",
                        "is_truncated": False,
                        "rawi": {"id": 0, "name": cr["section_title_ar"] or ""},
                        "muhaddith": {"id": 0, "name": cr["title_ar"]},
                        "source": {"id": cr["hadeeth_book_id"] or 0, "name": cr["title_ar"]},
                        "source_location": cr["hadith_number"],
                        "hukm": cr["primary_grade_ar"],
                        "hukm_ur": cr["primary_grade_ur"],
                        "has_sharh": bool(cr["sharh_urdu"]),
                        "explanation_is_similar": False,
                        "takhreej": cr["section_title_ar"] or "",
                        "grade_category": 1 if cr["grade_class"] == "ok" else 3,
                        "terminal_type": 0,
                        "explanation_id": None,
                        "sharh_html": cr["sharh_urdu"] or None,
                    },
                    "page_title": f"{cr['title_ar']} ({cr['hadith_number']}) | الباحث الحديثي",
                    "page_description": (cr["matn_urdu"] or cr["matn_vocalized"])[:160],
                }
        else:
            hid = int(tok[2:])
            hr = conn.execute("SELECT * FROM hadeethenc_entries WHERE id = ? LIMIT 1", (hid,)).fetchone()
            if hr:
                return {
                    "hadith": {
                        "hash": tok,
                        "text": hr["matn_vocalized"],
                        "text_urdu": hr["matn_urdu"],
                        "sharh_urdu": hr["explanation_ur"] or "",
                        "is_truncated": False,
                        "rawi": {"id": 0, "name": ""},
                        "muhaddith": {"id": 0, "name": hr["attribution_ar"] or ""},
                        "source": {"id": 0, "name": hr["takhrij_ar"] or hr["attribution_ar"] or ""},
                        "source_location": str(hr["id"]),
                        "hukm": hr["grade_ar"],
                        "hukm_ur": hr["grade_ur"],
                        "has_sharh": True,
                        "explanation_is_similar": False,
                        "takhreej": hr["takhrij_ar"] or "",
                        "grade_category": 1,
                        "terminal_type": 0,
                        "explanation_id": None,
                        "sharh_html": hr["explanation_ar"] or hr["explanation_ur"] or None,
                    },
                    "page_title": f"{hr['title_ur'] or hr['title_ar']} | الباحث الحديثي",
                    "page_description": (hr["matn_urdu"] or hr["matn_vocalized"])[:160],
                }

    from backend.cloud_storage_bridge import get_cached_route, save_cached_route

    cached_raw = get_cached_route(conn, cache_key)
    if cached_raw:
        cached_data = json.loads(cached_raw)
        return enrich_encyclopedia_payload_urdu(clean_path, cached_data, conn, translate_live=translate_live)

    upstream_url = f"https://hadeeth.com{clean_path}/__data.json"
    if q_str:
        upstream_url = f"{upstream_url}?{q_str}"

    try:
        resp = await http_client.get(upstream_url, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            raise ValueError(f"Upstream {upstream_url} returned HTTP {resp.status_code}")
        raw_json = resp.json()
        decoded = decode_sveltekit_devalue(raw_json)
    except Exception:
        # Offline fallback for /dorar/hadith/{hash} directly from 243,154 dorar_hadiths table
        m_dh = re.match(r"^/dorar/hadith/([A-Za-z0-9_-]+)$", clean_path)
        if m_dh:
            h_hash = m_dh.group(1)
            d_row = conn.execute("SELECT * FROM dorar_hadiths WHERE hadith_id = ? LIMIT 1", (h_hash,)).fetchone()
            if d_row:
                decoded = {
                    "hadith": {
                        "hash": d_row["hadith_id"],
                        "text": d_row["matn_vocalized"],
                        "is_truncated": False,
                        "rawi": {"id": d_row["rawi_id"], "name": d_row["rawi_ar"]},
                        "muhaddith": {"id": d_row["mohdith_id"], "name": d_row["mohdith_ar"]},
                        "source": {"id": d_row["book_id"], "name": d_row["book_ar"]},
                        "source_location": d_row["number_or_page"],
                        "hukm": d_row["grade_ar"],
                        "has_sharh": bool(d_row["sharh_id"] or d_row["sharh_vocalized"]),
                        "explanation_is_similar": False,
                        "takhreej": d_row["takhrij_ar"],
                        "grade_category": d_row["grade_bucket"],
                        "terminal_type": d_row["terminal_type"],
                        "explanation_id": int(d_row["sharh_id"]) if str(d_row["sharh_id"]).isdigit() else None,
                        "sharh_html": d_row["sharh_vocalized"] or None,
                    },
                    "page_title": f"حديث {d_row['hadith_id']} | الباحث الحديثي",
                    "page_description": d_row["matn_vocalized"][:160],
                }
            else:
                raise
        else:
            raise

    enriched = enrich_encyclopedia_payload_urdu(clean_path, decoded, conn, translate_live=translate_live)
    save_cached_route(conn, cache_key, json.dumps(enriched, ensure_ascii=False))

    return enriched

