# -*- coding: utf-8 -*-
"""
Fast, Concurrent & Idempotent Google Drive Uploader for `/home/antigravity/hadith-search-urdu`
into Google Drive folder `حدیث سرچ` (`1c7w9HLYONrrdcvqh7uPhQdE0sAOqHmLA`).
"""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
TARGET_DRIVE_FOLDER_ID = "1c7w9HLYONrrdcvqh7uPhQdE0sAOqHmLA"

SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".antigravity", "scripts", "evals"}
SKIP_SUFFIXES = {".pyc", ".pyo", "-wal", "-shm", ".orig"}
FORCE_DB = "--force-db" in sys.argv

FORCE_UPDATE_FILES = {
    "ACTIVE_LINKS.txt",
    "AGENTS.md",
    "Install-Windows-AutoStart.bat",
    "README.md",
    "requirements.txt",
    "Setup-Local-PC-D-Drive.bat",
    "Start-Al-Bahith-Hadith.bat",
    "Start-Background-Silent.vbs",
    "Sync-To-Google-Drive.bat",
    "سیٹ_اپ_لوکل_پی_سی.bat",
    "تشغيل_الباحث_الحديثي.bat",
    "cloud_runtime_config.json",
    "hadeeth_home_catalogs.json",
    "index.html",
    "hadeeth_serverless_engine.js",
    "hadeeth_urdu_bridge.js",
    "hadeeth_urdu_bridge.css",
    "NotoNastaliqUrdu-Variable.ttf",
    "main.py",
    "cloud_storage_bridge.py",
    "arabic_urdu_sanitizer.py",
    "hybrid_rag_engine.py",
    "memory_and_proposals.py",
    "security_guardrails.py",
    "salafi_urdu_engine.py",
    "sveltekit_bridge.py",
    "books_catalog.py",
    "normalizer.py",
    "run_local_server.py",
    "setup_local_pc_minimal.py",
    "sync_to_gdrive.py",
    "validate_agent_harness.py",
    "verify_platform.py",
}


import time


def run_gdrive(*args: str, timeout: int = 1800) -> str:
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            res = subprocess.run(["gdrive", *args], capture_output=True, text=True, check=True, timeout=timeout)
            return res.stdout.strip()
        except Exception as exc:
            last_err = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"gdrive command failed after 3 attempts: {args}: {last_err}")


def get_children_map(parent_id: str) -> Dict[str, Dict[str, Any]]:
    for attempt in range(3):
        out = run_gdrive("readonly", "ls", parent_id, "--max", "500", "--json")
        if out:
            data = json.loads(out)
            items = data.get("files") if isinstance(data, dict) else data
            mapping: Dict[str, Dict[str, Any]] = {}
            for it in items or []:
                if isinstance(it, dict) and it.get("name") and it.get("id"):
                    mapping[it["name"]] = {
                        "id": it["id"],
                        "mimeType": it.get("mimeType", ""),
                        "size": int(it["size"]) if str(it.get("size") or "").isdigit() else -1,
                    }
            return mapping
        time.sleep(0.6 * (attempt + 1))
    return {}


def ensure_drive_folder(name: str, parent_id: str, existing: Dict[str, Dict[str, Any]]) -> str:
    if name in existing and "folder" in existing[name].get("mimeType", ""):
        return existing[name]["id"]
    refreshed_first = get_children_map(parent_id)
    if name in refreshed_first and "folder" in refreshed_first[name].get("mimeType", ""):
        existing.update(refreshed_first)
        return refreshed_first[name]["id"]
    out = run_gdrive("mutate", "mkdir", name, "--parent", parent_id, "--json")
    try:
        parsed = json.loads(out)
        if isinstance(parsed, dict) and parsed.get("id"):
            existing[name] = {"id": str(parsed["id"]), "mimeType": "application/vnd.google-apps.folder", "size": -1}
            return str(parsed["id"])
    except Exception:
        pass
    refreshed = get_children_map(parent_id)
    if name in refreshed:
        existing.update(refreshed)
        return refreshed[name]["id"]
    raise RuntimeError(f"Failed to resolve created Drive folder '{name}'")


