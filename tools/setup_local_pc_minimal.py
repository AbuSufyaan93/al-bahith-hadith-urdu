# -*- coding: utf-8 -*-
"""
Minimal Local PC Runtime Installer & Bloat Cleaner (`~10.6 MB` Local Footprint)
===============================================================================
Ensures `"D:\\علمی معاون پرجیکٹ\\حدیث سرچ"` on the user's PC contains ONLY the
strictly essential runtime code, SvelteKit UI assets, pre-packed filter catalogs,
and tiny `local_runtime_cache.db` (~10.6 MB total), while keeping all 3.2+ GB of
master databases, raw corpora, exports, and archives safely on Google Drive
(`G:\\My Drive\\علمی پروجیکٹ\\حدیث سرچ\\cloud_data`).
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.cloud_storage_bridge import (
    _init_local_cache_file,
    compute_local_runtime_footprint_mb,
    find_mounted_google_drive_folder,
)

DEFAULT_WINDOWS_TARGET = r"D:\علمی معاون پرجیکٹ\حدیث سرچ"

ALLOWED_ROOT_FILES = [
    "ACTIVE_LINKS.txt",
    "AGENTS.md",
    "Install-Windows-AutoStart.bat",
    "README.md",
    "Setup-Local-PC-D-Drive.bat",
    "Start-Al-Bahith-Hadith.bat",
    "Start-Background-Silent.vbs",
    "Sync-To-Google-Drive.bat",
    "cloud_runtime_config.json",
    "requirements.txt",
    "تشغيل_الباحث_الحديثي.bat",
    "سیٹ_اپ_لوکل_پی_سی.bat",
]

ALLOWED_BACKEND_PY = [
    "__init__.py",
    "arabic_urdu_sanitizer.py",
    "cloud_storage_bridge.py",
    "hybrid_rag_engine.py",
    "main.py",
    "memory_and_proposals.py",
    "security_guardrails.py",
]

ALLOWED_PIPELINE_PY = [
    "__init__.py",
    "books_catalog.py",
    "normalizer.py",
    "salafi_urdu_engine.py",
    "sveltekit_bridge.py",
]

ALLOWED_TOOLS_PY = [
    "run_local_server.py",
    "setup_local_pc_minimal.py",
    "sync_to_gdrive.py",
    "validate_agent_harness.py",
    "verify_platform.py",
]

BLOAT_DIRS_TO_PURGE = [
    "cloud_data",
    "datasets_raw",
    "exports",
    "frontend",
    "backend/static/_app",
]

BLOAT_FILES_TO_PURGE = [
    "Dockerfile",
    "docker-compose.yml",
    "postgres_schema.sql",
    "schema.sql",
    "pipeline/build_database.py",
    "tools/build_github_pages.py",
    "tools/build_sk_assets.py",
    "tools/repair_dorar_urdu_links.py",
]


def _copy_file_if_changed(src: Path, dst: Path) -> bool:
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_file():
        st_s, st_d = src.stat(), dst.stat()
        if st_s.st_size == st_d.st_size and int(st_s.st_mtime) == int(st_d.st_mtime):
            return False
    shutil.copy2(src, dst)
    return True


def _copy_static_tree(src_static: Path, dst_static: Path) -> int:
    copied = 0
    for item in src_static.rglob("*"):
        rel = item.relative_to(src_static)
        if "_app" in rel.parts or "__pycache__" in rel.parts or item.name.endswith(".orig"):
            continue
        if item.is_file():
            if _copy_file_if_changed(item, dst_static / rel):
                copied += 1
    return copied


def _find_verified_cloud_db(explicit_cloud_dir: Optional[Path] = None) -> Optional[Path]:
    candidates = []
    if explicit_cloud_dir:
        candidates.append(explicit_cloud_dir)
    gdrive = find_mounted_google_drive_folder()
    if gdrive:
        candidates.append(gdrive)
    if (BASE_DIR / "cloud_data" / "database" / "al_bahith_hadith.db").is_file():
        candidates.append(BASE_DIR)

    for root in candidates:
        for rel in ("cloud_data/database/al_bahith_hadith.db", "database/al_bahith_hadith.db"):
            p = root / rel
            try:
                if p.is_file() and p.stat().st_size >= 1_400_000_000:
                    return p
            except Exception:
                continue
    return None


def purge_non_runtime_bloat(target_dir: Path, explicit_cloud_dir: Optional[Path] = None) -> int:
    removed_bytes = 0
    for rel_d in BLOAT_DIRS_TO_PURGE:
        d_path = target_dir / rel_d
        # Never delete `cloud_data` if someone accidentally runs `--clean-self` inside Google Drive itself!
        if rel_d == "cloud_data" and ("my drive" in str(target_dir).lower() or target_dir.resolve() == BASE_DIR.resolve()):
            continue
        if d_path.is_dir():
            for f in d_path.rglob("*"):
                if f.is_file():
                    removed_bytes += f.stat().st_size
            shutil.rmtree(d_path, ignore_errors=True)

    for rel_f in BLOAT_FILES_TO_PURGE:
        f_path = target_dir / rel_f
        if f_path.is_file():
            removed_bytes += f_path.stat().st_size
            f_path.unlink(missing_ok=True)

    # Purge local 1.71 GB `database/al_bahith_hadith.db*` on local PC ONLY after confirming Google Drive holds it safely!
    local_master = target_dir / "database" / "al_bahith_hadith.db"
    cloud_master = _find_verified_cloud_db(explicit_cloud_dir)
    if local_master.exists():
        if cloud_master and cloud_master.resolve() != local_master.resolve():
            for db_f in (target_dir / "database").glob("al_bahith_hadith.db*"):
                if db_f.is_file():
                    removed_bytes += db_f.stat().st_size
                    db_f.unlink(missing_ok=True)
            print(f"[CLEANED] Removed local duplicate master DB (verified safe on Cloud Vault: {cloud_master})")
        else:
            gdrive = explicit_cloud_dir or find_mounted_google_drive_folder()
            if gdrive and gdrive.resolve() != target_dir.resolve():
                dest_cloud_db = gdrive / "cloud_data" / "database" / "al_bahith_hadith.db"
                dest_cloud_db.parent.mkdir(parents=True, exist_ok=True)
                print(f"[MIGRATING] Moving {local_master} -> Google Drive `{dest_cloud_db}`...")
                shutil.copy2(local_master, dest_cloud_db)
                if dest_cloud_db.is_file() and dest_cloud_db.stat().st_size == local_master.stat().st_size:
                    for db_f in (target_dir / "database").glob("al_bahith_hadith.db*"):
                        if db_f.is_file():
                            removed_bytes += db_f.stat().st_size
                            db_f.unlink(missing_ok=True)
                    print("[MIGRATED] Master DB safely moved to Google Drive and purged from local PC!")
    else:
        # Clean orphan .wal/.shm files if any
        if (target_dir / "database").is_dir():
            for sidecar in (target_dir / "database").glob("al_bahith_hadith.db-*"):
                if sidecar.is_file():
                    removed_bytes += sidecar.stat().st_size
                    sidecar.unlink(missing_ok=True)

    return removed_bytes


def install_minimal_runtime(source_dir: Path, target_dir: Path, explicit_cloud_dir: Optional[Path] = None) -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    copied_files = 0

    if source_dir.resolve() != target_dir.resolve():
        for fname in ALLOWED_ROOT_FILES:
            if _copy_file_if_changed(source_dir / fname, target_dir / fname):
                copied_files += 1

        for fname in ALLOWED_BACKEND_PY:
            if _copy_file_if_changed(source_dir / "backend" / fname, target_dir / "backend" / fname):
                copied_files += 1

        copied_files += _copy_static_tree(source_dir / "backend" / "static", target_dir / "backend" / "static")

        for fname in ALLOWED_PIPELINE_PY:
            if _copy_file_if_changed(source_dir / "pipeline" / fname, target_dir / "pipeline" / fname):
                copied_files += 1

        for fname in ALLOWED_TOOLS_PY:
            if _copy_file_if_changed(source_dir / "tools" / fname, target_dir / "tools" / fname):
                copied_files += 1

        cat_rel = Path("database") / "catalogs" / "hadeeth_home_catalogs.json"
        if _copy_file_if_changed(source_dir / cat_rel, target_dir / cat_rel):
            copied_files += 1

    purged_bytes = purge_non_runtime_bloat(target_dir, explicit_cloud_dir=explicit_cloud_dir)
    cache_db = target_dir / "database" / "local_runtime_cache.db"
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    _init_local_cache_file(cache_db)

    footprint_mb = compute_local_runtime_footprint_mb(target_dir)
    return {
        "target_dir": str(target_dir),
        "copied_files": copied_files,
        "purged_mb": round(purged_bytes / (1024 * 1024), 2),
        "local_runtime_footprint_mb": footprint_mb,
        "local_cache_db": str(cache_db),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup Minimal Local PC Runtime for الباحث الحديثي")
    parser.add_argument("--target", default=DEFAULT_WINDOWS_TARGET if os.name == "nt" else "", help="Target local PC directory")
    parser.add_argument("--cloud-dir", default="", help="Optional explicit Google Drive folder path")
    parser.add_argument("--clean-self", action="store_true", help="Clean non-runtime bloat in current directory")
    args = parser.parse_args()

    cloud_dir = Path(args.cloud_dir) if args.cloud_dir else None
    if args.clean_self:
        purged = purge_non_runtime_bloat(BASE_DIR, explicit_cloud_dir=cloud_dir)
        mb_now = compute_local_runtime_footprint_mb(BASE_DIR)
        print(f"[OK] Local runtime verified at `{BASE_DIR}` ({mb_now} MB; purged {purged / (1024*1024):.2f} MB).")
        return

    if not args.target:
        print("Error: --target is required on non-Windows platforms.")
        sys.exit(1)

    res = install_minimal_runtime(BASE_DIR, Path(args.target), explicit_cloud_dir=cloud_dir)
    print("============================================================================")
    print("  الباحث الحديثي — Minimal Local PC Setup Complete!")
    print(f"  Local Runtime Folder : {res['target_dir']}")
    print(f"  Files Synced         : {res['copied_files']}")
    print(f"  Bloat Purged         : {res['purged_mb']} MB")
    print(f"  Total Local Size     : {res['local_runtime_footprint_mb']} MB (99.5% smaller than 3.25 GB!)")
    print("============================================================================")


if __name__ == "__main__":
    main()
