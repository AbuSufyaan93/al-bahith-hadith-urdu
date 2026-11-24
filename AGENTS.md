# الباحث الحديثي — اردو، عربي (Al-Bahith Al-Hadithi — Production Agent Context Map)

## 1. System Identity & Core Mission
**الباحث الحديثي — اردو، عربی** (`Ilmi Muawin / Ilmi Project — Hadith Search`) is a production-grade scholarly Hadith & Lexicon platform achieving 100% visual and wire-protocol parity with `https://hadeeth.com/` while integrating authentic Salafi Urdu translations, explanations (`sharh`), 3-stage Hybrid RAG (`BM25 + Dense Vector + RRF k=60 + Cross-Encoder Reranker`), 3-Tier Living Research Memory, Staged Human-in-the-Loop Proposals, and the 283,601-entry Rekhta & Qari Urdu-Arabic Lexicon.

## 2. Architecture & Storage Map (Dual-Tier Cloud Vault + Minimal Local PC)
- **`backend/main.py`**: FastAPI entry point, exact `search.hadeeth.com` v2 wire API, SvelteKit `devalue` `/sk-data.json` bridge, Private Network Access (`PNA`), and REST endpoints.
- **`backend/cloud_storage_bridge.py`**: Opens the `1.71 GB` master SQLite FTS5 vault (`cloud_data/database/al_bahith_hadith.db` on Google Drive `1c7w9HLYONrrdcvqh7uPhQdE0sAOqHmLA`) in lock-free immutable mode (`?mode=ro&immutable=1`) and attaches local writable `database/local_runtime_cache.db`.
- **`backend/hybrid_rag_engine.py`**: 3-Stage Hybrid Scholarly Retrieval (`BM25 k1=1.2, b=0.75` + `256-dim Bilingual Concept/N-gram Dense Vector` -> `RRF k=60` -> `Scholarly Cross-Encoder Reranker` + strict `Abstention Threshold = 0.22` + static `ContextCache`). Never use HyDE.
- **`backend/memory_and_proposals.py`**: 3-Tier Living Memory (`valid_from`, `superseded_by`, `expires_at`, user delete) + Staged Human-in-the-Loop Proposals (`pending` -> explicit human `approved` -> override applied).
- **`backend/security_guardrails.py`**: OWASP Agentic Top 10 (`ASI01`–`ASI10`) shield, `<untrusted_source>` wrapping, deterministic Model-Armor prompt-injection filter, sliding-window rate limiter, and append-only audit trail.
- **`pipeline/normalizer.py` & `pipeline/salafi_urdu_engine.py`**: Dual-Field Arabic/Urdu Unicode & Presentation-Forms normalizer (`canonical_text` never mutated!) and Salafi creed/honorifics engine.
- **`backend/static/`**: Genuine Svelte 5 + SvelteKit 2 frontend + `assets/hadeeth_urdu_bridge.js` + `assets/hadeeth_urdu_bridge.css` + `assets/hadeeth_serverless_engine.js` (hybrid local-PC + 48,911-Hadith serverless GitHub Pages runtime).
- **`evals/`**: 36-case Golden Benchmark + 4-Pattern ADK Trajectory/Rubric/Memory/Telemetry evaluator + RAGAS (`Faithfulness >= 0.85`) + 3D Citation Audit (`Support`, `Coverage`, `Authority`).

## 3. Closed-Loop Execution Protocol (`Plan → Trace → Act → Verify`)
1. **Plan**: Inspect target files with line-bounded reads; verify invariants in `.agents/rules/`.
2. **Trace**: Identify root causes using local deterministic CLI scripts (`0 LLM tokens`) before editing.
3. **Act**: Apply surgical targeted diffs (`replace_file_content`). Never leave `// TODO`, mock data, or truncated scholarly text.
4. **Verify**: Run unit, security, harness, platform, and evaluation suites before pushing to both GitHub branches (`main` + `gh-pages`) and Google Drive.

## 4. Essential Build, Test & Verification Commands
- Validate 4-Layer Agent Harness: `.venv/bin/python tools/validate_agent_harness.py`
- Run 15-Gate Platform Verification: `.venv/bin/python tools/verify_platform.py`
- Run 4-Pattern ADK + RAGAS + Security Eval Suite: `.venv/bin/python evals/run_all_evals.py`
- Launch Dual-Stack Local Server (`8088` + `8080`): `.venv/bin/python tools/run_local_server.py --ports 8088,8080`
- Build & Push GitHub (`main` + `gh-pages`): `.venv/bin/python tools/build_github_pages.py && bash scripts/push-all-github.sh`
- Sync Minimal Runtime & Launchers to Google Drive: `.venv/bin/python tools/sync_to_gdrive.py`

## 5. Non-Negotiable Scholarly, Linguistic & Retry Invariants
1. **Zero Fabricated Hadith / Strict Abstention**: Never invent a Hadith, narrator chain, or scholar ruling. When reranker confidence `< 0.22`, return `"دستیاب مستند ذخیرے میں اس سوال کا واضح حوالہ موجود نہیں۔"`.
2. **Dual-Field Preservation**: Never overwrite vocalized `matn_vocalized` with normalized text.
3. **Salafi Urdu Creed**: Use `اللہ تعالیٰ`, `ﷺ`, `سیدنا ... رضی اللہ عنہ`, `امام ... رحمہ اللہ`, and `وفات`.
4. **Strict Retry Bound (Max 3 Attempts)**: Never loop infinitely on a failing command or test. After **3 failed attempts**, log the root cause in `.agents/memory/errors.md` and escalate for human review.
5. **Cloud-Vault Hygiene**: Never commit `cloud_data/` (`3.25 GB`) to GitHub `main` or copy it into `D:\علمی معاون پرجیکٹ\حدیث سرچ` (`< 20 MB` local footprint limit).