def migrate_legacy_root_into_cloud_data(root_id: str) -> None:
    """
    Safely relocates heavy/non-runtime items inside `1c7w9HLYONrrdcvqh7uPhQdE0sAOqHmLA` into `cloud_data/`
    using `gdrive mutate mv` (preserving all shared permissions and deleting ZERO user files).
    """
    root_map = get_children_map(root_id)
    cloud_id = ensure_drive_folder("cloud_data", root_id, root_map)
    cloud_map = get_children_map(cloud_id)
    cloud_db_id = ensure_drive_folder("database", cloud_id, cloud_map)
    ensure_drive_folder("datasets_raw", cloud_id, cloud_map)
    ensure_drive_folder("cache_snapshots", cloud_id, cloud_map)
    dev_arch_id = ensure_drive_folder("dev_archive", cloud_id, cloud_map)
    dev_arch_map = get_children_map(dev_arch_id)

    # 1. Move top-level `exports` -> `cloud_data/exports`
    if "exports" in root_map and "exports" not in cloud_map:
        print("[MIGRATE] Moving Drive `exports/` -> `cloud_data/exports/`...", flush=True)
        run_gdrive("mutate", "mv", root_map["exports"]["id"], cloud_id)

    # 2. Move top-level archive items -> `cloud_data/dev_archive/`
    for arch_name in ("frontend", "Dockerfile", "docker-compose.yml"):
        if arch_name in root_map and arch_name not in dev_arch_map:
            print(f"[MIGRATE] Moving Drive `{arch_name}` -> `cloud_data/dev_archive/{arch_name}`...", flush=True)
            run_gdrive("mutate", "mv", root_map[arch_name]["id"], dev_arch_id)

    # 3. Inspect `database/` on Drive: move `al_bahith_hadith.db` -> `cloud_data/database/`, schemas & stale sidecars -> `dev_archive/`
    if "database" in root_map:
        db_folder_id = root_map["database"]["id"]
        db_children = get_children_map(db_folder_id)
        cloud_db_children = get_children_map(cloud_db_id)
        if "al_bahith_hadith.db" in db_children and "al_bahith_hadith.db" not in cloud_db_children:
            print("[MIGRATE] Moving Drive `database/al_bahith_hadith.db` -> `cloud_data/database/al_bahith_hadith.db`...", flush=True)
            run_gdrive("mutate", "mv", db_children["al_bahith_hadith.db"]["id"], cloud_db_id)
        for sch in ("postgres_schema.sql", "schema.sql"):
            if sch in db_children:
                print(f"[MIGRATE] Moving Drive `database/{sch}` -> `cloud_data/dev_archive/{sch}`...", flush=True)
                run_gdrive("mutate", "mv", db_children[sch]["id"], dev_arch_id)
        for sidecar, new_nm in (
            ("al_bahith_hadith.db-shm", "legacy_al_bahith_hadith.db-shm.bak"),
            ("al_bahith_hadith.db-wal", "legacy_al_bahith_hadith.db-wal.bak"),
        ):
            if sidecar in db_children:
                print(f"[MIGRATE] Archiving stale WAL sidecar `{sidecar}` -> `cloud_data/dev_archive/{new_nm}`...", flush=True)
                run_gdrive("mutate", "rename", db_children[sidecar]["id"], new_nm)
                run_gdrive("mutate", "mv", db_children[sidecar]["id"], dev_arch_id)

    # 4. Inspect `pipeline/`, `tools/`, and `backend/static/` for legacy build/duplicate items
    if "pipeline" in root_map:
        p_children = get_children_map(root_map["pipeline"]["id"])
        if "build_database.py" in p_children:
            print("[MIGRATE] Moving `pipeline/build_database.py` -> `cloud_data/dev_archive/`...", flush=True)
            run_gdrive("mutate", "mv", p_children["build_database.py"]["id"], dev_arch_id)

    if "tools" in root_map:
        t_children = get_children_map(root_map["tools"]["id"])
        for t_arch in ("build_sk_assets.py", "repair_dorar_urdu_links.py"):
            if t_arch in t_children:
                print(f"[MIGRATE] Moving `tools/{t_arch}` -> `cloud_data/dev_archive/`...", flush=True)
                run_gdrive("mutate", "mv", t_children[t_arch]["id"], dev_arch_id)

    if "backend" in root_map:
        b_children = get_children_map(root_map["backend"]["id"])
        if "static" in b_children:
            st_children = get_children_map(b_children["static"]["id"])
            if "_app" in st_children:
                print("[MIGRATE] Moving duplicate `backend/static/_app` -> `cloud_data/dev_archive/_app_legacy`...", flush=True)
                run_gdrive("mutate", "rename", st_children["_app"]["id"], "_app_legacy")
                run_gdrive("mutate", "mv", st_children["_app"]["id"], dev_arch_id)


