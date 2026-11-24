# -*- coding: utf-8 -*-
"""
OWASP Top 10 for Agentic Applications (2026: ASI01–ASI10) & Deterministic Model Armor Shield
============================================================================================
- ASI01 (Agent Goal Hijack / Indirect Prompt Injection): `<untrusted_source>` structural isolation
  + deterministic bilingual prompt-injection & XSS detector.
- ASI04 / ASI08 (Unbounded Consumption / Cascading Failures): Per-IP sliding-window rate limiter.
- ASI06 (Memory Poisoning): Provenance allowlist & injection block on memory/proposal writes.
- ASI10 (Auditability): Append-only SQLite audit log (`local_cache.audit_logs`).
"""

import collections
import html
import json
import re
import sqlite3
import threading
import time
from typing import Any, Deque, Dict, List, Tuple

PROMPT_INJECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("ignore_instructions", re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)\s+instructions", re.I)),
    ("system_override", re.compile(r"(?:you\s+are\s+now|new\s+system\s+prompt|reveal\s+your\s+system\s+prompt|developer\s+mode)", re.I)),
    ("fabricate_hadith_en", re.compile(r"(?:invent|fabricate|make\s+up)\s+(?:a\s+)?(?:sahih\s+)?hadith", re.I)),
    ("fabricate_hadith_ur", re.compile(r"(?:جھوٹی|فرضی|من\s*گھڑت)\s+حدیث\s+(?:گھڑ|بنا|لکھ)")),
    ("script_xss", re.compile(r"<\s*/?\s*(?:script|iframe|object|embed|svg\s+onload)\b", re.I)),
    ("delimiter_escape", re.compile(r"</?\s*untrusted_source\b", re.I)),
    ("sql_ddl_injection", re.compile(r";\s*(?:DROP|DELETE|ALTER|ATTACH|DETACH)\s+TABLE\b", re.I)),
]

ALLOWED_PROVENANCE_SOURCES = {
    "user_explicit",
    "researcher_proposal",
    "session_context",
    "ui_settings",
    "verified_corpus",
}


def inspect_input_model_armor(raw_text: str, max_chars: int = 2000) -> Dict[str, Any]:
    """
    Deterministic Model-Armor-grade input/output shield.
    Detects prompt injection, XSS tags, delimiter breakout, and Hadith fabrication commands.
    """
    text = str(raw_text or "")[:max_chars]
    flagged: List[str] = []
    sanitized = text

    for label, pat in PROMPT_INJECTION_PATTERNS:
        if pat.search(text):
            flagged.append(label)
            sanitized = pat.sub(" ", sanitized)

    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    return {
        "safe": len(flagged) == 0,
        "flagged_patterns": flagged,
        "sanitized": sanitized,
    }


def wrap_untrusted_source(source_id: str, authority: str, raw_content: str) -> str:
    """
    OWASP ASI01 Defense: Wraps retrieved external/corpus text inside explicit `<untrusted_source>`
    data boundaries and strips any nested boundary-escape tags so retrieved text is NEVER
    interpreted as executable system instructions.
    """
    safe_id = html.escape(str(source_id or "unknown"), quote=True)
    safe_auth = html.escape(str(authority or "corpus"), quote=True)
    cleaned_body = re.sub(r"</?\s*untrusted_source[^>]*>", "", str(raw_content or ""), flags=re.I)
    return f'<untrusted_source id="{safe_id}" authority="{safe_auth}">\n{cleaned_body}\n</untrusted_source>'


def validate_provenance(provenance: str) -> str:
    p = str(provenance or "user_explicit").strip().lower()
    return p if p in ALLOWED_PROVENANCE_SOURCES else "user_explicit"


class SlidingWindowRateLimiter:
    """OWASP ASI04 Defense: Per-client sliding-window rate limiter preventing unbounded consumption."""

    def __init__(self, max_requests: int = 180, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def check(self, client_key: str) -> Tuple[bool, int, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            dq = self._hits[client_key]
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - dq[0])) + 1)
                return False, 0, retry_after
            dq.append(now)
            remaining = max(0, self.max_requests - len(dq))
            return True, remaining, 0


def record_audit_event(
    conn: sqlite3.Connection,
    write_lock: threading.Lock,
    event_type: str,
    endpoint: str,
    details: Dict[str, Any],
    actor: str = "user",
) -> None:
    """OWASP ASI10 Defense: Append-only audit log in local writable SQLite overlay (`local_cache.audit_logs`)."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = json.dumps(details or {}, ensure_ascii=False)[:4000]
    try:
        with write_lock:
            conn.execute(
                """
                INSERT INTO local_cache.audit_logs (event_type, actor, endpoint, details_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(event_type)[:80], str(actor)[:80], str(endpoint)[:160], payload, ts),
            )
            conn.commit()
    except Exception:
        pass
