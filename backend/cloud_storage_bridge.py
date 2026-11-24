# -*- coding: utf-8 -*-
"""
Cloud-First Google Drive Storage + Minimal Local PC Runtime Bridge
==================================================================
1. Keeps ALL heavy project data (1.71 GB `al_bahith_hadith.db`, 1.49 GB `datasets_raw`,
   `exports`, `dev_archive`) exclusively on Google Drive (`حدیث سرچ` — `1c7w9HLYONrrdcvqh7uPhQdE0sAOqHmLA`,
   mounted at `G:\\My Drive\\علمی پروجیکٹ\\حدیث سرچ`).
2. Keeps `D:\\علمی معاون پرجیکٹ\\حدیث سرچ` strictly minimal (~10 MB runtime code + catalogs + tiny
   `local_runtime_cache.db`), opening Google Drive's master SQLite DB in zero-lock immutable
   read-only mode (`?mode=ro&immutable=1`) so ZERO `.db-wal` or `.db-shm` files ever touch Google Drive.
3. Automatically hot-detects Google Drive mounts and gracefully falls back to live upstream
   wire APIs (`search.hadeeth.com`, `hadeeth.com`, `api.turath.io`) if Google Drive is temporarily offline.
"""

import json
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "cloud_runtime_config.json"

_DRIVE_LETTERS = ("G", "H", "I", "J", "K", "F", "E", "D", "C", "L", "M", "N", "O", "P", "Z")
_MIN_VALID_MASTER_DB_BYTES = 100 * 1024 * 1024  # >100 MB sanity guard


def load_cloud_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _is_google_drive_path(p: Path) -> bool:
    s = str(p).lower()
    return ("my drive" in s) or ("google drive" in s) or ("shared with me" in s) or ("ملفاتي" in s)


def resolve_local_cache_db_path() -> Path:
    """
    Returns writable local SSD SQLite overlay cache path (`local_runtime_cache.db`).
    Never places writable WAL files inside a Google Drive mounted folder!
    """
    explicit = os.environ.get("ALBAHITH_LOCAL_CACHE_DB", "").strip()
    if explicit:
        p = Path(explicit)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # If the user accidentally launched from inside `G:\My Drive\...`, redirect writable cache to `D:\علمی معاون پرجیکٹ\حدیث سرچ` or LOCALAPPDATA
    if _is_google_drive_path(BASE_DIR):
        d_root = Path(r"D:\علمی معاون پرجیکٹ\حدیث سرچ\database")
        if Path("D:\\").exists():
            try:
                d_root.mkdir(parents=True, exist_ok=True)
                return d_root / "local_runtime_cache.db"
            except Exception:
                pass
        local_app = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        fallback_dir = Path(local_app) / "AlBahithHadith"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / "local_runtime_cache.db"

    local_db_dir = BASE_DIR / "database"
    local_db_dir.mkdir(parents=True, exist_ok=True)
    return local_db_dir / "local_runtime_cache.db"


def find_mounted_google_drive_folder() -> Optional[Path]:
    """Auto-discovers mounted Google Drive folder `حدیث سرچ` on Windows/macOS/Linux."""
    env_cloud = os.environ.get("ALBAHITH_CLOUD_DIR", "").strip()
    if env_cloud and Path(env_cloud).is_dir():
        return Path(env_cloud)

    cfg = load_cloud_config()
    subpaths: List[str] = cfg.get("google_drive_mount_subpaths") or [
        "My Drive\\علمی پروجیکٹ\\حدیث سرچ",
        "My Drive\\علمی معاون پرجیکٹ\\حدیث سرچ",
        "My Drive\\حدیث سرچ",
    ]

    if os.name == "nt":
        for drv in _DRIVE_LETTERS:
            drive_root = Path(f"{drv}:\\")
            if not drive_root.exists():
                continue
            for sub in subpaths:
                cand = drive_root / sub
                if cand.is_dir():
                    return cand
        user_prof = os.environ.get("USERPROFILE", "")
        if user_prof:
            for base_name in ("Google Drive", "My Drive"):
                for folder_sub in ("علمی پروجیکٹ\\حدیث سرچ", "علمی معاون پرجیکٹ\\حدیث سرچ", "حدیث سرچ"):
                    cand = Path(user_prof) / base_name / folder_sub
                    if cand.is_dir():
                        return cand

    return None


