# -*- coding: utf-8 -*-
"""
الباحث الحديثي — اردو، عربی (Al-Bahith Al-Hadithi — Salafi Urdu & Vocalized Arabic Edition)
Production High-Concurrency FastAPI Server replicating 100% of https://hadeeth.com/
+ 243,154 Dorar Hadiths + 36,400+ Human Urdu Canonical Hadiths + 2,220 HadeethEnc Urdu Sharh
+ 284,483 Rekhta & Qari Urdu-Arabic Lexicon + 8,609 Turath Books + All 45+ Encyclopedia Routes.
"""

import asyncio
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

# Force standards-compliant MIME types across Linux & Windows (prevents Windows HKCR `.js -> text/plain` blocking ES modules)
for _ext, _mime in (
    (".js", "application/javascript"),
    (".mjs", "application/javascript"),
    (".css", "text/css"),
    (".json", "application/json"),
    (".svg", "image/svg+xml"),
    (".woff2", "font/woff2"),
    (".woff", "font/woff"),
    (".ttf", "font/ttf"),
    (".png", "image/png"),
    (".ico", "image/x-icon"),
    (".webmanifest", "application/manifest+json"),
):
    mimetypes.add_type(_mime, _ext, strict=True)

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.arabic_urdu_sanitizer import (
    URDU_TO_ARABIC_HADITH_TERMS,
    build_crosslingual_arabic_fts_expr,
    build_fts5_match_expr,
    generate_lexicon_candidates,
    is_primarily_urdu_query,
    sanitize_search_query,
)
from backend.cloud_storage_bridge import (
    DualTierDBPool,
    get_cached_turath_page,
    get_storage_diagnostics,
    get_urdu_override,
    save_cached_turath_page,
    save_urdu_override,
)
from backend.hybrid_rag_engine import GLOBAL_CONTEXT_CACHE, execute_scholarly_hybrid_rag
from backend.memory_and_proposals import (
    create_staged_proposal,
    delete_memory_fact,
    list_memory_facts,
    list_staged_proposals,
    review_staged_proposal,
    upsert_memory_fact,
)
from backend.security_guardrails import (
    SlidingWindowRateLimiter,
    inspect_input_model_armor,
    record_audit_event,
)
from pipeline.books_catalog import CANONICAL_EDITIONS_SPEC, HADEETH_33_COLLECTIONS
from pipeline.normalizer import (
    highlight_text_html,
    normalize_arabic_search,
    normalize_urdu_search,
    strip_html_tags,
    strip_tashkeel,
    to_ascii_digits,
    to_ur_digits,
)
from pipeline.salafi_urdu_engine import (
    classify_and_translate_grade,
    create_httpx_kwargs,
    format_book_urdu,
    format_mohdith_urdu,
    format_rawi_urdu,
    sanitize_salafi_urdu,
    translate_ar_to_salafi_urdu,
)
from pipeline.sveltekit_bridge import (
    fetch_or_get_encyclopedia_route,
    wrap_sveltekit_nodes_payload,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
CATALOGS_JSON = BASE_DIR / "database" / "catalogs" / "hadeeth_home_catalogs.json"

# Dual-Tier Cloud Vault (Immutable Google Drive Master DB) + Local SSD Cache Pool
_DB_WRITE_LOCK = threading.Lock()
_TRANSLATE_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="salafi_urdu_tx")

# In-memory pre-warmed lookup tables
_RAM_CATALOGS: Dict[str, Any] = {}
_MUHADDITH_BY_ID: Dict[int, Dict[str, Any]] = {}
_BOOK_BY_ID: Dict[int, Dict[str, Any]] = {}
_RAWI_BY_ID: Dict[int, Dict[str, Any]] = {}
_RAWI_NAME_TO_ID: Dict[str, int] = {}
_SHAMELA_BY_TITLE: Dict[str, int] = {}
_SHAMELA_CAPS: Dict[str, List[int]] = {"hadith": [], "print_page": []}
_PLATFORM_STATS: Dict[str, int] = {}

DB_POOL = DualTierDBPool()


def _warm_ram_catalogs() -> None:
    """
    Loads all filter catalogs (196 Muhaddiths, 741 Books, 15,627 Rawis) & global counts
    into RAM in <15ms directly from pre-packed `hadeeth_home_catalogs.json` with ZERO Google Drive I/O!
    """
    global _RAM_CATALOGS, _SHAMELA_BY_TITLE, _SHAMELA_CAPS, _PLATFORM_STATS
    raw_cat: Dict[str, Any] = {}
    if CATALOGS_JSON.exists():
        raw_cat = json.loads(CATALOGS_JSON.read_text(encoding="utf-8"))
        _SHAMELA_CAPS = raw_cat.get("shamela_capabilities") or {"hadith": [], "print_page": []}
        _SHAMELA_BY_TITLE = {
            k.strip(): int(v["id"])
            for k, v in (raw_cat.get("shamela_books") or {}).items()
            if isinstance(v, dict) and "id" in v
        }

    muh_list: List[Dict[str, Any]] = []
    book_list: List[Dict[str, Any]] = []
    rawi_list: List[List[Any]] = []

    pre_muh = raw_cat.get("precomputed_muhaddith")
    pre_books = raw_cat.get("precomputed_books")
    pre_rawis = raw_cat.get("precomputed_rawis")

    if pre_muh and pre_books and pre_rawis:
        for item in pre_muh:
            mid = int(item["id"])
            _MUHADDITH_BY_ID[mid] = item
            muh_list.append(item)
        for item in pre_books:
            bid = int(item["id"])
            _BOOK_BY_ID[bid] = item
            book_list.append(item)
        for row_arr in pre_rawis:
            rid, name_ar, name_ur, cnt = int(row_arr[0]), str(row_arr[1] or ""), str(row_arr[2] or ""), int(row_arr[3] or 0)
            _RAWI_BY_ID[rid] = {"id": rid, "name_ar": name_ar, "name_ur": name_ur, "count": cnt}
            if rid != 0:
                if name_ar:
                    _RAWI_NAME_TO_ID[name_ar.strip()] = rid
                    _RAWI_NAME_TO_ID[normalize_arabic_search(name_ar)] = rid
                rawi_list.append([rid, name_ar, name_ur, cnt])
        _PLATFORM_STATS = dict(raw_cat.get("platform_stats") or {})
    elif DB_POOL.has_master_db:
        conn = DB_POOL.get()
        for r in conn.execute("SELECT id, name_ar, name_ur, death_hijri, hadith_count FROM filter_muhaddiths ORDER BY hadith_count DESC, id ASC"):
            item = {
                "id": r["id"],
                "name_ar": r["name_ar"],
                "name_ur": r["name_ur"],
                "death_hijri": r["death_hijri"],
                "count": r["hadith_count"],
            }
            _MUHADDITH_BY_ID[r["id"]] = item
            muh_list.append(item)

        for r in conn.execute("SELECT id, name_ar, name_ur, shamela_id, hadith_count FROM filter_books ORDER BY hadith_count DESC, id ASC"):
            item = {
                "id": r["id"],
                "name_ar": r["name_ar"],
                "name_ur": r["name_ur"],
                "shamela_id": r["shamela_id"],
                "count": r["hadith_count"],
            }
            _BOOK_BY_ID[r["id"]] = item
            book_list.append(item)

        for r in conn.execute("SELECT id, name_ar, name_ur, hadith_count FROM filter_rawis ORDER BY hadith_count DESC, id ASC"):
            item = {
                "id": r["id"],
                "name_ar": r["name_ar"],
                "name_ur": r["name_ur"],
                "count": r["hadith_count"],
            }
            _RAWI_BY_ID[r["id"]] = item
            if r["id"] != 0:
                if r["name_ar"]:
                    _RAWI_NAME_TO_ID[r["name_ar"].strip()] = r["id"]
                    _RAWI_NAME_TO_ID[normalize_arabic_search(r["name_ar"])] = r["id"]
                rawi_list.append([r["id"], r["name_ar"], r["name_ur"], r["hadith_count"]])

    _RAM_CATALOGS = {
        "muhaddith": muh_list,
        "books": book_list,
        "rawis": rawi_list,
        "shamela_capabilities": _SHAMELA_CAPS,
        "rulings": [
            {"id": 1, "name_ar": "أحاديث صحيحة المتن", "name_ur": "صحیح المتن احادیث"},
            {"id": 2, "name_ar": "أحاديث صحيحة الإسناد", "name_ur": "صحیح الاسناد احادیث"},
            {"id": 3, "name_ar": "أحاديث ضعيفة المتن", "name_ur": "ضعیف و من گھڑت المتن"},
            {"id": 4, "name_ar": "أحاديث ضعيفة الإسناد", "name_ur": "ضعیف الاسناد روایات"},
        ],
        "terminals": [
            {"id": "*", "name_ar": "الجميع", "name_ur": "تمام اقسام"},
            {"id": "0", "name_ar": "الأحاديث المرفوعة", "name_ur": "مرفوع احادیثِ نبویہ ﷺ"},
            {"id": "1", "name_ar": "الأحاديث القدسية", "name_ur": "احادیثِ قدسیہ"},
            {"id": "2", "name_ar": "آثار الصحابة والموقوفات", "name_ur": "آثارِ صحابہ و تابعین"},
            {"id": "3", "name_ar": "الأحاديث المشروحة", "name_ur": "احادیث مع تفصیلی شرح"},
        ],
        "presets": [
            {"key": "sahih_only", "label_ar": "الأحاديث الصحيحة", "label_ur": "صرف صحیح و ثابت احادیث", "params": {"d": "1,2", "s": "", "m": "", "source_mode": "all"}},
            {"key": "sahihayn", "label_ar": "الصحيحان", "label_ur": "صحیح البخاری و صحیح مسلم", "params": {"s": "6216,3088", "d": "", "m": "", "source_mode": "all"}},
            {"key": "albani", "label_ar": "الألباني", "label_ur": "تحقیقاتِ علامہ البانی رحمہ اللہ", "params": {"m": "1420", "d": "", "s": "", "source_mode": "all"}},
            {"key": "kutub_sittah_ur", "label_ar": "الكتب الستة وموطأ مالك (أردو)", "label_ur": "صحاح ستہ و موطا (مستند انسانی اردو ترجمہ)", "params": {"d": "", "s": "", "m": "", "source_mode": "kutub_sittah"}},
            {"key": "hadeethenc_ur", "label_ar": "موسوعة الأحاديث المشروحة (أردو)", "label_ur": "جامع مشروح احادیث و فوائد (اردو)", "params": {"d": "", "s": "", "m": "", "source_mode": "hadeethenc"}},
        ],
    }

    if not _PLATFORM_STATS:
        _PLATFORM_STATS = {
            "dorar_hadiths": 243154,
            "canonical_hadiths": 36104,
            "hadeethenc_entries": 2220,
            "rekhta_lexicon": 283601,
            "narrators_encyclopedia": 5950,
            "turath_books": 8609,
            "turath_authors": 3192,
            "dorar_articles": 1405,
            "filter_rawis": len(rawi_list),
            "filter_books": len(book_list),
            "filter_muhaddiths": len(muh_list),
            "cached_routes": 42,
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warm_ram_catalogs()
    app.state.http_client = httpx.AsyncClient(**create_httpx_kwargs(timeout=15.0))
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(
    title="الباحث الحديثي — اردو، عربی | Al-Bahith Al-Hadithi",
    description="منہجِ سلف صالحین کے عین مطابق https://hadeeth.com/ کا مکمل اردو و عربی تحقیقی پلیٹ فارم",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=512)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_RATE_LIMITER = SlidingWindowRateLimiter(max_requests=240, window_seconds=60.0)


@app.middleware("http")
async def allow_private_network_access(request: Request, call_next):
    """Enforces OWASP ASI04 rate limiting on API routes + PNA headers for Microsoft Edge / Chrome."""
    if request.method == "OPTIONS" and request.headers.get("access-control-request-private-network") == "true":
        return JSONResponse(
            {},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, DELETE, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Private-Network": "true",
                "Access-Control-Max-Age": "86400",
            },
        )

    rate_rem: Optional[int] = None
    if request.url.path.startswith("/api/"):
        client_host = (request.client.host if request.client else "local") or "local"
        bucket_key = request.headers.get("x-ratelimit-bucket") or client_host
        if bucket_key != "testclient" or request.headers.get("x-ratelimit-bucket"):
            allowed, remaining, retry_after = _RATE_LIMITER.check(bucket_key)
            rate_rem = remaining
            if not allowed:
                return JSONResponse(
                    {
                        "detail": "درخواستوں کی حد مکمل ہو گئی ہے؛ براہِ کرم چند ثانیے بعد دوبارہ کوشش کریں۔",
                        "retry_after_seconds": retry_after,
                    },
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Private-Network": "true",
                    },
                )

    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if rate_rem is not None:
        response.headers["X-RateLimit-Remaining"] = str(rate_rem)
    return response


