# -*- coding: utf-8 -*-
"""
Zero-Server GitHub Pages Static Portal & Compressed Shard Builder
=================================================================
Builds two clean artifacts from `/home/antigravity/hadith-search-urdu`:
1. `/tmp/gh_main_repo`: Clean ~16.5 MB source repository (`main` branch) — zero GB bloat!
2. `/tmp/gh_pages_site`: Complete serverless static portal (`gh-pages` branch) served at
   `https://abusufyaan93.github.io/al-bahith-hadith-urdu/` with:
   - Subpath-safe SvelteKit 2 + Salafi Urdu Bridge + SPA `404.html` router
   - 48,911 Bilingual Vocalized Arabic + Salafi Urdu Hadiths (`2,220` HadeethEnc + `46,691` Dorar)
   - 32-bucket Delta-Encoded Inverted Search Index (instant `<80ms` Urdu & Arabic search)
   - 32-bucket Hadith Sharh & Fawaid Shards (`HadeethEnc` + `Dorar`)
   - 64-bucket Complete 283,601-word Rekhta & Qari Urdu-Arabic Lexicon
   - Pre-compiled Encyclopedia `routes.bin` (`/(site)/*` SvelteKit envelopes)
"""

import argparse
import gzip
import json
import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.arabic_urdu_sanitizer import URDU_TO_ARABIC_HADITH_TERMS
from backend.cloud_storage_bridge import resolve_master_db_path
from pipeline.books_catalog import HADEETH_33_COLLECTIONS
from pipeline.sveltekit_bridge import decode_sveltekit_devalue, enrich_encyclopedia_payload_urdu
from tools.setup_local_pc_minimal import (
    ALLOWED_BACKEND_PY,
    ALLOWED_PIPELINE_PY,
    ALLOWED_ROOT_FILES,
    ALLOWED_TOOLS_PY,
)

REPO_SUBPATH = "/al-bahith-hadith-urdu"
SHARD_SIZE = 2048

TASHKEEL_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
NON_AR_RE = re.compile(r"[^\u0621-\u064A0-9\s]")
NON_UR_RE = re.compile(r"[^\u0600-\u06FF0-9\s]")

STOP_WORDS: Set[str] = {
    "من", "في", "على", "علي", "الى", "إلى", "عن", "ان", "أن", "إن", "لا", "ما", "هو", "هي", "هم",
    "هذا", "هذه", "ذلك", "التي", "الذي", "كان", "كانت", "قال", "قالت", "رسول", "النبي", "الله",
    "حدثنا", "اخبرنا", "سمعت", "روایت", "ہے", "ہیں", "تھا", "تھی", "تھے", "کہ", "فرمایا", "سے",
    "نے", "کی", "کا", "کے", "میں", "پر", "کو", "اور", "بھی", "ہو", "کر", "جو", "اس", "ان", "تو", "یہ",
}


def fnv1a32_utf16(s: str) -> int:
    """Bit-identical to JavaScript `fnv1a32(str)` using UTF-16LE code units."""
    b = s.encode("utf-16-le")
    h = 0x811C9DC5
    for i in range(0, len(b), 2):
        cu = b[i] | (b[i + 1] << 8)
        h ^= cu
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def norm_ar(s: str) -> str:
    if not s:
        return ""
    s = TASHKEEL_RE.sub("", s)
    s = (
        s.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
        .replace("ی", "ي")
        .replace("ے", "ي")
        .replace("ک", "ك")
        .replace("ہ", "ه")
        .replace("ۀ", "ه")
        .replace("ۃ", "ه")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
    )
    s = NON_AR_RE.sub(" ", s)
    return " ".join(s.split())


def norm_ur(s: str) -> str:
    if not s:
        return ""
    s = TASHKEEL_RE.sub("", s)
    s = (
        s.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
        .replace("ك", "ک")
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ة", "ہ")
        .replace("ه", "ہ")
        .replace("ۀ", "ہ")
        .replace("ۃ", "ہ")
        .replace("ؤ", "و")
        .replace("ئ", "ی")
    )
    s = NON_UR_RE.sub(" ", s)
    return " ".join(s.split())


def write_gzip_json(path: Path, obj: Any) -> int:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    gz = gzip.compress(raw, compresslevel=6)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gz)
    return len(gz)


