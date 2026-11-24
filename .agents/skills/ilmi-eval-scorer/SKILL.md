---
name: ilmi-eval-scorer
description: Executes Google ADK 4-Pattern trajectory evaluation, RAGAS Faithfulness (>= 0.85 merge-blocking floor), Answer Relevancy, Context Precision/Recall, 3D Citation Audit, and OWASP red-team tests. Use before any milestone gate or production release.
---
# Ilmi 4-Pattern Evaluation & RAGAS Scorer Skill

1. **4 ADK Evaluation Patterns**:
   - **Pattern 1 (Tool Trajectory)**: Verify exact retrieval/filter/lookup sequence (`tool_trajectory_avg_score == 1.0`).
   - **Pattern 2 (Deterministic Rubric Outcome)**: Evaluate semantic & scholarly rubric adherence with deterministic `temperature=0` scoring.
   - **Pattern 3 (Multi-Turn Memory Consistency)**: Test 3-Tier `living_memory` persistence and `superseded_by` updates in dedicated multi-turn sessions (kept separate from single-turn groundtruth trajectory cases).
   - **Pattern 4 (Workflow & Telemetry)**: Record `tool_call_count_v1`, `invocation_duration_v1`, and `context_cache_hit_rate`.
2. **RAGAS & 3D Citation Gate**: Run `.venv/bin/python evals/run_all_evals.py` (`scripts/run_eval_suite.py`). Block release if `RAGAS Faithfulness < 0.85` or `Broken Citations > 0`. Detail rubrics live in `references/eval-rubrics.md`.