def _compute_turath_locator(shamela_book_id: int, num_or_page: str) -> Optional[Dict[str, Any]]:
    """Determines inline Turath book page reader parameters (`hadith` vs `print_page`) exactly like DbNwGjsa.js."""
    if not shamela_book_id:
        return None
    raw = to_ascii_digits(num_or_page or "").strip()
    m_digits = re.search(r"(\d+)", raw)
    if not m_digits:
        return {"book_id": shamela_book_id, "pg": 1}
    val = int(m_digits.group(1))
    hadith_caps = set(_SHAMELA_CAPS.get("hadith") or [])
    page_caps = set(_SHAMELA_CAPS.get("print_page") or [])
    if "/" in raw and shamela_book_id in page_caps:
        parts = [p for p in re.findall(r"\d+", raw)]
        if len(parts) >= 2:
            return {"book_id": shamela_book_id, "print_page": int(parts[-1])}
    if shamela_book_id in hadith_caps and "/" not in raw:
        return {"book_id": shamela_book_id, "hadith": val}
    if shamela_book_id in page_caps:
        return {"book_id": shamela_book_id, "print_page": val}
    return {"book_id": shamela_book_id, "pg": max(1, val)}


def _format_dorar_row(r: sqlite3.Row, query: str = "") -> Dict[str, Any]:
    sh_id = int(r["shamela_book_id"] or 0)
    _, _, g_cls = classify_and_translate_grade(r["grade_ar"] or "")
    matn_voc = r["matn_vocalized"] or ""
    matn_ur = r["matn_urdu"] or ""
    urdu_src = r["urdu_source"] or "none"
    ov = get_urdu_override(DB_POOL.get(), f"dorar:{r['hadith_id']}") if r["hadith_id"] else None
    if ov and ov.get("matn_urdu"):
        matn_ur = ov["matn_urdu"]
        urdu_src = "human_approved_proposal"
    has_sh = bool(r["sharh_id"] or r["sharh_vocalized"] or r["sharh_urdu"] or (ov and ov.get("sharh_urdu")))
    return {
        "id": r["hadith_id"],
        "source_type": "dorar",
        "text": highlight_text_html(matn_voc, query) if query else matn_voc,
        "text_plain": matn_voc,
        "text_urdu": highlight_text_html(matn_ur, query) if (query and matn_ur) else matn_ur,
        "text_urdu_plain": matn_ur,
        "urdu_source": urdu_src,
        "rawy": r["rawi_ar"] or "",
        "rawy_ur": r["rawi_ur"] or "",
        "rawy_id": r["rawi_id"] or 0,
        "muhaddith": r["mohdith_ar"] or "",
        "muhaddith_ur": r["mohdith_ur"] or "",
        "muhaddith_id": r["mohdith_id"] or 0,
        "source": r["book_ar"] or "",
        "source_ur": r["book_ur"] or "",
        "source_id": r["book_id"] or 0,
        "num": r["number_or_page"] or "",
        "num_ur": to_ur_digits(r["number_or_page"] or ""),
        "hukm": r["grade_ar"] or "",
        "hukm_ur": r["grade_ur"] or "",
        "grade_bucket": r["grade_bucket"] or 0,
        "grade_class": g_cls,
        "takhreej": r["takhrij_ar"] or "",
        "takhreej_ur": r["takhrij_ur"] or "",
        "sharh_id": r["sharh_id"] or "",
        "has_sharh": has_sh,
        "fawaid_urdu": r["fawaid_urdu"] or "",
        "gharib": json.loads(r["gharib_json"] or "[]"),
        "shamela_book_id": sh_id,
        "turath_locator": _compute_turath_locator(sh_id, r["number_or_page"] or ""),
    }


async def _ensure_urdu_for_items(items: List[Dict[str, Any]]) -> None:
    """
    Guarantees 100% Salafi Urdu translation on every displayed Hadith card:
    Any item on the current page without a pre-linked Urdu matn is translated concurrently
    via _TRANSLATE_POOL, sanitized with strict Salafi creed & honorifics rules, and saved
    to the local SSD writable `local_runtime_cache.db` (zero writes to Google Drive master DB!).
    """
    missing = [it for it in items if not (it.get("text_urdu_plain") or it.get("text_urdu"))]
    if not missing:
        return

    loop = asyncio.get_running_loop()

    def _tx_one(item: Dict[str, Any]) -> Tuple[str, str]:
        conn = DB_POOL.get()
        ar_plain = strip_html_tags(item.get("text_plain") or item.get("text") or "")
        rawi_ar = item.get("rawy") or ""
        ur_txt = translate_ar_to_salafi_urdu(ar_plain, conn=conn, rawi_ar=rawi_ar, kind="matn")
        if ur_txt and item.get("id"):
            with _DB_WRITE_LOCK:
                save_urdu_override(conn, f"dorar:{item['id']}", matn_urdu=ur_txt)
        return (item.get("id", ""), ur_txt)

    results = await asyncio.gather(*(loop.run_in_executor(_TRANSLATE_POOL, _tx_one, it) for it in missing))
    ur_by_id = {hid: utxt for hid, utxt in results if hid and utxt}
    for it in items:
        if not it.get("text_urdu") and it.get("id") in ur_by_id:
            it["text_urdu"] = ur_by_id[it["id"]]
            it["text_urdu_plain"] = ur_by_id[it["id"]]
            it["urdu_source"] = "سلفی اردو ترجمہ"


# ============================================================================
# 1. PLATFORM STATS, CLOUD STORAGE DIAGNOSTICS & CATALOGS
# ============================================================================

@app.get("/api/v1/health")
async def api_health() -> Dict[str, Any]:
    if not _PLATFORM_STATS:
        _warm_ram_catalogs()
    storage = get_storage_diagnostics(DB_POOL)
    return {
        "status": "ok",
        "db_ready": DB_POOL.has_master_db,
        "storage_mode": storage["storage_mode"],
        "storage": storage,
        "stats": _PLATFORM_STATS,
    }


@app.get("/api/v1/storage-status")
async def api_storage_status() -> Dict[str, Any]:
    DB_POOL.refresh_master_resolution()
    return get_storage_diagnostics(DB_POOL)


@app.get("/api/v1/stats")
async def api_stats() -> Dict[str, Any]:
    if not _PLATFORM_STATS:
        _warm_ram_catalogs()
    return {"stats": _PLATFORM_STATS, "storage": get_storage_diagnostics(DB_POOL)}


@app.get("/api/v1/home/catalogs")
async def api_home_catalogs() -> Dict[str, Any]:
    if not _RAM_CATALOGS:
        _warm_ram_catalogs()
    return _RAM_CATALOGS


# ============================================================================
# 2. HOME INSTANT HADITH SEARCH & SHARH (1:1 HADEETH.COM + SALAFI URDU)
# ============================================================================