def delta_encode(sorted_gids: List[int]) -> List[int]:
    if not sorted_gids:
        return []
    out = [sorted_gids[0]]
    prev = sorted_gids[0]
    for g in sorted_gids[1:]:
        if g != prev:
            out.append(g - prev)
            prev = g
    return out


def rewrite_subpath_assets(text: str, sub: str) -> str:
    if not sub:
        return text
    for prefix in ("/assets/", "/fonts/", "/app.png", "/manifest.json"):
        # Avoid double-prefixing if already prefixed
        placeholder = f"__AB_PRE_{hash(prefix)}__"
        text = text.replace(sub + prefix, placeholder)
        text = text.replace(f'"{prefix}', f'"{sub}{prefix}')
        text = text.replace(f"'{prefix}", f"'{sub}{prefix}")
        text = text.replace(f"`{prefix}", f"`{sub}{prefix}")
        text = text.replace(placeholder, sub + prefix)
    return text


def build_main_source_tree(out_main: Path) -> None:
    if out_main.exists():
        shutil.rmtree(out_main)
    out_main.mkdir(parents=True, exist_ok=True)

    for f in ALLOWED_ROOT_FILES:
        src = BASE_DIR / f
        if src.is_file():
            shutil.copy2(src, out_main / f)

    for f in ALLOWED_BACKEND_PY:
        src = BASE_DIR / "backend" / f
        if src.is_file():
            (out_main / "backend").mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_main / "backend" / f)

    src_static = BASE_DIR / "backend" / "static"
    dst_static = out_main / "backend" / "static"
    for item in src_static.rglob("*"):
        rel = item.relative_to(src_static)
        if "_app" in rel.parts or "__pycache__" in rel.parts or item.name.endswith(".orig"):
            continue
        if item.is_file():
            (dst_static / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst_static / rel)

    for f in ALLOWED_PIPELINE_PY:
        src = BASE_DIR / "pipeline" / f
        if src.is_file():
            (out_main / "pipeline").mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_main / "pipeline" / f)

    for f in list(ALLOWED_TOOLS_PY) + ["build_github_pages.py"]:
        src = BASE_DIR / "tools" / f
        if src.is_file():
            (out_main / "tools").mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_main / "tools" / f)

    cat_rel = Path("database") / "catalogs" / "hadeeth_home_catalogs.json"
    if (BASE_DIR / cat_rel).is_file():
        (out_main / cat_rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE_DIR / cat_rel, out_main / cat_rel)

    for extra_dir in (".agents", "scripts", "evals"):
        src_d = BASE_DIR / extra_dir
        if src_d.is_dir():
            shutil.copytree(
                src_d,
                out_main / extra_dir,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                dirs_exist_ok=True,
            )

    gitignore = (
        ".venv/\n"
        "__pycache__/\n"
        "*.pyc\n"
        "cloud_data/\n"
        "datasets_raw/\n"
        "exports/\n"
        "database/*.db\n"
        "database/*.db-*\n"
    )
    (out_main / ".gitignore").write_text(gitignore, encoding="utf-8")


