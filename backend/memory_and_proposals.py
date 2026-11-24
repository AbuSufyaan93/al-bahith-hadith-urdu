# -*- coding: utf-8 -*-
"""
3-Tier Living Research Memory & Staged Human-in-the-Loop Proposal Engine
========================================================================
1. Living Memory (`local_cache.living_memory`):
   - Tier 1: Permanent researcher preferences (script, grading strictness, citation format)
   - Tier 2: Active research topic / book with explicit TTL (`expires_at`)
   - Tier 3: Ephemeral session context
   - Temporal lineage: Updates never silently overwrite history; prior active rows receive
     `superseded_by = <new_id>` with `valid_from` ISO timestamps, and users can delete any item.
2. Staged Human-in-the-Loop Proposals (`local_cache.staged_proposals`):
   - All proposed Urdu translation refinements or scholarly notes enter as `status = 'pending'`
     with a clear diff & risk summary (`<StagedProposalCard />`).
   - Active `runtime_urdu_overrides` is NEVER mutated until explicit human `approve`.
"""

import difflib
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from backend.cloud_storage_bridge import save_urdu_override
from backend.security_guardrails import (
    inspect_input_model_armor,
    record_audit_event,
    validate_provenance,
)
from pipeline.salafi_urdu_engine import sanitize_salafi_urdu


def _utc_iso(offset_seconds: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset_seconds))