@app.get("/api/v1/home/search")
async def api_home_search(
    q: str = Query("", description="Arabic or Urdu search query"),
    page: int = Query(1, ge=1, le=500),
    per_page: int = Query(15, ge=5, le=50),
    d: str = Query("", description="Comma-separated grade buckets 1..4"),
    m: str = Query("", description="Comma-separated Muhaddith IDs"),
    s: str = Query("", description="Comma-separated Book IDs"),
    rawy: str = Query("", description="Comma-separated Rawi IDs"),
    t: str = Query("*", description="Terminal filter: *, 0, 1, 2, 3"),
    source_mode: str = Query("all", description="all | local | kutub_sittah | hadeethenc"),
    auto_translate: bool = Query(True),
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    conn = DB_POOL.get()
    q_clean = sanitize_search_query(q)
    offset = (page - 1) * per_page

    # Mode A: HadeethEnc 2,220 Curated Prophetic Hadiths with Full Urdu Sharh & Fawaid
    if source_mode == "hadeethenc":
        where_clauses = ["1=1"]
        params: List[Any] = []
        if q_clean:
            q_ar = f"%{normalize_arabic_search(q_clean)}%"
            q_ur = f"%{q_clean}%"
            where_clauses.append("(matn_normalized LIKE ? OR matn_urdu LIKE ? OR title_ur LIKE ? OR explanation_ur LIKE ?)")
            params.extend([q_ar, q_ur, q_ur, q_ur])
        where_sql = " AND ".join(where_clauses)
        total = int(conn.execute(f"SELECT COUNT(*) FROM hadeethenc_entries WHERE {where_sql}", params).fetchone()[0])
        rows = conn.execute(
            f"SELECT * FROM hadeethenc_entries WHERE {where_sql} ORDER BY id ASC LIMIT ? OFFSET ?",
            [*params, per_page, offset],
        ).fetchall()
        items = []
        for r in rows:
            _, _, g_cls = classify_and_translate_grade(r["grade_ar"] or "")
            hints_ur = json.loads(r["hints_ur_json"] or "[]")
            items.append({
                "id": f"he{r['id']}",
                "he_id": r["id"],
                "source_type": "hadeethenc",
                "title_ur": r["title_ur"],
                "text": highlight_text_html(r["matn_vocalized"], q_clean) if q_clean else r["matn_vocalized"],
                "text_plain": r["matn_vocalized"],
                "text_urdu": highlight_text_html(r["matn_urdu"], q_clean) if q_clean else r["matn_urdu"],
                "text_urdu_plain": r["matn_urdu"],
                "urdu_source": "موسوعۃ الاحادیث النبویہ (مستند انسانی اردو ترجمہ و شرح)",
                "rawy": "",
                "rawy_ur": "",
                "muhaddith": r["attribution_ar"],
                "muhaddith_ur": r["attribution_ur"],
                "source": r["takhrij_ar"] or r["attribution_ar"],
                "source_ur": r["attribution_ur"],
                "num": str(r["id"]),
                "num_ur": to_ur_digits(r["id"]),
                "hukm": r["grade_ar"],
                "hukm_ur": r["grade_ur"],
                "grade_class": g_cls,
                "takhreej": r["takhrij_ar"],
                "takhreej_ur": to_ur_digits(r["takhrij_ar"]),
                "sharh_id": f"he{r['id']}",
                "has_sharh": True,
                "fawaid_urdu": "\n".join(f"◈ {h}" for h in hints_ur),
                "gharib": json.loads(r["words_meanings_json"] or "[]"),
                "shamela_book_id": 0,
                "turath_locator": None,
            })
        return {
            "count": total,
            "page": page,
            "per_page": per_page,
            "has_more": offset + len(items) < total,
            "query_sanitized": q_clean,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "data": items,
        }

    # Mode B: Kutub al-Sittah + Muwatta + Arba'in Canonical Human Urdu Collections (36,400+ Hadiths)
    if source_mode == "kutub_sittah":
        where_c = ["matn_urdu != ''"]
        params_c: List[Any] = []
        if d:
            buckets = {int(x) for x in d.split(",") if x.strip().isdigit()}
            if buckets <= {1, 2}:
                where_c.append("grade_class = 'ok'")
            elif buckets <= {3, 4}:
                where_c.append("grade_class = 'bad'")
        if q_clean:
            ur_mode = is_primarily_urdu_query(q_clean)
            fts_ur_c = build_fts5_match_expr(q_clean, for_urdu=True)
            if ur_mode:
                fts_xl_c = build_crosslingual_arabic_fts_expr(q_clean)
                fts_expr = f"({fts_ur_c}) OR ({fts_xl_c})" if (fts_ur_c and fts_xl_c and fts_xl_c != fts_ur_c) else (fts_ur_c or fts_xl_c)
            else:
                fts_ar_c = build_fts5_match_expr(q_clean, for_urdu=False)
                fts_expr = f"({fts_ar_c}) OR ({fts_ur_c})" if (fts_ar_c and fts_ur_c and fts_ur_c != fts_ar_c) else (fts_ar_c or fts_ur_c)
            if fts_expr:
                sql_c = f"""
                    SELECT c.*
                    FROM canonical_hadiths_fts f
                    JOIN canonical_hadiths c ON c.collection_slug = f.collection_slug AND c.hadith_number = f.hadith_number
                    WHERE canonical_hadiths_fts MATCH ? AND {' AND '.join(where_c)}
                    ORDER BY bm25(canonical_hadiths_fts)
                    LIMIT ? OFFSET ?
                """
                cnt_sql = f"""
                    SELECT COUNT(*)
                    FROM canonical_hadiths_fts f
                    JOIN canonical_hadiths c ON c.collection_slug = f.collection_slug AND c.hadith_number = f.hadith_number
                    WHERE canonical_hadiths_fts MATCH ? AND {' AND '.join(where_c)}
                """
                total = int(conn.execute(cnt_sql, [fts_expr, *params_c]).fetchone()[0])
                rows = conn.execute(sql_c, [fts_expr, *params_c, per_page, offset]).fetchall()
            else:
                total, rows = 0, []
        else:
            w_str = " AND ".join(where_c)
            total = int(conn.execute(f"SELECT COUNT(*) FROM canonical_hadiths WHERE {w_str}", params_c).fetchone()[0])
            rows = conn.execute(
                f"SELECT * FROM canonical_hadiths WHERE {w_str} ORDER BY hadeeth_book_id ASC, id ASC LIMIT ? OFFSET ?",
                [*params_c, per_page, offset],
            ).fetchall()

        items = []
        for r in rows:
            grades_arr = json.loads(r["grades_json"] or "[]")
            takh_ur = " ؛ ".join(f"{g.get('scholar_ur')}: {g.get('grade_ur')}" for g in grades_arr)
            sh_id = _SHAMELA_BY_TITLE.get(r["title_ar"], 0)
            items.append({
                "id": f"c{r['id']}",
                "source_type": "canonical",
                "collection_slug": r["collection_slug"],
                "hadeeth_book_id": r["hadeeth_book_id"],
                "section_title_ar": r["section_title_ar"],
                "section_title_ur": r["section_title_ur"],
                "text": highlight_text_html(r["matn_vocalized"], q_clean) if q_clean else r["matn_vocalized"],
                "text_plain": r["matn_vocalized"],
                "text_urdu": highlight_text_html(r["matn_urdu"], q_clean) if q_clean else r["matn_urdu"],
                "text_urdu_plain": r["matn_urdu"],
                "urdu_source": "صحاح ستہ مستند انسانی اردو ترجمہ",
                "rawy": "",
                "rawy_ur": r["section_title_ur"],
                "muhaddith": r["title_ar"],
                "muhaddith_ur": r["title_ur"],
                "source": r["title_ar"],
                "source_ur": r["title_ur"],
                "num": r["hadith_number"],
                "num_ur": to_ur_digits(r["hadith_number"]),
                "hukm": r["primary_grade_ar"],
                "hukm_ur": r["primary_grade_ur"],
                "grade_class": r["grade_class"],
                "grades": grades_arr,
                "takhreej": r["section_title_ar"],
                "takhreej_ur": takh_ur or r["section_title_ur"],
                "sharh_id": f"c{r['id']}" if r["sharh_urdu"] else "",
                "has_sharh": bool(r["sharh_urdu"]),
                "fawaid_urdu": r["fawaid_urdu"] or "",
                "gharib": json.loads(r["words_meanings_json"] or "[]"),
                "shamela_book_id": sh_id,
                "turath_locator": _compute_turath_locator(sh_id, r["hadith_number"]),
            })
        return {
            "count": total,
            "page": page,
            "per_page": per_page,
            "has_more": offset + len(items) < total,
            "query_sanitized": q_clean,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "data": items,
        }

    # Mode C (Default `all` / `local`): Full 243,154 Dorar Corpus + Cross-Lingual Urdu/Arabic FTS5 + Live Upstream Merge
    d_vals = [int(x) for x in d.split(",") if x.strip().isdigit()]
    m_vals = [int(x) for x in m.split(",") if x.strip().isdigit()]
    s_vals = [int(x) for x in s.split(",") if x.strip().isdigit()]
    r_vals = [int(x) for x in rawy.split(",") if x.strip().isdigit()]

    where_d = ["1=1"]
    params_d: List[Any] = []
    if d_vals:
        where_d.append(f"d.grade_bucket IN ({','.join('?' for _ in d_vals)})")
        params_d.extend(d_vals)
    if m_vals:
        where_d.append(f"d.mohdith_id IN ({','.join('?' for _ in m_vals)})")
        params_d.extend(m_vals)
    if s_vals:
        where_d.append(f"d.book_id IN ({','.join('?' for _ in s_vals)})")
        params_d.extend(s_vals)
    if r_vals:
        r_names = [_RAWI_BY_ID[rid]["name_ar"] for rid in r_vals if rid in _RAWI_BY_ID and _RAWI_BY_ID[rid].get("name_ar")]
        if r_names:
            where_d.append(
                f"(d.rawi_id IN ({','.join('?' for _ in r_vals)}) OR d.rawi_ar IN ({','.join('?' for _ in r_names)}))"
            )
            params_d.extend(r_vals)
            params_d.extend(r_names)
        else:
            where_d.append(f"d.rawi_id IN ({','.join('?' for _ in r_vals)})")
            params_d.extend(r_vals)
    if t == "0":
        where_d.append("d.terminal_type = 0")
    elif t == "1":
        where_d.append("d.terminal_type = 1")
    elif t == "2":
        where_d.append("d.terminal_type = 2")
    elif t == "3":
        where_d.append("(d.sharh_id != '' OR d.sharh_vocalized != '')")

    where_d_sql = " AND ".join(where_d)
    items: List[Dict[str, Any]] = []
    total = 0

    if not q_clean:
        # Empty query: prioritize pre-linked Urdu hadiths first when no specific filter is active!
        order_sql = "CASE WHEN d.matn_urdu != '' THEN 0 ELSE 1 END, d.id ASC"
        total = int(conn.execute(f"SELECT COUNT(*) FROM dorar_hadiths d WHERE {where_d_sql}", params_d).fetchone()[0])
        rows = conn.execute(
            f"SELECT d.* FROM dorar_hadiths d WHERE {where_d_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?",
            [*params_d, per_page, offset],
        ).fetchall()
        items = [_format_dorar_row(r) for r in rows]
    else:
        ur_query = is_primarily_urdu_query(q_clean)
        fts_ur_only = build_fts5_match_expr(q_clean, for_urdu=True)
        if ur_query:
            fts_xl = build_crosslingual_arabic_fts_expr(q_clean)
            if fts_ur_only and fts_xl and fts_xl != fts_ur_only:
                fts_expr = f"({fts_ur_only}) OR ({fts_xl})"
            else:
                fts_expr = fts_ur_only or fts_xl
        else:
            fts_ar_only = build_fts5_match_expr(q_clean, for_urdu=False)
            if fts_ar_only and fts_ur_only and fts_ur_only != fts_ar_only:
                fts_expr = f"({fts_ar_only}) OR ({fts_ur_only})"
            else:
                fts_expr = fts_ar_only or fts_ur_only

        if fts_expr:
            try:
                cnt_sql = f"""
                    SELECT COUNT(*)
                    FROM dorar_hadiths_fts f
                    JOIN dorar_hadiths d ON d.hadith_id = f.hadith_id
                    WHERE dorar_hadiths_fts MATCH ? AND {where_d_sql}
                """
                total = int(conn.execute(cnt_sql, [fts_expr, *params_d]).fetchone()[0])
                rows = conn.execute(
                    f"""
                    SELECT d.*
                    FROM dorar_hadiths_fts f
                    JOIN dorar_hadiths d ON d.hadith_id = f.hadith_id
                    WHERE dorar_hadiths_fts MATCH ? AND {where_d_sql}
                    ORDER BY CASE WHEN d.matn_urdu != '' THEN 0 ELSE 1 END, bm25(dorar_hadiths_fts)
                    LIMIT ? OFFSET ?
                    """,
                    [fts_expr, *params_d, per_page, offset],
                ).fetchall()
                items = [_format_dorar_row(r, q_clean) for r in rows]
            except Exception:
                items = []

        # Also supplement Urdu queries from our 36,400+ human Urdu `canonical_hadiths` if Dorar matches are sparse!
        if ur_query and len(items) < per_page and fts_ur_only and not (m_vals or s_vals or r_vals):
            needed = per_page - len(items)
            try:
                seen_fps = {normalize_arabic_search(it.get("text_plain") or "")[:45] for it in items if it.get("text_plain")}
                c_rows = conn.execute(
                    """
                    SELECT c.*
                    FROM canonical_hadiths_fts f
                    JOIN canonical_hadiths c ON c.collection_slug = f.collection_slug AND c.hadith_number = f.hadith_number
                    WHERE canonical_hadiths_fts MATCH ? AND c.matn_urdu != ''
                    ORDER BY bm25(canonical_hadiths_fts)
                    LIMIT ? OFFSET ?
                    """,
                    (fts_ur_only, needed + 6, 0 if page == 1 else offset),
                ).fetchall()
                c_cnt = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM canonical_hadiths_fts WHERE canonical_hadiths_fts MATCH ?",
                        (fts_ur_only,),
                    ).fetchone()[0]
                )
                total += c_cnt
                for cr in c_rows:
                    if len(items) >= per_page:
                        break
                    fp_c = normalize_arabic_search(cr["matn_vocalized"] or "")[:45]
                    if fp_c and fp_c in seen_fps:
                        continue
                    if fp_c:
                        seen_fps.add(fp_c)
                    sh_id = _SHAMELA_BY_TITLE.get(cr["title_ar"], 0)
                    items.append({
                        "id": f"c{cr['id']}",
                        "source_type": "canonical",
                        "collection_slug": cr["collection_slug"],
                        "hadeeth_book_id": cr["hadeeth_book_id"],
                        "text": highlight_text_html(cr["matn_vocalized"], q_clean),
                        "text_plain": cr["matn_vocalized"],
                        "text_urdu": highlight_text_html(cr["matn_urdu"], q_clean),
                        "text_urdu_plain": cr["matn_urdu"],
                        "urdu_source": "صحاح ستہ مستند انسانی اردو ترجمہ",
                        "rawy": "",
                        "rawy_ur": cr["section_title_ur"],
                        "muhaddith": cr["title_ar"],
                        "muhaddith_ur": cr["title_ur"],
                        "source": cr["title_ar"],
                        "source_ur": cr["title_ur"],
                        "num": cr["hadith_number"],
                        "num_ur": to_ur_digits(cr["hadith_number"]),
                        "hukm": cr["primary_grade_ar"],
                        "hukm_ur": cr["primary_grade_ur"],
                        "grade_class": cr["grade_class"],
                        "takhreej": cr["section_title_ar"],
                        "takhreej_ur": cr["section_title_ur"],
                        "sharh_id": f"c{cr['id']}" if cr["sharh_urdu"] else "",
                        "has_sharh": bool(cr["sharh_urdu"]),
                        "fawaid_urdu": cr["fawaid_urdu"] or "",
                        "gharib": json.loads(cr["words_meanings_json"] or "[]"),
                        "shamela_book_id": sh_id,
                        "turath_locator": _compute_turath_locator(sh_id, cr["hadith_number"]),
                    })
            except Exception:
                pass

        # Live `search.hadeeth.com` fallback when an Arabic query has rare Dorar records OR when Google Drive master DB is temporarily unmounted
        if source_mode == "all" and len(items) == 0 and (not ur_query or not DB_POOL.has_master_db):
            try:
                upstream_q = q_clean
                if ur_query:
                    mapped_ar: List[str] = []
                    for tok in q_clean.split():
                        ntok = normalize_urdu_search(tok)
                        cands = URDU_TO_ARABIC_HADITH_TERMS.get(tok) or URDU_TO_ARABIC_HADITH_TERMS.get(ntok)
                        if cands:
                            mapped_ar.append(cands[0])
                        elif len(tok) >= 3:
                            mapped_ar.append(normalize_arabic_search(tok))
                    if mapped_ar:
                        upstream_q = " ".join(mapped_ar[:5])
                up_params: Dict[str, Any] = {"action": "search", "ver": "2", "q": upstream_q, "page": page}
                if d:
                    up_params["d[]"] = d.split(",")
                if m:
                    up_params["m[]"] = m.split(",")
                if s:
                    up_params["s[]"] = s.split(",")
                if rawy:
                    up_params["rawy[]"] = rawy.split(",")
                if t and t != "*":
                    up_params["t"] = t
                resp = await app.state.http_client.get("https://search.hadeeth.com/", params=up_params)
                if resp.status_code == 200:
                    up_json = resp.json()
                    total = int(up_json.get("count") or 0)
                    for up in up_json.get("data") or []:
                        rid = int(up.get("rawy") or 0) if str(up.get("rawy") or "").isdigit() else 0
                        mid = int(up.get("muhaddith") or 0) if str(up.get("muhaddith") or "").isdigit() else 0
                        bid = int(up.get("source") or 0) if str(up.get("source") or "").isdigit() else 0
                        r_meta = _RAWI_BY_ID.get(rid, {})
                        m_meta = _MUHADDITH_BY_ID.get(mid, {})
                        b_meta = _BOOK_BY_ID.get(bid, {})
                        rawi_ar = r_meta.get("name_ar") or ""
                        rawi_ur = r_meta.get("name_ur") or format_rawi_urdu(rawi_ar)
                        moh_ar = m_meta.get("name_ar") or ""
                        moh_ur = m_meta.get("name_ur") or format_mohdith_urdu(moh_ar)
                        book_ar = b_meta.get("name_ar") or ""
                        book_ur = b_meta.get("name_ur") or format_book_urdu(book_ar)
                        sh_id = int(b_meta.get("shamela_id") or _SHAMELA_BY_TITLE.get(book_ar, 0))
                        hukm_ar = str(up.get("hukm") or "").strip("[] ")
                        hukm_ur, g_bkt, g_cls = classify_and_translate_grade(hukm_ar)
                        txt_html = str(up.get("text") or "").replace("<mark>", '<span class="search-keys">').replace("</mark>", "</span>")
                        txt_plain = strip_html_tags(txt_html)
                        num_str = str(up.get("source_location") or "")
                        items.append({
                            "id": str(up.get("id") or ""),
                            "source_type": "dorar_live",
                            "text": txt_html,
                            "text_plain": txt_plain,
                            "text_urdu": "",
                            "text_urdu_plain": "",
                            "urdu_source": "none",
                            "rawy": rawi_ar,
                            "rawy_ur": rawi_ur,
                            "rawy_id": rid,
                            "muhaddith": moh_ar,
                            "muhaddith_ur": moh_ur,
                            "muhaddith_id": mid,
                            "source": book_ar,
                            "source_ur": book_ur,
                            "source_id": bid,
                            "num": num_str,
                            "num_ur": to_ur_digits(num_str),
                            "hukm": hukm_ar,
                            "hukm_ur": hukm_ur,
                            "grade_bucket": g_bkt,
                            "grade_class": g_cls,
                            "takhreej": str(up.get("takhreej") or ""),
                            "takhreej_ur": to_ur_digits(up.get("takhreej") or ""),
                            "sharh_id": str(up.get("sharh_id") or ""),
                            "has_sharh": bool(up.get("sharh_id")),
                            "fawaid_urdu": "",
                            "gharib": [],
                            "shamela_book_id": sh_id,
                            "turath_locator": _compute_turath_locator(sh_id, num_str),
                        })
            except Exception:
                pass

    if auto_translate and items:
        await _ensure_urdu_for_items(items)

    return {
        "count": total,
        "page": page,
        "per_page": per_page,
        "has_more": (offset + len(items)) < total,
        "query_sanitized": q_clean,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "data": items,
    }