def build_gh_pages_portal(out_pages: Path, sub: str = REPO_SUBPATH) -> Dict[str, Any]:
    if out_pages.exists():
        shutil.rmtree(out_pages)
    out_pages.mkdir(parents=True, exist_ok=True)

    # 1. Copy static UI tree and rewrite root-relative asset paths for `/al-bahith-hadith-urdu`
    src_static = BASE_DIR / "backend" / "static"
    for item in src_static.rglob("*"):
        rel = item.relative_to(src_static)
        if "_app" in rel.parts or "__pycache__" in rel.parts or item.name.endswith(".orig"):
            continue
        if item.is_file():
            dst = out_pages / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if item.suffix in (".html", ".js", ".webmanifest", ".json"):
                txt = item.read_text(encoding="utf-8")
                if item.name == "index.html":
                    route_css = (
                        '<link href="/assets/sk/immutable/assets/4.9HLJUNqK.css" rel="stylesheet" />\n'
                        '    <link href="/assets/sk/immutable/assets/App.DiaWME78.css" rel="stylesheet" />'
                    )
                    txt = txt.replace("<!-- ROUTE_CSS_SLOT -->", route_css)
                txt = rewrite_subpath_assets(txt, sub)
                dst.write_text(txt, encoding="utf-8")
            else:
                shutil.copy2(item, dst)

    # Create `.nojekyll` and SPA `404.html` redirector
    (out_pages / ".nojekyll").write_text("", encoding="utf-8")
    spa_404 = f"""<!doctype html>
<html lang="ar" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <title>الباحث الحديثي — اردو، عربي</title>
    <script>
      (function () {{
        try {{
          var full = window.location.pathname + window.location.search + window.location.hash;
          sessionStorage.setItem("__ab_spa_redirect__", full);
        }} catch (_) {{}}
        window.location.replace("{sub}/");
      }})();
    </script>
  </head>
  <body></body>
</html>
"""
    (out_pages / "404.html").write_text(spa_404, encoding="utf-8")

    # 2. Connect to Master SQLite Vault (`cloud_data/database/al_bahith_hadith.db`) to build shards
    db_path, _db_src = resolve_master_db_path()
    if not db_path:
        raise RuntimeError("Master SQLite database not found in cloud_data/database/al_bahith_hadith.db")

    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row

    static_db_dir = out_pages / "static_db"
    static_db_dir.mkdir(parents=True, exist_ok=True)
    total_shard_bytes = 0

    print("[1/5] Building 48,911 Bilingual Hadith Shards + 32-Bucket Inverted Index + 32-Bucket Sharh...")
    fmeta: List[List[int]] = []
    all_records: List[List[Any]] = []
    inv_buckets: List[Dict[str, List[int]]] = [defaultdict(list) for _ in range(32)]
    sharh_buckets: List[Dict[str, List[str]]] = [{} for _ in range(32)]
    gharib_list: List[Dict[str, str]] = []
    seen_gharib: Set[str] = set()

    def _index_hadith_tokens(gid: int, ar_text: str, ur_text: str) -> None:
        ar_tokens = {w for w in norm_ar(ar_text).split() if len(w) >= 2 and w not in STOP_WORDS}
        ur_tokens = {w for w in norm_ur(ur_text).split() if len(w) >= 2 and w not in STOP_WORDS}
        for w in ar_tokens:
            key = "a:" + w
            inv_buckets[fnv1a32_utf16(key) & 31][key].append(gid)
            if w.startswith("ال") and len(w) >= 4:
                bare = "a:" + w[2:]
                inv_buckets[fnv1a32_utf16(bare) & 31][bare].append(gid)
        for w in ur_tokens:
            key = "u:" + w
            inv_buckets[fnv1a32_utf16(key) & 31][key].append(gid)

    # A. First 2,220 HadeethEnc Explained Hadiths (highest pedagogical priority + rich Urdu Sharh & Fawaid)
    for r in conn.execute(
        """
        SELECT id, matn_vocalized, matn_urdu, attribution_ar, attribution_ur,
               grade_ar, grade_ur, explanation_ar, explanation_ur, hints_ur_json, words_meanings_json, takhrij_ar
        FROM hadeethenc_entries
        ORDER BY id ASC
        """
    ):
        gid = len(all_records)
        sid = f"he_{r['id']}"
        fawaid_ur = ""
        try:
            hints = json.loads(r["hints_ur_json"] or "[]")
            if isinstance(hints, list) and hints:
                fawaid_ur = "\n".join(f"• {h}" for h in hints if h)
        except Exception:
            pass
        try:
            wm = json.loads(r["words_meanings_json"] or "[]")
            if isinstance(wm, list):
                for item in wm:
                    if isinstance(item, dict) and item.get("word") and len(gharib_list) < 1200:
                        wb = norm_ar(str(item["word"])).replace(" ", "")
                        if wb and wb not in seen_gharib:
                            seen_gharib.add(wb)
                            gharib_list.append({
                                "w": str(item["word"]),
                                "wb": wb,
                                "ar": str(item.get("meaning") or ""),
                                "ur": str(item.get("meaning_ur") or item.get("meaning") or ""),
                            })
        except Exception:
            pass

        sharh_ar = str(r["explanation_ar"] or "").strip()
        sharh_ur = str(r["explanation_ur"] or "").strip()
        has_sharh = bool(sharh_ar or sharh_ur)
        if has_sharh:
            sharh_buckets[fnv1a32_utf16(sid) & 31][sid] = [sharh_ar, sharh_ur, fawaid_ur]

        grade_ar = str(r["grade_ar"] or "صحيح").strip()
        grade_ur = str(r["grade_ur"] or "صحیح").strip()
        is_weak = any(k in grade_ar for k in ("ضعيف", "موضوع", "منكر", "باطل", "لا يصح"))
        g_bucket = 3 if is_weak else 1
        flags = 0 | (8 if has_sharh else 0) | 32  # terminal=0, hasSharh, isHadeethEnc

        fmeta.append([0, 0, 0, g_bucket, flags])
        all_records.append([
            sid,
            str(r["matn_vocalized"] or ""),
            str(r["matn_urdu"] or ""),
            "",
            str(r["attribution_ar"] or "موسوعة الأحاديث النبوية"),
            str(r["attribution_ar"] or "موسوعة الأحاديث النبوية"),
            str(r["id"]),
            grade_ar,
            grade_ur,
            "bad" if is_weak else "ok",
            sid if has_sharh else "",
            str(r["takhrij_ar"] or ""),
        ])
        _index_hadith_tokens(gid, str(r["matn_vocalized"] or ""), str(r["matn_urdu"] or ""))

    # B. All 46,691 Dorar Hadiths linked with Salafi Urdu translations + exact Dorar filter IDs!
    kept_dorar_sharhs = 0
    for r in conn.execute(
        """
        SELECT hadith_id, matn_vocalized, matn_urdu, rawi_id, rawi_ar, mohdith_id, mohdith_ar,
               book_id, book_ar, number_or_page, grade_ar, grade_ur, grade_bucket, terminal_type,
               takhrij_ar, sharh_id, sharh_vocalized, sharh_urdu, fawaid_urdu
        FROM dorar_hadiths
        WHERE matn_urdu IS NOT NULL AND matn_urdu != ''
        ORDER BY CASE WHEN sharh_urdu IS NOT NULL AND sharh_urdu != '' THEN 0 ELSE 1 END, id ASC
        """
    ):
        gid = len(all_records)
        rawi_id = int(r["rawi_id"] or 0)
        moh_id = int(r["mohdith_id"] or 0)
        book_id = int(r["book_id"] or 0)
        g_bucket = int(r["grade_bucket"] or 1)
        t_str = str(r["terminal_type"] or "0").strip()
        t_int = int(t_str) if t_str.isdigit() and int(t_str) <= 7 else 0

        raw_sid = str(r["sharh_id"] or "").strip()
        sh_ar = str(r["sharh_vocalized"] or "").strip()
        sh_ur = str(r["sharh_urdu"] or "").strip()
        fw_ur = str(r["fawaid_urdu"] or "").strip()
        include_sharh = False
        if raw_sid and (sh_ur or (sh_ar and kept_dorar_sharhs < 12000)):
            sharh_buckets[fnv1a32_utf16(raw_sid) & 31][raw_sid] = [sh_ar[:3500], sh_ur[:3500], fw_ur[:1500]]
            kept_dorar_sharhs += 1
            include_sharh = True

        is_kutub = book_id in (6216, 3088, 6267, 13509, 977, 13508, 13561, 13560)
        flags = (t_int & 7) | (8 if include_sharh else 0) | (16 if is_kutub else 0)
        fmeta.append([rawi_id, moh_id, book_id, g_bucket, flags])

        rawy_wire: Any = rawi_id if rawi_id > 0 else str(r["rawi_ar"] or "")
        moh_wire: Any = moh_id if moh_id > 0 else str(r["mohdith_ar"] or "")
        src_wire: str = str(book_id) if book_id > 0 else str(r["book_ar"] or "")
        grade_class = "bad" if g_bucket in (3, 4) else "ok"

        all_records.append([
            str(r["hadith_id"] or gid),
            str(r["matn_vocalized"] or ""),
            str(r["matn_urdu"] or ""),
            rawy_wire,
            moh_wire,
            src_wire,
            str(r["number_or_page"] or ""),
            str(r["grade_ar"] or ""),
            str(r["grade_ur"] or ""),
            grade_class,
            raw_sid if include_sharh else "",
            str(r["takhrij_ar"] or ""),
        ])
        _index_hadith_tokens(gid, str(r["matn_vocalized"] or ""), str(r["matn_urdu"] or ""))

    total_hadiths = len(all_records)
    num_hd_shards = (total_hadiths + SHARD_SIZE - 1) // SHARD_SIZE
    for s_idx in range(num_hd_shards):
        chunk = all_records[s_idx * SHARD_SIZE : (s_idx + 1) * SHARD_SIZE]
        total_shard_bytes += write_gzip_json(static_db_dir / f"hd_{s_idx:02d}.bin", chunk)

    total_shard_bytes += write_gzip_json(
        static_db_dir / "meta.bin",
        {
            "shard_size": SHARD_SIZE,
            "total_hadiths": total_hadiths,
            "urdu_to_ar": URDU_TO_ARABIC_HADITH_TERMS,
            "gharib": gharib_list,
        },
    )
    total_shard_bytes += write_gzip_json(static_db_dir / "fmeta.bin", fmeta)

    print("[2/5] Writing 32 Inverted Search Index Shards & 32 Sharh Shards...")
    for b in range(32):
        encoded_bucket = {tok: delta_encode(sorted(gids)) for tok, gids in inv_buckets[b].items()}
        total_shard_bytes += write_gzip_json(static_db_dir / f"idx_{b:02d}.bin", encoded_bucket)
        total_shard_bytes += write_gzip_json(static_db_dir / f"sh_{b:02d}.bin", sharh_buckets[b])

    print("[3/5] Building 64 Rekhta & Qari 283,601-Word Lexicon Shards...")
    lx_buckets: List[List[List[str]]] = [[] for _ in range(64)]
    for r in conn.execute("SELECT word_urdu, word_bare, word_ar_norm, root_letters, meanings_ur FROM rekhta_lexicon"):
        wb = norm_ur(str(r["word_bare"] or r["word_urdu"] or "")).replace(" ", "")
        wa = norm_ar(str(r["word_ar_norm"] or r["word_bare"] or "")).replace(" ", "")
        row_compact = [
            str(r["word_urdu"] or ""),
            wb,
            wa,
            str(r["root_letters"] or ""),
            str(r["meanings_ur"] or ""),
        ]
        b_Set: Set[int] = set()
        if len(wb) >= 2:
            b_Set.add(fnv1a32_utf16(wb[:2]) & 63)
        if len(wa) >= 2:
            b_Set.add(fnv1a32_utf16(wa[:2]) & 63)
        if not b_Set:
            b_Set.add(0)
        for b in b_Set:
            lx_buckets[b].append(row_compact)

    for b in range(64):
        total_shard_bytes += write_gzip_json(static_db_dir / f"lx_{b:02d}.bin", lx_buckets[b])

    print("[4/5] Building Enriched Encyclopedia `routes.bin` Bundle...")
    routes_map: Dict[str, Any] = {}
    for r in conn.execute("SELECT route_key, payload_json FROM hadeeth_route_cache"):
        rk = str(r["route_key"])
        raw_obj = json.loads(r["payload_json"])
        # Some rows store raw `{"type":"data","nodes":[...]}` envelope; decode if needed, then enrich with Salafi Urdu!
        if isinstance(raw_obj, dict) and raw_obj.get("type") == "data" and "nodes" in raw_obj:
            leaf_obj = decode_sveltekit_devalue(raw_obj)
        else:
            leaf_obj = raw_obj
        clean_route = rk.split("?")[0]
        enriched = enrich_encyclopedia_payload_urdu(clean_route, leaf_obj, conn, translate_live=False)
        routes_map[rk] = enriched

    # Ensure `/collections` has all 33 collections Urdu titles attached
    if "/collections" not in routes_map:
        routes_map["/collections"] = {"collections": list(HADEETH_33_COLLECTIONS.values())}

    total_shard_bytes += write_gzip_json(static_db_dir / "routes.bin", routes_map)
    conn.close()

    total_site_bytes = sum(f.stat().st_size for f in out_pages.rglob("*") if f.is_file())
    stats = {
        "total_hadiths": total_hadiths,
        "hadith_shards": num_hd_shards,
        "dorar_sharhs_included": kept_dorar_sharhs,
        "cached_routes": len(routes_map),
        "static_db_mb": round(total_shard_bytes / (1024 * 1024), 2),
        "total_portal_mb": round(total_site_bytes / (1024 * 1024), 2),
    }
    print(f"[5/5] GitHub Pages Portal Ready: {json.dumps(stats, ensure_ascii=False)}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GitHub main & gh-pages branches for الباحث الحديثي")
    parser.add_argument("--main-out", default="/tmp/gh_main_repo")
    parser.add_argument("--pages-out", default="/tmp/gh_pages_site")
    parser.add_argument("--subpath", default=REPO_SUBPATH)
    args = parser.parse_args()

    build_main_source_tree(Path(args.main_out))
    build_gh_pages_portal(Path(args.pages_out), sub=args.subpath)


if __name__ == "__main__":
    main()