def resolve_master_db_path() -> Tuple[Optional[Path], str]:
    """
    Resolves the 1.71 GB master `al_bahith_hadith.db` in strict Cloud-First order:
    1. Explicit `ALBAHITH_HADITH_DB` environment variable (`NONE` forces 0-DB cloud API mode).
    2. Mounted Google Drive for Desktop (`G:\\My Drive\\علمی پروجیکٹ\\حدیث سرچ\\cloud_data\\database\\al_bahith_hadith.db`).
    3. Workspace `cloud_data/database/al_bahith_hadith.db` (VM / server vault).
    4. Optional local fallback `database/al_bahith_hadith.db` (only if explicitly placed offline).
    """
    env_db = os.environ.get("ALBAHITH_HADITH_DB", "").strip()
    if env_db.upper() in ("NONE", "OFFLINE_TEST", "CLOUD_API_ONLY"):
        return None, "cloud_live_api_only"
    if env_db:
        p = Path(env_db)
        if p.is_file() and p.stat().st_size >= _MIN_VALID_MASTER_DB_BYTES:
            return p, "explicit_env"

    cfg = load_cloud_config()
    rel_candidates = cfg.get("cloud_relative_db_paths") or [
        "cloud_data/database/al_bahith_hadith.db",
        "database/al_bahith_hadith.db",
    ]

    gdrive_dir = find_mounted_google_drive_folder()
    if gdrive_dir:
        for rel in rel_candidates:
            cand = gdrive_dir / rel
            try:
                if cand.is_file() and cand.stat().st_size >= _MIN_VALID_MASTER_DB_BYTES:
                    return cand, "google_drive_mount"
            except Exception:
                continue

    for rel in rel_candidates:
        cand = BASE_DIR / rel
        try:
            if cand.is_file() and cand.stat().st_size >= _MIN_VALID_MASTER_DB_BYTES:
                mode_lbl = "workspace_cloud_vault" if "cloud_data" in rel else "local_disk_db"
                return cand, mode_lbl
        except Exception:
            continue

    return None, "cloud_live_api_only"