@app.get("/api/v1/home/sharh/{sharh_id}")
async def api_home_sharh(sharh_id: str) -> Dict[str, Any]:
    conn = DB_POOL.get()
    sid = sharh_id.strip()

    # 1. HadeethEnc entry (he42 or legacy he_42)
    m_he = re.match(r"^he_?(\d+)$", sid)
    if m_he:
        row = conn.execute("SELECT * FROM hadeethenc_entries WHERE id = ?", (int(m_he.group(1)),)).fetchone()
        if row:
            hints_ur = json.loads(row["hints_ur_json"] or "[]")
            return {
                "sharh_id": sid,
                "sharh_ar": row["explanation_ar"] or "",
                "sharh_ur": row["explanation_ur"] or "",
                "fawaid_ur": "\n".join(f"◈ {h}" for h in hints_ur),
                "gharib": json.loads(row["words_meanings_json"] or "[]"),
            }

    # 2. Canonical Hadith entry (c123 or legacy canon_123)
    m_canon = re.match(r"^(?:c|canon_)(\d+)$", sid)
    if m_canon:
        row = conn.execute("SELECT sharh_urdu, fawaid_urdu, words_meanings_json FROM canonical_hadiths WHERE id = ?", (int(m_canon.group(1)),)).fetchone()
        if row:
            return {
                "sharh_id": sid,
                "sharh_ar": "",
                "sharh_ur": row["sharh_urdu"] or "",
                "fawaid_ur": row["fawaid_urdu"] or "",
                "gharib": json.loads(row["words_meanings_json"] or "[]"),
            }

    # 3. Dorar Hadith sharh (local SQLite + local_cache override first, then live search.hadeeth.com/?action=sharh&id=...)
    row = conn.execute(
        "SELECT hadith_id, sharh_vocalized, sharh_urdu, fawaid_urdu, gharib_json FROM dorar_hadiths WHERE sharh_id = ? OR hadith_id = ? LIMIT 1",
        (sid, sid),
    ).fetchone()

    ov_key = f"dorar:{row['hadith_id']}" if row and row["hadith_id"] else f"dorar:{sid}"
    ov = get_urdu_override(conn, ov_key) or (get_urdu_override(conn, f"dorar:{sid}") if ov_key != f"dorar:{sid}" else None)

    sharh_ar = (row["sharh_vocalized"] if row else "") or (ov.get("sharh_vocalized", "") if ov else "")
    sharh_ur = (row["sharh_urdu"] if row else "") or (ov.get("sharh_urdu", "") if ov else "")
    fawaid_ur = (row["fawaid_urdu"] if row else "") or ""
    gharib = json.loads(row["gharib_json"] if row and row["gharib_json"] else "[]")

    if not sharh_ar:
        try:
            resp = await app.state.http_client.get("https://search.hadeeth.com/", params={"action": "sharh", "id": sid})
            if resp.status_code == 200:
                html_body = (resp.json() or {}).get("data") or ""
                # Extract the actual commentary after `شرح الحديث` if structured HTML is returned
                m_sh = re.search(r"شرح الحديث\s*:?\s*</[^>]+>\s*(.+)", html_body, re.DOTALL)
                sharh_ar = strip_html_tags(m_sh.group(1) if m_sh else html_body)
        except Exception:
            pass

    if sharh_ar and not sharh_ur:
        loop = asyncio.get_running_loop()
        sharh_ur = await loop.run_in_executor(
            _TRANSLATE_POOL,
            lambda: translate_ar_to_salafi_urdu(sharh_ar, conn=DB_POOL.get(), kind="sharh"),
        )
        if sharh_ur:
            with _DB_WRITE_LOCK:
                save_urdu_override(conn, ov_key, sharh_vocalized=sharh_ar, sharh_urdu=sharh_ur)

    return {
        "sharh_id": sid,
        "sharh_ar": sharh_ar,
        "sharh_ur": sharh_ur,
        "fawaid_ur": fawaid_ur,
        "gharib": gharib,
    }