def _ensure_tables_ready(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS local_cache.living_memory (
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
        CREATE TABLE IF NOT EXISTS local_cache.staged_proposals (
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
        CREATE TABLE IF NOT EXISTS local_cache.audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            actor TEXT DEFAULT 'user',
            endpoint TEXT DEFAULT '',
            details_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        """
    )


def upsert_memory_fact(
    conn: sqlite3.Connection,
    write_lock: threading.Lock,
    tier: int,
    fact_key: str,
    fact_value: str,
    provenance: str = "user_explicit",
    ttl_hours: Optional[int] = None,
) -> Dict[str, Any]:
    """Inserts a new Living Memory fact and sets `superseded_by` on any previous active fact for (tier, fact_key)."""
    if tier not in (1, 2, 3):
        raise ValueError("tier must be 1 (Permanent), 2 (Medium-Term TTL), or 3 (Session)")

    key_armor = inspect_input_model_armor(fact_key, max_chars=120)
    val_armor = inspect_input_model_armor(fact_value, max_chars=800)
    if not key_armor["safe"] or not val_armor["safe"]:
        raise ValueError(f"ASI06 Memory Poisoning Guard blocked input: {key_armor['flagged_patterns'] + val_armor['flagged_patterns']}")

    clean_key = key_armor["sanitized"]
    clean_val = val_armor["sanitized"]
    if not clean_key or not clean_val:
        raise ValueError("fact_key and fact_value cannot be empty")

    prov = validate_provenance(provenance)
    now_iso = _utc_iso(0)
    expires_iso: Optional[str] = None
    if tier == 2:
        hours = ttl_hours if (ttl_hours and ttl_hours > 0) else 24 * 14  # Default 14-day TTL for Tier 2
        expires_iso = _utc_iso(hours * 3600)
    elif tier == 3 and ttl_hours and ttl_hours > 0:
        expires_iso = _utc_iso(ttl_hours * 3600)

    with write_lock:
        _ensure_tables_ready(conn)
        prev_rows = conn.execute(
            """
            SELECT id FROM local_cache.living_memory
            WHERE tier = ? AND fact_key = ? AND is_deleted = 0 AND superseded_by IS NULL
            """,
            (tier, clean_key),
        ).fetchall()

        cur = conn.execute(
            """
            INSERT INTO local_cache.living_memory
            (tier, fact_key, fact_value, provenance, valid_from, superseded_by, expires_at, is_deleted)
            VALUES (?, ?, ?, ?, ?, NULL, ?, 0)
            """,
            (tier, clean_key, clean_val, prov, now_iso, expires_iso),
        )
        new_id = int(cur.lastrowid)

        superseded_ids: List[int] = []
        for pr in prev_rows:
            pid = int(pr[0])
            conn.execute(
                "UPDATE local_cache.living_memory SET superseded_by = ? WHERE id = ?",
                (new_id, pid),
            )
            superseded_ids.append(pid)
        conn.commit()

    record_audit_event(
        conn,
        write_lock,
        event_type="memory_upsert",
        endpoint="/api/v1/memory",
        details={"id": new_id, "tier": tier, "fact_key": clean_key, "superseded_ids": superseded_ids, "provenance": prov},
    )
    return {
        "id": new_id,
        "tier": tier,
        "fact_key": clean_key,
        "fact_value": clean_val,
        "provenance": prov,
        "valid_from": now_iso,
        "superseded_by": None,
        "superseded_previous_ids": superseded_ids,
        "expires_at": expires_iso,
    }


def list_memory_facts(conn: sqlite3.Connection, include_superseded: bool = False) -> List[Dict[str, Any]]:
    _ensure_tables_ready(conn)
    now_iso = _utc_iso(0)
    if include_superseded:
        rows = conn.execute(
            """
            SELECT id, tier, fact_key, fact_value, provenance, valid_from, superseded_by, expires_at
            FROM local_cache.living_memory
            WHERE is_deleted = 0
            ORDER BY tier ASC, id DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, tier, fact_key, fact_value, provenance, valid_from, superseded_by, expires_at
            FROM local_cache.living_memory
            WHERE is_deleted = 0
              AND superseded_by IS NULL
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY tier ASC, id DESC
            """,
            (now_iso,),
        ).fetchall()

    return [
        {
            "id": int(r[0]),
            "tier": int(r[1]),
            "fact_key": r[2],
            "fact_value": r[3],
            "provenance": r[4],
            "valid_from": r[5],
            "superseded_by": r[6],
            "expires_at": r[7],
        }
        for r in rows
    ]


def delete_memory_fact(conn: sqlite3.Connection, write_lock: threading.Lock, mem_id: int) -> bool:
    with write_lock:
        _ensure_tables_ready(conn)
        cur = conn.execute(
            "UPDATE local_cache.living_memory SET is_deleted = 1 WHERE id = ? AND is_deleted = 0",
            (int(mem_id),),
        )
        conn.commit()
        changed = cur.rowcount > 0
    if changed:
        record_audit_event(
            conn,
            write_lock,
            event_type="memory_delete",
            endpoint=f"/api/v1/memory/{mem_id}",
            details={"deleted_id": int(mem_id)},
        )
    return changed


def _compute_diff_summary(original: str, proposed: str) -> str:
    orig_words = (original or "").split()
    prop_words = (proposed or "").split()
    sm = difflib.SequenceMatcher(None, orig_words, prop_words)
    parts: List[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("delete", "replace") and i1 < i2:
            parts.append(f"[- {' '.join(orig_words[i1:i2])}]")
        if tag in ("insert", "replace") and j1 < j2:
            parts.append(f"[+ {' '.join(prop_words[j1:j2])}]")
    return " ".join(parts)[:600] if parts else "[+ نیا علمی اندراج]"


def create_staged_proposal(
    conn: sqlite3.Connection,
    write_lock: threading.Lock,
    target_type: str,
    target_id: str,
    original_text: str,
    proposed_text: str,
    provenance: str = "researcher_proposal",
) -> Dict[str, Any]:
    """
    Creates a `pending` Staged Human-in-the-Loop Proposal (`<StagedProposalCard />`).
    Strictly NEVER mutates `runtime_urdu_overrides` or master DB until human approval!
    """
    if target_type not in ("urdu_translation", "scholarly_note", "sharh_urdu"):
        raise ValueError("target_type must be urdu_translation, scholarly_note, or sharh_urdu")

    armor = inspect_input_model_armor(proposed_text, max_chars=3000)
    if not armor["safe"]:
        raise ValueError(f"ASI01/ASI09 Guard blocked unsafe proposal payload: {armor['flagged_patterns']}")

    clean_proposed = sanitize_salafi_urdu(armor["sanitized"])
    if not clean_proposed:
        raise ValueError("proposed_text cannot be empty")

    clean_orig = str(original_text or "").strip()[:3000]
    clean_tid = str(target_id or "").strip()[:120]
    if not clean_tid:
        raise ValueError("target_id is required")

    diff_sum = _compute_diff_summary(clean_orig, clean_proposed)
    risk_sum = (
        "یہ تجویز اس وقت زیرِ التوا (Pending) ہے؛ جب تک آپ خود «تجویز قبول کریں» پر کلک نہیں کریں گے، "
        "مقامی ذخیرے میں کوئی تبدیلی محفوظ نہیں ہوگی اور اصل عربی متن ۱۰۰٪ غیر متبدل رہے گا۔"
    )
    now_iso = _utc_iso(0)
    prov = validate_provenance(provenance)

    with write_lock:
        _ensure_tables_ready(conn)
        cur = conn.execute(
            """
            INSERT INTO local_cache.staged_proposals
            (target_type, target_id, original_text, proposed_text, diff_summary, risk_summary, status, provenance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (target_type, clean_tid, clean_orig, clean_proposed, diff_sum, risk_sum, prov, now_iso),
        )
        prop_id = int(cur.lastrowid)
        conn.commit()

    record_audit_event(
        conn,
        write_lock,
        event_type="proposal_staged",
        endpoint="/api/v1/proposals",
        details={"proposal_id": prop_id, "target_type": target_type, "target_id": clean_tid, "status": "pending"},
    )
    return {
        "id": prop_id,
        "target_type": target_type,
        "target_id": clean_tid,
        "original_text": clean_orig,
        "proposed_text": clean_proposed,
        "diff_summary": diff_sum,
        "risk_summary": risk_sum,
        "status": "pending",
        "created_at": now_iso,
    }


def list_staged_proposals(conn: sqlite3.Connection, status: Optional[str] = None) -> List[Dict[str, Any]]:
    _ensure_tables_ready(conn)
    if status in ("pending", "approved", "rejected"):
        rows = conn.execute(
            """
            SELECT id, target_type, target_id, original_text, proposed_text, diff_summary, risk_summary, status, created_at, reviewed_at
            FROM local_cache.staged_proposals
            WHERE status = ?
            ORDER BY id DESC LIMIT 100
            """,
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, target_type, target_id, original_text, proposed_text, diff_summary, risk_summary, status, created_at, reviewed_at
            FROM local_cache.staged_proposals
            ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END, id DESC LIMIT 100
            """
        ).fetchall()

    return [
        {
            "id": int(r[0]),
            "target_type": r[1],
            "target_id": r[2],
            "original_text": r[3],
            "proposed_text": r[4],
            "diff_summary": r[5],
            "risk_summary": r[6],
            "status": r[7],
            "created_at": r[8],
            "reviewed_at": r[9],
        }
        for r in rows
    ]


def review_staged_proposal(
    conn: sqlite3.Connection,
    write_lock: threading.Lock,
    proposal_id: int,
    action: str,
    edited_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes human review (`approve` or `reject`) on a pending Staged Proposal.
    ONLY upon explicit `approve` does it commit the Salafi-sanitized Urdu text to `runtime_urdu_overrides`.
    """
    act = str(action or "").strip().lower()
    if act not in ("approve", "reject"):
        raise ValueError("action must be 'approve' or 'reject'")

    with write_lock:
        _ensure_tables_ready(conn)
        row = conn.execute(
            """
            SELECT id, target_type, target_id, original_text, proposed_text, status
            FROM local_cache.staged_proposals WHERE id = ?
            """,
            (int(proposal_id),),
        ).fetchone()
        if not row:
            raise KeyError(f"Proposal {proposal_id} not found")

        target_type, target_id, orig_txt, prop_txt, cur_status = row[1], row[2], row[3], row[4], row[5]
        final_text = prop_txt
        if edited_text is not None and edited_text.strip():
            armor = inspect_input_model_armor(edited_text, max_chars=3000)
            if not armor["safe"]:
                raise ValueError(f"Blocked unsafe edited text: {armor['flagged_patterns']}")
            final_text = sanitize_salafi_urdu(armor["sanitized"])

        new_status = "approved" if act == "approve" else "rejected"
        reviewed_iso = _utc_iso(0)
        conn.execute(
            """
            UPDATE local_cache.staged_proposals
            SET status = ?, proposed_text = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (new_status, final_text, reviewed_iso, int(proposal_id)),
        )
        conn.commit()

    if new_status == "approved":
        with write_lock:
            if target_type == "urdu_translation":
                save_urdu_override(conn, f"dorar:{target_id}", matn_urdu=final_text)
            elif target_type in ("sharh_urdu", "scholarly_note"):
                save_urdu_override(conn, f"dorar:{target_id}", sharh_urdu=final_text)

    record_audit_event(
        conn,
        write_lock,
        event_type=f"proposal_{new_status}",
        endpoint=f"/api/v1/proposals/{proposal_id}/review",
        details={"proposal_id": int(proposal_id), "target_type": target_type, "target_id": target_id, "status": new_status},
    )
    return {
        "id": int(proposal_id),
        "target_type": target_type,
        "target_id": target_id,
        "original_text": orig_txt,
        "proposed_text": final_text,
        "status": new_status,
        "reviewed_at": reviewed_iso,
    }