_LOCAL_CACHE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS urdu_translation_cache (
    text_hash TEXT PRIMARY KEY,
    source_ar TEXT,
    translated_ur TEXT,
    kind TEXT DEFAULT 'matn',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS hadeeth_route_cache (
    route_key TEXT PRIMARY KEY,
    payload_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS turath_page_cache (
    cache_key TEXT PRIMARY KEY,
    payload_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS runtime_urdu_overrides (
    item_key TEXT PRIMARY KEY,
    matn_urdu TEXT DEFAULT '',
    sharh_vocalized TEXT DEFAULT '',
    sharh_urdu TEXT DEFAULT '',
    title_ur TEXT DEFAULT '',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS living_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    provenance TEXT DEFAULT 'user_explicit',
    valid_from TEXT NOT NULL,
    superseded_by INTEGER DEFAULT NULL,
    expires_at TEXT DEFAULT NULL,
    is_deleted INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_living_memory_active ON living_memory(tier, fact_key, is_deleted, superseded_by);
CREATE TABLE IF NOT EXISTS staged_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    original_text TEXT DEFAULT '',
    proposed_text TEXT NOT NULL,
    diff_summary TEXT DEFAULT '',
    risk_summary TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    provenance TEXT DEFAULT 'researcher_proposal',
    created_at TEXT NOT NULL,
    reviewed_at TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT DEFAULT 'user',
    endpoint TEXT DEFAULT '',
    details_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""

_EMPTY_FALLBACK_TEMP_SCHEMA_SQL = """
CREATE TEMP TABLE IF NOT EXISTS dorar_hadiths (
    id INTEGER PRIMARY KEY, hadith_id TEXT, matn_vocalized TEXT, matn_normalized TEXT,
    matn_urdu TEXT, matn_urdu_norm TEXT, urdu_source TEXT, rawi_id INTEGER, rawi_ar TEXT, rawi_ur TEXT,
    mohdith_id INTEGER, mohdith_ar TEXT, mohdith_ur TEXT, book_id INTEGER, book_ar TEXT, book_ur TEXT,
    shamela_book_id INTEGER, number_or_page TEXT, grade_ar TEXT, grade_ur TEXT, grade_bucket INTEGER,
    terminal_type INTEGER, takhrij_ar TEXT, takhrij_ur TEXT, sharh_id TEXT, sharh_vocalized TEXT,
    sharh_urdu TEXT, fawaid_urdu TEXT, gharib_json TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS temp.dorar_hadiths_fts USING fts5(
    hadith_id UNINDEXED, matn_normalized, matn_urdu_norm, rawi_ar, mohdith_ar, book_ar
);
CREATE TEMP TABLE IF NOT EXISTS canonical_hadiths (
    id INTEGER PRIMARY KEY, collection_slug TEXT, hadeeth_book_id INTEGER, title_ar TEXT, title_ur TEXT,
    hadith_number TEXT, arabic_number TEXT, section_id TEXT, section_num INTEGER,
    section_title_ar TEXT, section_title_ur TEXT,
    matn_vocalized TEXT, matn_normalized TEXT, matn_urdu TEXT, matn_urdu_norm TEXT,
    primary_grade_ar TEXT, primary_grade_ur TEXT, grade_class TEXT, grades_json TEXT,
    sharh_urdu TEXT, fawaid_urdu TEXT, words_meanings_json TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS temp.canonical_hadiths_fts USING fts5(
    collection_slug UNINDEXED, hadith_number UNINDEXED, matn_normalized, matn_urdu_norm, section_title_ur
);
CREATE TEMP TABLE IF NOT EXISTS hadeethenc_categories (
    id INTEGER PRIMARY KEY, parent_id INTEGER, title_ar TEXT, title_ur TEXT
);
CREATE TEMP TABLE IF NOT EXISTS hadeethenc_entries (
    id INTEGER PRIMARY KEY, category_id INTEGER, categories_json TEXT, title_ar TEXT, title_ur TEXT,
    matn_vocalized TEXT, matn_normalized TEXT, matn_urdu TEXT, attribution_ar TEXT, attribution_ur TEXT,
    grade_ar TEXT, grade_ur TEXT, takhrij_ar TEXT, explanation_ar TEXT, explanation_ur TEXT,
    hints_ar_json TEXT, hints_ur_json TEXT, words_meanings_json TEXT, references_ar TEXT
);
CREATE TEMP TABLE IF NOT EXISTS rekhta_lexicon (
    id INTEGER PRIMARY KEY, word_vocalized TEXT, word_bare TEXT, word_ar_norm TEXT, lang_code TEXT,
    root_word TEXT, root_letters TEXT, wazn TEXT, pos_tag TEXT, plural_form TEXT,
    meaning_ur TEXT, details_ur TEXT, quran_freq INTEGER, example_ar TEXT, source_dict TEXT
);
CREATE TEMP TABLE IF NOT EXISTS narrators_encyclopedia (
    id INTEGER PRIMARY KEY, narrator_key TEXT, name_ar TEXT, full_name_ar TEXT, name_bare TEXT, name_ur TEXT,
    kunya_ar TEXT, tabaqa TEXT, rank_ar TEXT, rank_ur TEXT, rank_class TEXT, death_hijri INTEGER, birth_death TEXT,
    teachers_json TEXT, students_json TEXT, jarh_tadil_json TEXT, evaluations_json TEXT, summary_json TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS temp.narrators_fts USING fts5(
    narrator_id UNINDEXED, name_bare, name_ur, rank_ar
);
CREATE TEMP TABLE IF NOT EXISTS turath_categories (
    id INTEGER PRIMARY KEY, name_ar TEXT, name_ur TEXT, book_count INTEGER
);
CREATE TEMP TABLE IF NOT EXISTS turath_authors (
    id INTEGER PRIMARY KEY, name_ar TEXT, name_ur TEXT, death_hijri INTEGER, bio_ar TEXT, bio_ur TEXT, book_count INTEGER
);
CREATE TEMP TABLE IF NOT EXISTS turath_books (
    id INTEGER PRIMARY KEY, name_ar TEXT, name_bare TEXT, name_ur TEXT, cat_id INTEGER, cat_name_ar TEXT,
    author_id INTEGER, author_ar TEXT, author_name_ar TEXT, author_ur TEXT, death_hijri INTEGER, author_death_hijri INTEGER,
    page_count INTEGER, volume_count INTEGER, printed INTEGER, has_pdf INTEGER,
    info_ar TEXT, info_card TEXT, pdf_links_json TEXT, pdf_urls_json TEXT, epub_links_json TEXT, epub_url TEXT
);
CREATE TEMP TABLE IF NOT EXISTS dorar_articles (
    id INTEGER PRIMARY KEY, article_id TEXT, url TEXT, title_ar TEXT, title_ur TEXT,
    title_bare TEXT, breadcrumb_path TEXT, content_vocalized TEXT, content_bare TEXT,
    content_urdu TEXT, footnotes_json TEXT, word_count INTEGER, char_count INTEGER
);
CREATE VIRTUAL TABLE IF NOT EXISTS temp.dorar_articles_fts USING fts5(
    article_row_id UNINDEXED, title_bare, content_bare
);
CREATE TEMP TABLE IF NOT EXISTS filter_muhaddiths (
    id INTEGER PRIMARY KEY, name_ar TEXT, name_ur TEXT, full_name_ar TEXT, death_hijri INTEGER,
    hadith_count INTEGER, bio_ar TEXT, bio_ur TEXT
);
CREATE TEMP TABLE IF NOT EXISTS filter_books (
    id INTEGER PRIMARY KEY, name_ar TEXT, name_ur TEXT, author_id INTEGER, shamela_id INTEGER,
    hadeeth_collection_id INTEGER, hadith_count INTEGER, description_ur TEXT
);
CREATE TEMP TABLE IF NOT EXISTS filter_rawis (
    id INTEGER PRIMARY KEY, name_ar TEXT, name_ur TEXT, tabaqa TEXT, hadith_count INTEGER
);
"""


def _init_local_cache_file(local_cache_path: Path) -> None:
    conn = sqlite3.connect(str(local_cache_path), timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.executescript(_LOCAL_CACHE_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


class DualTierDBPool:
    """
    Thread-local SQLite pool connecting:
    - `main` -> Immutable Read-Only Master DB on Google Drive (`?mode=ro&immutable=1`, zero WAL/SHM/locks)
    - `local_cache` -> Fast Local SSD Writable Cache DB (`local_runtime_cache.db`)
    Automatically hot-reconnects if Google Drive mounts after server startup!
    """

    def __init__(self) -> None:
        self._tls = threading.local()
        self.local_cache_path = resolve_local_cache_db_path()
        _init_local_cache_file(self.local_cache_path)
        self.master_path, self.storage_mode = resolve_master_db_path()
        self._last_probe_ts = time.monotonic()
        self._epoch = 1
        self._lock = threading.Lock()

    def refresh_master_resolution(self) -> Tuple[Optional[Path], str]:
        with self._lock:
            new_path, new_mode = resolve_master_db_path()
            if new_path != self.master_path or new_mode != self.storage_mode:
                self.master_path = new_path
                self.storage_mode = new_mode
                self._epoch += 1
            self._last_probe_ts = time.monotonic()
            return self.master_path, self.storage_mode

    @property
    def has_master_db(self) -> bool:
        return self.master_path is not None and self.master_path.exists()

    def get(self) -> sqlite3.Connection:
        # Periodically probe for newly mounted Google Drive if running in 0-DB cloud API mode
        if self.master_path is None and (time.monotonic() - self._last_probe_ts) > 5.0:
            self.refresh_master_resolution()

        conn: Optional[sqlite3.Connection] = getattr(self._tls, "conn", None)
        conn_epoch: int = getattr(self._tls, "epoch", 0)
        if conn is not None and conn_epoch == self._epoch:
            return conn

        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

        master = self.master_path
        if master is not None and master.exists():
            uri = master.resolve().as_uri() + "?mode=ro&immutable=1"
            new_conn = sqlite3.connect(uri, uri=True, check_same_thread=False, timeout=30.0)
            new_conn.row_factory = sqlite3.Row
            new_conn.execute("PRAGMA temp_store = MEMORY;")
            new_conn.execute("PRAGMA cache_size = -131072;")  # 128 MB RAM cache
            new_conn.execute("PRAGMA mmap_size = 0;")          # Safe on Windows Google DriveFS virtual drives
            new_conn.execute("ATTACH DATABASE ? AS local_cache;", (str(self.local_cache_path),))
        else:
            new_conn = sqlite3.connect(str(self.local_cache_path), check_same_thread=False, timeout=30.0)
            new_conn.row_factory = sqlite3.Row
            new_conn.execute("PRAGMA journal_mode = WAL;")
            new_conn.execute("PRAGMA synchronous = NORMAL;")
            new_conn.execute("PRAGMA temp_store = MEMORY;")
            new_conn.execute("ATTACH DATABASE ? AS local_cache;", (str(self.local_cache_path),))
            new_conn.executescript(_EMPTY_FALLBACK_TEMP_SCHEMA_SQL)

        self._tls.conn = new_conn
        self._tls.epoch = self._epoch
        return new_conn


# ---------------------------------------------------------------------------
# Unified Dual-Tier Cache & Runtime Override Helpers
# ---------------------------------------------------------------------------
def get_cached_translation(conn: sqlite3.Connection, text_hash: str) -> str:
    for schema in ("local_cache", "main"):
        try:
            row = conn.execute(
                f"SELECT translated_ur FROM {schema}.urdu_translation_cache WHERE text_hash = ?",
                (text_hash,),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            continue
    return ""


def save_cached_translation(
    conn: sqlite3.Connection, text_hash: str, source_ar: str, translated_ur: str, kind: str = "matn"
) -> None:
    try:
        conn.execute(
            "INSERT OR REPLACE INTO local_cache.urdu_translation_cache(text_hash, source_ar, translated_ur, kind) VALUES (?, ?, ?, ?)",
            (text_hash, source_ar, translated_ur, kind),
        )
        conn.commit()
    except Exception:
        pass


def get_cached_route(conn: sqlite3.Connection, route_key: str) -> Optional[str]:
    for schema in ("local_cache", "main"):
        try:
            row = conn.execute(
                f"SELECT payload_json FROM {schema}.hadeeth_route_cache WHERE route_key = ?",
                (route_key,),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            continue
    return None


def save_cached_route(conn: sqlite3.Connection, route_key: str, payload_json: str) -> None:
    try:
        conn.execute(
            "INSERT OR REPLACE INTO local_cache.hadeeth_route_cache(route_key, payload_json) VALUES (?, ?)",
            (route_key, payload_json),
        )
        conn.commit()
    except Exception:
        pass


def get_cached_turath_page(conn: sqlite3.Connection, cache_key: str) -> Optional[str]:
    for schema in ("local_cache", "main"):
        try:
            row = conn.execute(
                f"SELECT payload_json FROM {schema}.turath_page_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            continue
    return None


def save_cached_turath_page(conn: sqlite3.Connection, cache_key: str, payload_json: str) -> None:
    try:
        conn.execute(
            "INSERT OR REPLACE INTO local_cache.turath_page_cache(cache_key, payload_json) VALUES (?, ?)",
            (cache_key, payload_json),
        )
        conn.commit()
    except Exception:
        pass


def get_urdu_override(conn: sqlite3.Connection, item_key: str) -> Optional[Dict[str, str]]:
    try:
        row = conn.execute(
            "SELECT matn_urdu, sharh_vocalized, sharh_urdu, title_ur FROM local_cache.runtime_urdu_overrides WHERE item_key = ?",
            (item_key,),
        ).fetchone()
        if row:
            return {
                "matn_urdu": row["matn_urdu"] or "",
                "sharh_vocalized": row["sharh_vocalized"] or "",
                "sharh_urdu": row["sharh_urdu"] or "",
                "title_ur": row["title_ur"] or "",
            }
    except Exception:
        pass
    return None


def save_urdu_override(
    conn: sqlite3.Connection,
    item_key: str,
    matn_urdu: str = "",
    sharh_vocalized: str = "",
    sharh_urdu: str = "",
    title_ur: str = "",
) -> None:
    try:
        existing = get_urdu_override(conn, item_key) or {}
        conn.execute(
            """
            INSERT OR REPLACE INTO local_cache.runtime_urdu_overrides(
                item_key, matn_urdu, sharh_vocalized, sharh_urdu, title_ur, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                item_key,
                matn_urdu or existing.get("matn_urdu", ""),
                sharh_vocalized or existing.get("sharh_vocalized", ""),
                sharh_urdu or existing.get("sharh_urdu", ""),
                title_ur or existing.get("title_ur", ""),
            ),
        )
        conn.commit()
    except Exception:
        pass


def compute_local_runtime_footprint_mb(root_dir: Path = BASE_DIR) -> float:
    """Calculates size of strictly local PC runtime files (excluding `.venv` and `cloud_data`)."""
    total = 0
    skip_top = {".venv", "cloud_data", "datasets_raw", ".git", "node_modules", "__pycache__", ".antigravity"}
    for entry in root_dir.iterdir():
        if entry.name in skip_top:
            continue
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            for sub in entry.rglob("*"):
                if sub.is_file() and "__pycache__" not in sub.parts:
                    if sub.name.startswith("al_bahith_hadith.db"):
                        continue
                    total += sub.stat().st_size
    return round(total / (1024 * 1024), 2)


def get_storage_diagnostics(pool: DualTierDBPool) -> Dict[str, Any]:
    cfg = load_cloud_config()
    master_mb = round(pool.master_path.stat().st_size / (1024 * 1024), 2) if pool.has_master_db and pool.master_path else 0.0
    cache_mb = round(pool.local_cache_path.stat().st_size / (1024 * 1024), 3) if pool.local_cache_path.exists() else 0.0
    return {
        "architecture": "google_drive_master_vault_plus_minimal_local_pc_runtime",
        "storage_mode": pool.storage_mode,
        "master_db_connected": pool.has_master_db,
        "master_db_path": str(pool.master_path) if pool.master_path else None,
        "master_db_size_mb": master_mb,
        "master_db_lock_free_immutable": True,
        "local_runtime_dir": str(BASE_DIR),
        "local_pc_target_dir": cfg.get("local_pc_target_dir", r"D:\علمی معاون پرجیکٹ\حدیث سرچ"),
        "local_runtime_footprint_mb": compute_local_runtime_footprint_mb(BASE_DIR),
        "local_cache_db_path": str(pool.local_cache_path),
        "local_cache_size_mb": cache_mb,
        "google_drive_folder_id": cfg.get("google_drive_folder_id", "1c7w9HLYONrrdcvqh7uPhQdE0sAOqHmLA"),
    }