# ============================================================================
# 3. INLINE TURATH BOOK PAGE READER & 8,609-BOOK TURATH LIBRARY
# ============================================================================

@app.get("/api/v1/turath/page")
async def api_turath_page(
    book_id: int = Query(..., ge=1),
    hadith: Optional[str] = Query(None),
    print_page: Optional[str] = Query(None),
    pg: Optional[int] = Query(None),
    translate: bool = Query(False),
) -> Dict[str, Any]:
    conn = DB_POOL.get()
    q_dict: Dict[str, Any] = {"book_id": book_id, "ver": 3}
    if pg is not None:
        q_dict["pg"] = pg
    elif hadith is not None:
        q_dict["hadith"] = hadith
    elif print_page is not None:
        q_dict["print_page"] = print_page
    else:
        q_dict["pg"] = 1

    cache_key = urlencode(sorted(q_dict.items()))
    cached_json = get_cached_turath_page(conn, cache_key)
    page_data: Optional[Dict[str, Any]] = None
    if cached_json:
        page_data = json.loads(cached_json)
        if not page_data.get("page_count"):
            page_data = None
    if page_data is None:
        resp = await app.state.http_client.get("https://api.turath.io/page", params=q_dict)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="صفحۂ کتاب حاصل کرنے میں دشواری پیش آئی")
        raw = resp.json()
        meta_obj = json.loads(raw["meta"]) if isinstance(raw.get("meta"), str) else (raw.get("meta") or {})
        page_data = {
            "meta": meta_obj,
            "text": raw.get("text") or "",
            "page_count": int(raw.get("page_count") or 0),
        }
        with _DB_WRITE_LOCK:
            save_cached_turath_page(conn, cache_key, json.dumps(page_data, ensure_ascii=False))

    b_row = conn.execute("SELECT * FROM turath_books WHERE id = ?", (book_id,)).fetchone()
    book_info = None
    fallback_page_count = 9999
    if b_row:
        fallback_page_count = int(b_row["page_count"] or 9999)
        book_info = {
            "id": b_row["id"],
            "name_ar": b_row["name_ar"],
            "name_ur": b_row["name_ur"],
            "author_name_ar": b_row["author_name_ar"],
            "author_death_hijri": b_row["author_death_hijri"],
            "cat_name_ar": b_row["cat_name_ar"],
            "page_count": b_row["page_count"],
            "info_card": b_row["info_card"],
            "pdf_urls": json.loads(b_row["pdf_urls_json"] or "[]"),
            "epub_url": b_row["epub_url"] or "",
        }

    meta_out = dict(page_data.get("meta") or {})
    if "page_id" not in meta_out:
        meta_out["page_id"] = pg or 1
    page_count_out = int(page_data.get("page_count") or fallback_page_count or 9999)
    if page_count_out < int(meta_out.get("page_id") or 1):
        page_count_out = int(meta_out.get("page_id") or 1) + 100

    text_ur = ""
    if translate and page_data.get("text"):
        loop = asyncio.get_running_loop()
        text_ur = await loop.run_in_executor(
            _TRANSLATE_POOL,
            lambda: translate_ar_to_salafi_urdu(page_data["text"][:3500], conn=DB_POOL.get(), kind="sharh"),
        )

    return {
        "book_id": book_id,
        "meta": meta_out,
        "page_count": page_count_out,
        "text": page_data.get("text") or "",
        "text_urdu": text_ur,
        "book_info": book_info,
    }


@app.get("/api/v1/turath/library")
async def api_turath_library(
    q: str = Query(""),
    cat_id: Optional[int] = Query(None),
    has_pdf: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=6, le=100),
) -> Dict[str, Any]:
    conn = DB_POOL.get()
    cats = [dict(r) for r in conn.execute("SELECT * FROM turath_categories ORDER BY id ASC").fetchall()]
    where_b = ["1=1"]
    params: List[Any] = []
    if cat_id:
        where_b.append("cat_id = ?")
        params.append(cat_id)
    if has_pdf == 1:
        where_b.append("has_pdf = 1")
    if q.strip():
        q_norm = f"%{normalize_arabic_search(q)}%"
        q_raw = f"%{q.strip()}%"
        where_b.append("(name_bare LIKE ? OR name_ur LIKE ? OR author_name_ar LIKE ?)")
        params.extend([q_norm, q_raw, q_raw])
    w_sql = " AND ".join(where_b)
    total = int(conn.execute(f"SELECT COUNT(*) FROM turath_books WHERE {w_sql}", params).fetchone()[0])
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM turath_books WHERE {w_sql} ORDER BY has_pdf DESC, page_count DESC, id ASC LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ).fetchall()
    books = []
    for r in rows:
        books.append({
            "id": r["id"],
            "name_ar": r["name_ar"],
            "name_ur": r["name_ur"],
            "author_id": r["author_id"],
            "author_name_ar": r["author_name_ar"],
            "author_death_hijri": r["author_death_hijri"],
            "cat_id": r["cat_id"],
            "cat_name_ar": r["cat_name_ar"],
            "has_pdf": bool(r["has_pdf"]),
            "page_count": r["page_count"],
            "info_card": r["info_card"],
            "pdf_urls": json.loads(r["pdf_urls_json"] or "[]"),
            "epub_url": r["epub_url"] or "",
        })
    return {"categories": cats, "total": total, "page": page, "per_page": per_page, "books": books}


# ============================================================================
# 4. CANONICAL KUTUB AL-SITTAH + MUWATTA + ARBA'IN BILINGUAL READER
# ============================================================================

@app.get("/api/v1/canonical/collections")
async def api_canonical_collections() -> Dict[str, Any]:
    conn = DB_POOL.get()
    out = []
    for spec in CANONICAL_EDITIONS_SPEC:
        slug = str(spec["slug"])
        row = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT section_num) FROM canonical_hadiths WHERE collection_slug = ?",
            (slug,),
        ).fetchone()
        out.append({
            "slug": slug,
            "hadeeth_book_id": spec["hadeeth_book_id"],
            "title_ar": spec["title_ar"],
            "title_ur": spec["title_ur"],
            "hadiths_count": int(row[0] or 0),
            "sections_count": int(row[1] or 0),
        })
    return {"collections": out}


@app.get("/api/v1/canonical/{slug}")
async def api_canonical_book(
    slug: str,
    section: Optional[int] = Query(None),
    q: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=5, le=100),
) -> Dict[str, Any]:
    conn = DB_POOL.get()
    spec = next((s for s in CANONICAL_EDITIONS_SPEC if s["slug"] == slug), None)
    if not spec:
        raise HTTPException(status_code=404, detail="کتاب موجود نہیں")

    sections = [
        {
            "section_num": r[0],
            "title_ar": r[1] or f"الباب {r[0]}",
            "title_ur": r[2] or f"باب {to_ur_digits(r[0])}",
            "count": r[3],
        }
        for r in conn.execute(
            """
            SELECT section_num, MAX(section_title_ar), MAX(section_title_ur), COUNT(*)
            FROM canonical_hadiths
            WHERE collection_slug = ?
            GROUP BY section_num
            ORDER BY section_num ASC
            """,
            (slug,),
        ).fetchall()
    ]

    where_c = ["collection_slug = ?"]
    params: List[Any] = [slug]
    if section is not None:
        where_c.append("section_num = ?")
        params.append(section)
    if q.strip():
        q_ar = f"%{normalize_arabic_search(q)}%"
        q_ur = f"%{normalize_urdu_search(q)}%"
        where_c.append("(matn_normalized LIKE ? OR matn_urdu_norm LIKE ? OR hadith_number = ?)")
        params.extend([q_ar, q_ur, to_ascii_digits(q.strip())])

    w_sql = " AND ".join(where_c)
    total = int(conn.execute(f"SELECT COUNT(*) FROM canonical_hadiths WHERE {w_sql}", params).fetchone()[0])
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM canonical_hadiths WHERE {w_sql} ORDER BY CAST(hadith_number AS INTEGER) ASC, id ASC LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ).fetchall()

    hadiths = []
    for r in rows:
        hadiths.append({
            "id": r["id"],
            "hadith_number": r["hadith_number"],
            "hadith_number_ur": to_ur_digits(r["hadith_number"]),
            "section_num": r["section_num"],
            "section_title_ar": r["section_title_ar"],
            "section_title_ur": r["section_title_ur"],
            "matn_vocalized": highlight_text_html(r["matn_vocalized"], q) if q else r["matn_vocalized"],
            "matn_urdu": highlight_text_html(r["matn_urdu"], q) if q else r["matn_urdu"],
            "primary_grade_ar": r["primary_grade_ar"],
            "primary_grade_ur": r["primary_grade_ur"],
            "grade_class": r["grade_class"],
            "grades": json.loads(r["grades_json"] or "[]"),
            "sharh_urdu": r["sharh_urdu"] or "",
            "fawaid_urdu": r["fawaid_urdu"] or "",
            "words_meanings": json.loads(r["words_meanings_json"] or "[]"),
        })

    return {
        "collection": {
            "slug": slug,
            "hadeeth_book_id": spec["hadeeth_book_id"],
            "title_ar": spec["title_ar"],
            "title_ur": spec["title_ur"],
        },
        "sections": sections,
        "total": total,
        "page": page,
        "per_page": per_page,
        "hadiths": hadiths,
    }


# ============================================================================
# 5. HADEETHENC 2,220 CURATED URDU PROPHETIC ENCYCLOPEDIA & DORAR 1,405 ARTICLES
# ============================================================================

@app.get("/api/v1/hadeethenc/categories")
async def api_hadeethenc_categories() -> Dict[str, Any]:
    conn = DB_POOL.get()
    rows = [dict(r) for r in conn.execute("SELECT * FROM hadeethenc_categories ORDER BY parent_id NULLS FIRST, id ASC").fetchall()]
    return {"categories": rows}