def collect_sync_plan(
    local_dir: Path, drive_parent_id: str, rel_prefix: str = ""
) -> Tuple[List[Tuple[Path, str, str, Dict[str, Any]]], List[Tuple[Path, str, str, Dict[str, Any]]]]:
    """Creates all folders first and returns (small_files, large_files) to upload."""
    existing = get_children_map(drive_parent_id)
    small_files: List[Tuple[Path, str, str, Dict[str, Any]]] = []
    large_files: List[Tuple[Path, str, str, Dict[str, Any]]] = []

    for entry in sorted(local_dir.iterdir(), key=lambda p: p.name):
        if entry.name.startswith("."):
            continue
        if entry.is_file():
            if any(entry.name.endswith(s) for s in SKIP_SUFFIXES):
                continue
            # Never upload local_runtime_cache.db into `database/` root on Drive
            if entry.name == "local_runtime_cache.db" and rel_prefix == "database":
                continue
            rel_name = f"{rel_prefix}/{entry.name}".lstrip("/")
            ex_meta = existing.get(entry.name, {})
            local_sz = entry.stat().st_size
            if ex_meta and "folder" not in ex_meta.get("mimeType", ""):
                ex_sz = int(ex_meta.get("size") or -1)
                force_code = entry.name in FORCE_UPDATE_FILES
                if (not force_code and ex_sz == local_sz and entry.name != "al_bahith_hadith.db") or (
                    not FORCE_DB and entry.name == "al_bahith_hadith.db" and ex_sz == local_sz
                ):
                    print(f"  [SKIP-EXISTS] {rel_name}", flush=True)
                    continue
            item = (entry, drive_parent_id, rel_name, ex_meta)
            if local_sz > 50 * 1024 * 1024:
                large_files.append(item)
            else:
                small_files.append(item)
        elif entry.is_dir() and entry.name not in SKIP_DIRS:
            if entry.name == "cloud_data" and not FORCE_DB and entry.name in existing:
                print("  [SKIP-VAULT] cloud_data/ (3.25 GB unchanged; pass --force-db to rescan)", flush=True)
                continue
            rel_dir = f"{rel_prefix}/{entry.name}".lstrip("/")
            print(f"[DIR] {rel_dir}/", flush=True)
            sub_id = ensure_drive_folder(entry.name, drive_parent_id, existing)
            sf, lf = collect_sync_plan(entry, sub_id, rel_dir)
            small_files.extend(sf)
            large_files.extend(lf)

    return small_files, large_files


def _upload_single(task: Tuple[Path, str, str, Dict[str, Any]]) -> str:
    fpath, parent_id, rel_name, ex_meta = task
    mb = fpath.stat().st_size / (1024 * 1024)
    if ex_meta and ex_meta.get("id") and "folder" not in ex_meta.get("mimeType", ""):
        run_gdrive("mutate", "update", ex_meta["id"], str(fpath))
    else:
        run_gdrive("mutate", "upload", str(fpath), "--parent", parent_id)
    return f"  [OK] {rel_name} ({mb:.2f} MB)"


if __name__ == "__main__":
    print(f"=== Cloud-Vault + Minimal Runtime Sync: {BASE_DIR} -> Google Drive `{TARGET_DRIVE_FOLDER_ID}` (حدیث سرچ) ===", flush=True)
    migrate_legacy_root_into_cloud_data(TARGET_DRIVE_FOLDER_ID)
    small, large = collect_sync_plan(BASE_DIR, TARGET_DRIVE_FOLDER_ID)
    print(f"Uploading {len(small)} files concurrently (8 workers)...", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_upload_single, t) for t in small]
        for fut in as_completed(futs):
            print(fut.result(), flush=True)
            done += 1

    for lt in large:
        print(f"Uploading large vault file {lt[2]} ({lt[0].stat().st_size / (1024*1024):.1f} MB)...", flush=True)
        print(_upload_single(lt), flush=True)
        done += 1

    print(f"=== ALL DONE! {done} files synced/updated in Google Drive `حدیث سرچ` ===", flush=True)
