# Architectural Decisions Record (`.agents/memory/decisions.md`)

1. **ADR-001 — Dual-Tier Google Drive Cloud Vault + Minimal Local Runtime (`< 20 MB`)**:
   - Keep `3.25 GB` (`al_bahith_hadith.db` + raw corpora) on Google Drive in immutable `journal_mode=DELETE` (`?mode=ro&immutable=1`) and keep `D:\علمی معاون پرجیکٹ\حدیث سرچ` + GitHub `main` strictly `< 20 MB`.
2. **ADR-002 — 3-Stage Hybrid Retrieval (`BM25 + Dense Vector -> RRF k=60 -> Reranker`) with Strict Abstention (`0.22`) & Zero HyDE**:
   - Combine exact FTS5 BM25 (`k1=1.2, b=0.75`) with 256-dim bilingual concept/trigram dense vectors via RRF (`k=60`) and scholarly cross-encoder reranking; abstain cleanly below `0.22`.
3. **ADR-003 — 3-Tier Living Memory & Staged Human-in-the-Loop Proposals**:
   - Store structured facts separately from semantic corpus search with `valid_from` / `superseded_by` lineage, and require explicit human approval on `pending` proposals before updating `runtime_urdu_overrides`.