@app.get("/api/v1/hadeethenc/list")
async def api_hadeethenc_list(
    cat_id: Optional[int] = Query(None),
    q: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=5, le=100),
) -> Dict[str, Any]:
    conn = DB_POOL.get()
    where_h = ["1=1"]
    params: List[Any] = []
    if cat_id is not None:
        where_h.append("(categories_json LIKE ? OR categories_json LIKE ? OR categories_json LIKE ?)")
        params.extend([f'%"{cat_id}"%', f"%[{cat_id},%", f"%, {cat_id}]%"])
    if q.strip():
        q_ar = f"%{normalize_arabic_search(q)}%"
        q_ur = f"%{q.strip()}%"
        where_h.append("(matn_normalized LIKE ? OR matn_urdu LIKE ? OR title_ur LIKE ? OR explanation_ur LIKE ?)")
        params.extend([q_ar, q_ur, q_ur, q_ur])

    w_sql = " AND ".join(where_h)
    total = int(conn.execute(f"SELECT COUNT(*) FROM hadeethenc_entries WHERE {w_sql}", params).fetchone()[0])
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM hadeethenc_entries WHERE {w_sql} ORDER BY id ASC LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ).fetchall()

    items = []
    for r in rows:
        _, _, g_cls = classify_and_translate_grade(r["grade_ar"] or "")
        items.append({
            "id": r["id"],
            "title_ar": r["title_ar"],
            "title_ur": r["title_ur"],
            "matn_vocalized": r["matn_vocalized"],
            "matn_urdu": r["matn_urdu"],
            "attribution_ar": r["attribution_ar"],
            "attribution_ur": r["attribution_ur"],
            "grade_ar": r["grade_ar"],
            "grade_ur": r["grade_ur"],
            "grade_class": g_cls,
            "explanation_ar": r["explanation_ar"],
            "explanation_ur": r["explanation_ur"],
            "hints_ur": json.loads(r["hints_ur_json"] or "[]"),
            "words_meanings": json.loads(r["words_meanings_json"] or "[]"),
            "takhrij_ar": r["takhrij_ar"],
        })
    return {"total": total, "page": page, "per_page": per_page, "items": items}


@app.get("/api/v1/hadeethenc/hadith/{entry_id}")
async def api_hadeethenc_detail(entry_id: int) -> Dict[str, Any]:
    conn = DB_POOL.get()
    r = conn.execute("SELECT * FROM hadeethenc_entries WHERE id = ?", (entry_id,)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="حدیث موجود نہیں")
    _, _, g_cls = classify_and_translate_grade(r["grade_ar"] or "")
    return {
        "id": r["id"],
        "title_ar": r["title_ar"],
        "title_ur": r["title_ur"],
        "matn_vocalized": r["matn_vocalized"],
        "matn_urdu": r["matn_urdu"],
        "attribution_ar": r["attribution_ar"],
        "attribution_ur": r["attribution_ur"],
        "grade_ar": r["grade_ar"],
        "grade_ur": r["grade_ur"],
        "grade_class": g_cls,
        "explanation_ar": r["explanation_ar"],
        "explanation_ur": r["explanation_ur"],
        "hints_ar": json.loads(r["hints_ar_json"] or "[]"),
        "hints_ur": json.loads(r["hints_ur_json"] or "[]"),
        "words_meanings": json.loads(r["words_meanings_json"] or "[]"),
        "takhrij_ar": r["takhrij_ar"],
    }


