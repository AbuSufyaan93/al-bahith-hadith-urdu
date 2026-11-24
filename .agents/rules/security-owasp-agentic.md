---
description: Mandatory OWASP Top 10 for Agentic Applications 2026 (ASI01-ASI10) security controls, prompt-injection isolation, supply-chain pinning, rate limiting, and secret protection.
trigger: always_on
---
# OWASP Agentic Top 10 (ASI01–ASI10) & Supply-Chain Security Rule

1. **ASI01 (Goal Hijack Defense)**: Wrap all retrieved external/database passages inside `<untrusted_source id="..." authority="...">` boundaries and strip indirect prompt-injection directives (`ignore previous instructions`, `system:`, `<script>`).
2. **ASI02/ASI03 (Least Privilege)**: Keep the master SQLite database strictly read-only immutable (`?mode=ro&immutable=1`). Restrict auditor subagents to read-only tools.
3. **ASI04/ASI08 (Bounded Consumption & Retries)**: Enforce per-IP sliding-window rate limiting on search/RAG/translation routes and cap automated self-healing loops at **3 retries**.
4. **ASI06/ASI09 (Memory Provenance & Human Approval)**: Validate provenance and sanitize payloads before writing to `living_memory` or `staged_proposals`; never apply scholarly overrides without explicit human approval.
5. **Supply Chain & Secrets**: Never commit `.env` files, tokens, or unpinned/unverified packages (Slopsquatting defense). Log tool/mutation events to the append-only audit trail.