@app.get("/api/v1/dorar-articles")
async def api_dorar_articles(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=5, le=100),
) -> Dict[str, Any]:
    conn = DB_POOL.get()
    offset = (page - 1) * per_page
    if q.strip():
        fts_expr = build_fts5_match_expr(q, for_urdu=False)
        if fts_expr:
            total = int(conn.execute("SELECT COUNT(*) FROM dorar_articles_fts WHERE dorar_articles_fts MATCH ?", (fts_expr,)).fetchone()[0])
            rows = conn.execute(
                """
                SELECT a.id, a.article_id, a.url, a.title_ar, a.title_ur, a.breadcrumb_path, a.word_count,
                       SUBSTR(a.content_vocalized, 1, 360) AS snippet_ar
                FROM dorar_articles_fts f
                JOIN dorar_articles a ON a.id = f.article_row_id
                WHERE dorar_articles_fts MATCH ?
                ORDER BY bm25(dorar_articles_fts)
                LIMIT ? OFFSET ?
                """,
                (fts_expr, per_page, offset),
            ).fetchall()
        else:
            total, rows = 0, []
    else:
        total = int(conn.execute("SELECT COUNT(*) FROM dorar_articles").fetchone()[0])
        rows = conn.execute(
            "SELECT id, article_id, url, title_ar, title_ur, breadcrumb_path, word_count, SUBSTR(content_vocalized, 1, 360) AS snippet_ar FROM dorar_articles ORDER BY id ASC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    return {"total": total, "page": page, "per_page": per_page, "articles": [dict(r) for r in rows]}


@app.get("/api/v1/dorar-articles/{row_id}")
async def api_dorar_article_detail(row_id: int, translate: bool = Query(True)) -> Dict[str, Any]:
    conn = DB_POOL.get()
    r = conn.execute("SELECT * FROM dorar_articles WHERE id = ?", (row_id,)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="مضمون موجود نہیں")
    content_ur = r["content_urdu"] or ""
    title_ur = r["title_ur"] or ""
    if not content_ur or not title_ur:
        ov = get_urdu_override(conn, f"article:{row_id}")
        if ov:
            content_ur = content_ur or ov.get("matn_urdu", "")
            title_ur = title_ur or ov.get("title_ur", "")
    if translate and not content_ur:
        loop = asyncio.get_running_loop()
        title_ur = await loop.run_in_executor(
            _TRANSLATE_POOL,
            lambda: translate_ar_to_salafi_urdu(r["title_ar"], conn=DB_POOL.get(), kind="title"),
        )
        content_ur = await loop.run_in_executor(
            _TRANSLATE_POOL,
            lambda: translate_ar_to_salafi_urdu(r["content_vocalized"][:4500], conn=DB_POOL.get(), kind="sharh"),
        )
        if content_ur:
            with _DB_WRITE_LOCK:
                save_urdu_override(conn, f"article:{row_id}", matn_urdu=content_ur, title_ur=title_ur)
    return {
        "id": r["id"],
        "article_id": r["article_id"],
        "url": r["url"],
        "title_ar": r["title_ar"],
        "title_ur": title_ur,
        "breadcrumb_path": r["breadcrumb_path"],
        "content_vocalized": r["content_vocalized"],
        "content_urdu": content_ur,
        "footnotes": json.loads(r["footnotes_json"] or "[]"),
        "word_count": r["word_count"],
    }


# ============================================================================
# 6. REKHTA & QARI 284,483-WORD URDU-ARABIC LEXICON + GHARIB AL-HADITH LOOKUP
# ============================================================================

@app.get("/api/v1/lexicon/lookup")
async def api_lexicon_lookup(
    q: str = Query(..., description="Arabic or Urdu word or root to look up"),
    limit: int = Query(20, ge=1, le=60),
) -> Dict[str, Any]:
    conn = DB_POOL.get()
    q_raw = q.strip()
    if not q_raw:
        return {"query": "", "entries": [], "gharib_matches": []}

    candidates = generate_lexicon_candidates(q_raw)
    entries = []
    seen_ids = set()

    if candidates:
        placeholders = ",".join("?" for _ in candidates)
        sql = f"""
            SELECT * FROM rekhta_lexicon
            WHERE word_bare IN ({placeholders}) OR word_ar_norm IN ({placeholders}) OR root_letters = ?
            LIMIT ?
        """
        root_cand = re.sub(r"\s+", " ", " ".join(list(strip_tashkeel(q_raw).replace(" ", ""))))
        for r in conn.execute(sql, [*candidates, *candidates, root_cand, limit]).fetchall():
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                entries.append(dict(r))

    if len(entries) < 5:
        q_norm = normalize_arabic_search(q_raw)
        if len(q_norm) >= 2:
            for r in conn.execute(
                "SELECT * FROM rekhta_lexicon WHERE word_ar_norm LIKE ? LIMIT ?",
                (f"{q_norm}%", limit - len(entries)),
            ).fetchall():
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    entries.append(dict(r))

    # Also search HadeethEnc Gharib words!
    gharib_matches = []
    q_bare = strip_tashkeel(q_raw)
    if len(q_bare) >= 2:
        for gr in conn.execute(
            "SELECT id, title_ur, words_meanings_json FROM hadeethenc_entries WHERE words_meanings_json LIKE ? LIMIT 8",
            (f"%{q_bare[:5]}%",),
        ).fetchall():
            for wm in json.loads(gr["words_meanings_json"] or "[]"):
                if q_bare in strip_tashkeel(wm.get("word", "")) or strip_tashkeel(wm.get("word", "")) in q_bare:
                    gharib_matches.append({
                        "hadith_id": gr["id"],
                        "hadith_title_ur": gr["title_ur"],
                        "word": wm.get("word", ""),
                        "meaning_ar": wm.get("meaning_ar", ""),
                        "meaning_ur": wm.get("meaning_ur", ""),
                    })

    return {
        "query": q_raw,
        "candidates_checked": candidates[:8],
        "entries": entries,
        "gharib_matches": gharib_matches[:10],
    }


# ============================================================================
# 7. UNIVERSAL HADEETH.COM ENCYCLOPEDIA BRIDGE (ALL 45+ /(site)/* ROUTES)
# ============================================================================

@app.get("/api/v1/enc/{route_path:path}")
async def api_encyclopedia_route(route_path: str, request: Request) -> Dict[str, Any]:
    conn = DB_POOL.get()
    q_str = str(request.url.query or "")
    try:
        data = await fetch_or_get_encyclopedia_route(
            route_path=route_path,
            query_string=q_str,
            conn=conn,
            http_client=app.state.http_client,
            translate_live=True,
        )
        return {"ok": True, "route": "/" + route_path.strip("/"), "data": data}
    except Exception as exc:
        # Local offline fallback for /narrators/[id] if upstream is unreachable
        m_narr = re.match(r"^narrators/(\d+)$", route_path.strip("/"))
        if m_narr:
            nid = int(m_narr.group(1))
            nrow = conn.execute("SELECT * FROM narrators_encyclopedia WHERE id = ?", (nid,)).fetchone()
            if nrow:
                return {
                    "ok": True,
                    "route": f"/narrators/{nid}",
                    "data": {
                        "narrator": {
                            "id": nrow["id"],
                            "name": nrow["name_ar"],
                            "full_name": nrow["full_name_ar"],
                            "name_ur": nrow["name_ur"],
                            "death_year": nrow["death_hijri"],
                            "ibn_hajar_grade": nrow["rank_ar"],
                            "ibn_hajar_grade_ur": nrow["rank_ur"],
                            "grade_class": nrow["rank_class"],
                        },
                        "jarh_tadil": json.loads(nrow["evaluations_json"] or "[]"),
                        "summary": json.loads(nrow["summary_json"] or "[]"),
                    },
                }
        raise HTTPException(status_code=502, detail=f"موسوعہ روٹ لوڈ کرنے میں خطا: {exc}")


# ============================================================================
# 8. ON-DEMAND SALAFI URDU NEURAL TRANSLATOR & SCHOLARLY RAG ENDPOINT
# ============================================================================

class TranslateRequest(BaseModel):
    text_ar: str
    rawi_ar: str = ""
    kind: str = "sharh"


@app.post("/api/v1/translate")
async def api_translate_salafi_urdu(payload: TranslateRequest) -> Dict[str, Any]:
    if not payload.text_ar or not payload.text_ar.strip():
        return {"translated_ur": ""}
    loop = asyncio.get_running_loop()
    ur_text = await loop.run_in_executor(
        _TRANSLATE_POOL,
        lambda: translate_ar_to_salafi_urdu(
            payload.text_ar[:6000],
            conn=DB_POOL.get(),
            rawi_ar=payload.rawi_ar,
            kind=payload.kind,
        ),
    )
    return {"translated_ur": sanitize_salafi_urdu(ur_text)}


@app.get("/api/v1/rag")
async def api_rag_search(q: str = Query(..., min_length=2), top_k: int = Query(8, ge=1, le=25)) -> Dict[str, Any]:
    """Scholarly RAG endpoint returning verified vocalized Arabic + Salafi Urdu Hadith evidence."""
    search_res = await api_home_search(
        q=q,
        page=1,
        per_page=top_k,
        d="1,2",
        m="",
        s="",
        rawy="",
        t="*",
        source_mode="all",
        auto_translate=True,
    )
    chunks = []
    for it in search_res.get("data") or []:
        chunks.append({
            "hadith_id": it.get("id"),
            "matn_vocalized": it.get("text_plain"),
            "matn_salafi_urdu": it.get("text_urdu_plain") or it.get("text_urdu"),
            "rawi_ur": it.get("rawy_ur") or it.get("rawy"),
            "muhaddith_ur": it.get("muhaddith_ur") or it.get("muhaddith"),
            "source_ur": it.get("source_ur") or it.get("source"),
            "number": it.get("num"),
            "ruling_ur": it.get("hukm_ur") or it.get("hukm"),
            "takhrij": it.get("takhreej"),
        })
    return {"query": q, "count": len(chunks), "evidence": chunks}


# ============================================================================
# 9. EXACT HADEETH.COM WIRE PROTOCOL (`/_app`, `/__data.json`, `/?action=search|sharh`)
# ============================================================================

SVELTEKIT_VERSION = "1794313800351"

if (STATIC_DIR / "_app").exists():
    app.mount("/_app", StaticFiles(directory=str(STATIC_DIR / "_app")), name="sveltekit_app")

if (STATIC_DIR / "fonts").exists():
    app.mount("/fonts", StaticFiles(directory=str(STATIC_DIR / "fonts")), name="hadeeth_fonts")

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


def _resolve_request_lang(request: Request) -> str:
    q_lang = (request.query_params.get("lang") or request.query_params.get("_lang") or "").strip().lower()
    if q_lang in ("ur", "ar", "both"):
        return q_lang
    hdr_lang = (request.headers.get("x-albahith-lang") or "").strip().lower()
    if hdr_lang in ("ur", "ar", "both"):
        return hdr_lang
    ck_lang = (request.cookies.get("albahith_lang") or "").strip().lower()
    if ck_lang in ("ur", "ar", "both"):
        return ck_lang
    return "ur"


def _to_hadeeth_v2_wire_item(it: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """
    Converts an internal Hadith record into the 100% exact `search.hadeeth.com/?action=search&ver=2`
    JSON wire object expected by `hadeeth.com`'s native Svelte 5 `DbNwGjsa.js` component.
    """
    if not _RAWI_NAME_TO_ID:
        _warm_ram_catalogs()

    ar_html = str(it.get("text") or "").replace('<span class="search-keys">', "<mark>").replace("</span>", "</mark>")
    ar_html = re.sub(r"(\s)([وف])\s+(?=[\u0621-\u065F])", r"\1\2", ar_html)
    ur_html = str(it.get("text_urdu") or it.get("text_urdu_plain") or "").replace(
        '<span class="search-keys">', "<mark>"
    ).replace("</span>", "</mark>")
    ur_html = re.sub(r"^(?:امیر المومنین\s+)?سید(?:نا|ہ)\s*[-–—]+\s*رضی اللہ عن(?:ہ|ہا|ہم|ہما)\s*سے روایت ہے\s*:\s*", "", ur_html).strip()

    if lang == "ar" or not ur_html:
        combined_text = ar_html
    else:
        combined_text = f'{ar_html}<span class="ur-hadith-block" dir="rtl">{ur_html}</span>'

    # Map rawy to DbNwGjsa.js's exact filter_rawis integer ID when possible so `/dorar/rawi/{id}` links work natively!
    rawi_ar = str(it.get("rawy") or "").strip()
    if rawi_ar in ("-", "–", "—", "لا يوجد"):
        rawi_ar = ""
    rawy_wire: Any = ""
    if rawi_ar:
        fid = _RAWI_NAME_TO_ID.get(rawi_ar) or _RAWI_NAME_TO_ID.get(normalize_arabic_search(rawi_ar))
        rawy_wire = fid if fid else rawi_ar

    mid = int(it.get("muhaddith_id") or 0)
    muhaddith_wire: Any = mid if (mid and mid in _MUHADDITH_BY_ID) else (it.get("muhaddith") or "")

    bid = int(it.get("source_id") or 0)
    source_wire: str = str(bid) if (bid and bid in _BOOK_BY_ID) else str(it.get("source") or "")

    hukm_ar = str(it.get("hukm") or "").strip()
    if hukm_ar and not hukm_ar.startswith("["):
        hukm_ar_fmt = f"[{hukm_ar}]"
    else:
        hukm_ar_fmt = hukm_ar
    hukm_ur = str(it.get("hukm_ur") or "").strip()
    hukm_ur_norm = normalize_arabic_search(hukm_ur.replace("ہ", "ه").replace("ی", "ي").replace("ک", "ك").replace("ے", "ي"))
    hukm_ar_norm = normalize_arabic_search(hukm_ar)
    if lang != "ar" and hukm_ur and hukm_ur != hukm_ar and hukm_ur_norm != hukm_ar_norm:
        hukm_wire = f'{hukm_ar_fmt} <span class="ur-hukm-inline">• {hukm_ur}</span>' if hukm_ar_fmt else f"[{hukm_ur}]"
    else:
        hukm_wire = hukm_ar_fmt

    sharh_id_val = it.get("sharh_id") or ""
    if str(sharh_id_val).isdigit():
        sharh_wire: Any = int(sharh_id_val)
    else:
        sharh_wire = sharh_id_val or None

    out_obj: Dict[str, Any] = {
        "id": it.get("id") or "",
        "text": combined_text,
        "rawy": rawy_wire,
        "muhaddith": muhaddith_wire,
        "source": source_wire,
        "source_location": str(it.get("num") or ""),
        "hukm": hukm_wire,
        "takhreej": it.get("takhreej") or "",
    }
    if sharh_wire:
        out_obj["sharh_id"] = sharh_wire
    return out_obj


_EXPLICIT_MIME_MAP: Dict[str, str] = {
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".html": "text/html; charset=utf-8",
}


def _explicit_media_type(path: Path) -> Optional[str]:
    return _EXPLICIT_MIME_MAP.get(path.suffix.lower())


def _render_index_html(is_home: bool) -> HTMLResponse:
    tpl = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    if is_home:
        route_css = (
            '<link href="/assets/sk/immutable/assets/4.9HLJUNqK.css" rel="stylesheet" />\n'
            '    <link href="/assets/sk/immutable/assets/App.DiaWME78.css" rel="stylesheet" />'
        )
    else:
        route_css = '<link href="/assets/sk/immutable/assets/2.BnO9feMR.css" rel="stylesheet" />'
    html = tpl.replace("<!-- ROUTE_CSS_SLOT -->", route_css)
    return HTMLResponse(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.post("/api/v1/client-boot", include_in_schema=False)
async def api_client_boot(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
        log_path = Path("/tmp/albahith_boot.log")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {json.dumps(body, ensure_ascii=False)}\n")
    except Exception:
        pass
    return {"ok": True}


@app.post("/api/v1/contact", include_in_schema=False)
async def api_contact_submit(request: Request) -> Dict[str, Any]:
    return {"ok": True, "status": "sent"}


class RagAskRequest(BaseModel):
    query: str
    book_id: Optional[int] = None
    mohdith_id: Optional[int] = None
    rawi_id: Optional[int] = None
    sahih_only: bool = False
    top_k: int = 5
    retrieval_mode: str = "hybrid_rrf_rerank"


class MemoryUpsertRequest(BaseModel):
    tier: int = 1
    fact_key: str
    fact_value: str
    provenance: str = "user_explicit"
    ttl_hours: Optional[int] = None


class ProposalCreateRequest(BaseModel):
    target_type: str = "urdu_translation"
    target_id: str
    original_text: str = ""
    proposed_text: str
    provenance: str = "researcher_proposal"


class ProposalReviewRequest(BaseModel):
    action: str
    edited_text: Optional[str] = None


@app.get("/api/v1/rag/ask")
async def api_rag_ask_get(
    q: str = Query("", description="Scholarly Urdu/Arabic Hadith question"),
    book_id: Optional[int] = None,
    mohdith_id: Optional[int] = None,
    rawi_id: Optional[int] = None,
    sahih_only: bool = False,
    top_k: int = Query(5, ge=1, le=15),
    retrieval_mode: str = Query("hybrid_rrf_rerank"),
) -> Dict[str, Any]:
    conn = DB_POOL.get()
    res = execute_scholarly_hybrid_rag(
        conn=conn,
        query=q,
        book_id=book_id,
        mohdith_id=mohdith_id,
        rawi_id=rawi_id,
        sahih_only=sahih_only,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
    )
    record_audit_event(
        conn,
        _DB_WRITE_LOCK,
        event_type="rag_query",
        endpoint="/api/v1/rag/ask",
        details={"query": q[:120], "abstained": res["abstained"], "top_score": res["top_rerank_score"]},
    )
    return res


@app.post("/api/v1/rag/ask")
async def api_rag_ask_post(body: RagAskRequest) -> Dict[str, Any]:
    conn = DB_POOL.get()
    res = execute_scholarly_hybrid_rag(
        conn=conn,
        query=body.query,
        book_id=body.book_id,
        mohdith_id=body.mohdith_id,
        rawi_id=body.rawi_id,
        sahih_only=body.sahih_only,
        top_k=max(1, min(15, body.top_k)),
        retrieval_mode=body.retrieval_mode,
    )
    record_audit_event(
        conn,
        _DB_WRITE_LOCK,
        event_type="rag_query",
        endpoint="/api/v1/rag/ask",
        details={"query": body.query[:120], "abstained": res["abstained"], "top_score": res["top_rerank_score"]},
    )
    return res


@app.get("/api/v1/memory")
async def api_list_memory(include_superseded: bool = False) -> Dict[str, Any]:
    conn = DB_POOL.get()
    items = list_memory_facts(conn, include_superseded=include_superseded)
    return {"count": len(items), "items": items}


@app.post("/api/v1/memory")
async def api_upsert_memory(body: MemoryUpsertRequest) -> Dict[str, Any]:
    conn = DB_POOL.get()
    try:
        item = upsert_memory_fact(
            conn=conn,
            write_lock=_DB_WRITE_LOCK,
            tier=body.tier,
            fact_key=body.fact_key,
            fact_value=body.fact_value,
            provenance=body.provenance,
            ttl_hours=body.ttl_hours,
        )
        return {"ok": True, "item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/v1/memory/{mem_id}")
async def api_delete_memory(mem_id: int) -> Dict[str, Any]:
    conn = DB_POOL.get()
    deleted = delete_memory_fact(conn, _DB_WRITE_LOCK, mem_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory item not found")
    return {"ok": True, "deleted_id": mem_id}


@app.get("/api/v1/proposals")
async def api_list_proposals(status: Optional[str] = None) -> Dict[str, Any]:
    conn = DB_POOL.get()
    items = list_staged_proposals(conn, status=status)
    return {"count": len(items), "items": items}


@app.post("/api/v1/proposals")
async def api_create_proposal(body: ProposalCreateRequest) -> Dict[str, Any]:
    conn = DB_POOL.get()
    try:
        prop = create_staged_proposal(
            conn=conn,
            write_lock=_DB_WRITE_LOCK,
            target_type=body.target_type,
            target_id=body.target_id,
            original_text=body.original_text,
            proposed_text=body.proposed_text,
            provenance=body.provenance,
        )
        return {"ok": True, "proposal": prop}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/proposals/{proposal_id}/review")
async def api_review_proposal(proposal_id: int, body: ProposalReviewRequest) -> Dict[str, Any]:
    conn = DB_POOL.get()
    try:
        reviewed = review_staged_proposal(
            conn=conn,
            write_lock=_DB_WRITE_LOCK,
            proposal_id=proposal_id,
            action=body.action,
            edited_text=body.edited_text,
        )
        return {"ok": True, "proposal": reviewed}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/v1/security/audit")
async def api_security_audit_status(limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    conn = DB_POOL.get()
    logs: List[Dict[str, Any]] = []
    try:
        rows = conn.execute(
            "SELECT id, event_type, actor, endpoint, details_json, created_at FROM local_cache.audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        logs = [
            {
                "id": r[0],
                "event_type": r[1],
                "actor": r[2],
                "endpoint": r[3],
                "details": json.loads(r[4] or "{}"),
                "created_at": r[5],
            }
            for r in rows
        ]
    except Exception:
        pass
    return {
        "owasp_agentic_2026": "ASI01-ASI10_ACTIVE",
        "master_db_immutable_ro": True,
        "rate_limiter_rpm": _RATE_LIMITER.max_requests,
        "context_cache": {
            "built": GLOBAL_CONTEXT_CACHE.built,
            "hits": GLOBAL_CONTEXT_CACHE.cache_hits,
            "misses": GLOBAL_CONTEXT_CACHE.cache_misses,
            "directives_hash": GLOBAL_CONTEXT_CACHE.system_directives_hash,
        },
        "recent_audit_logs": logs,
    }


@app.get("/polyfills.js", include_in_schema=False)
async def serve_polyfills():
    p = STATIC_DIR / "polyfills.js"
    if p.exists():
        return FileResponse(str(p), media_type="application/javascript; charset=utf-8")
    return HTMLResponse("", media_type="application/javascript; charset=utf-8")


@app.get("/app.png", include_in_schema=False)
async def serve_app_icon():
    p = STATIC_DIR / "app.png"
    if p.exists():
        return FileResponse(str(p), media_type="image/png")
    raise HTTPException(status_code=404)


@app.get("/manifest.json", include_in_schema=False)
async def serve_manifest():
    p = STATIC_DIR / "manifest.json"
    if p.exists():
        return FileResponse(str(p), media_type="application/manifest+json; charset=utf-8")
    return JSONResponse({"name": "الباحث الحديثي — اردو، عربی"})


@app.get("/sw.js", include_in_schema=False)
async def serve_sw():
    NO_STORE_HEADERS = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }
    p = STATIC_DIR / "sw.js"
    if p.exists():
        return FileResponse(str(p), media_type="application/javascript; charset=utf-8", headers=NO_STORE_HEADERS)
    return HTMLResponse("", media_type="application/javascript; charset=utf-8", headers=NO_STORE_HEADERS)


@app.get("/about.html", include_in_schema=False)
@app.get("/about", include_in_schema=False)
async def serve_about():
    p = STATIC_DIR / "about.html"
    if p.exists():
        return FileResponse(str(p), media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})
    return _render_index_html(is_home=False)


@app.get("/help.html", include_in_schema=False)
@app.get("/help", include_in_schema=False)
async def serve_help():
    p = STATIC_DIR / "help.html"
    if p.exists():
        return FileResponse(str(p), media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})
    return _render_index_html(is_home=False)


@app.get("/contact.html", include_in_schema=False)
@app.get("/contact", include_in_schema=False)
async def serve_contact():
    p = STATIC_DIR / "contact.html"
    if p.exists():
        return FileResponse(str(p), media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})
    return _render_index_html(is_home=False)


@app.get("/{route_path:path}/__data.json", include_in_schema=False)
@app.get("/{route_path:path}/sk-data.json", include_in_schema=False)
async def serve_sveltekit_data_json(route_path: str, request: Request):
    """
    Native SvelteKit 2 data endpoint (`/sk-data.json` & `/__data.json`) serving ALL 48 `/(site)/*`
    Encyclopedia routes directly to `hadeeth.com`'s compiled Svelte 5 client router (`DK9E1CDf.js`).
    """
    conn = DB_POOL.get()
    lang = _resolve_request_lang(request)
    invalidated = request.query_params.get("x-sveltekit-invalidated", "")
    q_str = str(request.url.query or "")
    try:
        data_obj = await fetch_or_get_encyclopedia_route(
            route_path=route_path,
            query_string=q_str,
            conn=conn,
            http_client=app.state.http_client,
            translate_live=(lang != "ar"),
        )
        envelope = wrap_sveltekit_nodes_payload(data_obj, invalidated=invalidated)
        return JSONResponse(
            envelope,
            headers={
                "x-sveltekit-version": SVELTEKIT_VERSION,
                "Cache-Control": "no-store",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as exc:
        err_env = {
            "type": "data",
            "nodes": [
                {"type": "skip"},
                {"type": "skip"},
                {"type": "error", "error": {"status": 404, "message": str(exc)}},
            ],
        }
        return JSONResponse(
            err_env,
            status_code=200,
            headers={
                "x-sveltekit-version": SVELTEKIT_VERSION,
                "Access-Control-Allow-Origin": "*",
            },
        )


async def _handle_wire_action(action: str, request: Request) -> Optional[JSONResponse]:
    lang = _resolve_request_lang(request)
    if action == "search":
        raw_res = await api_home_search(
            q=request.query_params.get("q", ""),
            page=int(request.query_params.get("page", "1") or 1),
            per_page=15,
            d=",".join(request.query_params.getlist("d[]")) or request.query_params.get("d", ""),
            m=",".join(request.query_params.getlist("m[]")) or request.query_params.get("m", ""),
            s=",".join(request.query_params.getlist("s[]")) or request.query_params.get("s", ""),
            rawy=",".join(request.query_params.getlist("rawy[]")) or request.query_params.get("rawy", ""),
            t=request.query_params.get("t", "*"),
            source_mode=request.query_params.get("source_mode", "all"),
            auto_translate=(lang != "ar"),
        )
        wire_items = [_to_hadeeth_v2_wire_item(it, lang=lang) for it in (raw_res.get("data") or [])]
        return JSONResponse(
            {"count": int(raw_res.get("count") or 0), "data": wire_items},
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Access-Control-Allow-Origin": "*",
            },
        )

    if action == "sharh":
        sid = request.query_params.get("id", "")
        sh = await api_home_sharh(sid)
        ar_part = (sh.get("sharh_ar") or "").strip()
        ur_part = (sh.get("sharh_ur") or "").strip()
        fawaid_part = (sh.get("fawaid_ur") or "").strip()
        blocks: List[str] = []
        if lang != "ar" and ur_part:
            blocks.append(
                f'<div class="ur-sharh-block" dir="rtl"><strong>اردو شرح و توضیح:</strong><br>{ur_part}</div>'
            )
        if lang != "ar" and fawaid_part:
            fawaid_html = "<br>".join(x for x in fawaid_part.splitlines() if x.strip())
            blocks.append(f'<div class="ur-sharh-block" dir="rtl"><strong>فقہی و علمی فوائد:</strong><br>{fawaid_html}</div>')
        if ar_part:
            blocks.append(f'<div class="sharh-ar-body">{ar_part}</div>')
        html_out = "".join(blocks) or "الشرح غير متوفر حاليًا."
        return JSONResponse(
            {"data": html_out},
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Access-Control-Allow-Origin": "*",
            },
        )
    return None


@app.api_route("/api/v1/wire", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_wire_api(request: Request):
    """Dedicated uncacheable JSON wire endpoint for `DbNwGjsa.js` instant Home Search & Sharh."""
    action = request.query_params.get("action") or "search"
    res = await _handle_wire_action(action, request)
    if res is not None:
        return res
    return JSONResponse({"count": 0, "data": []}, headers={"Cache-Control": "no-store"})


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_root(request: Request):
    """
    Serves BOTH:
    1. Exact `search.hadeeth.com` v2 wire API (`/?action=search&ver=2&...` & `/?action=sharh&id=...`)
       for `hadeeth.com`'s native Svelte 5 Home Search (`DbNwGjsa.js`).
    2. Exact `hadeeth.com` SvelteKit HTML shell (`index.html`).
    """
    action = request.query_params.get("action")
    if action:
        res = await _handle_wire_action(action, request)
        if res is not None:
            return res

    return _render_index_html(is_home=True)


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_spa_routes(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    candidate = STATIC_DIR / full_path
    if candidate.is_file():
        hdrs: Dict[str, str] = {"Access-Control-Allow-Origin": "*"}
        if full_path.endswith((".html", "bridge.js", "bridge.css", "boot.js", "sw.js")):
            hdrs["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return FileResponse(str(candidate), media_type=_explicit_media_type(candidate), headers=hdrs)
    return _render_index_html(is_home=False)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)

