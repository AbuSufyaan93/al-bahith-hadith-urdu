---
name: ilmi-rag-pipeline
description: Builds and audits the citation-grounded scholarly Hadith RAG pipeline using dual-field Urdu/Arabic Unicode normalization, parallel BM25 + dense vector search, RRF (k=60), cross-encoder reranking, and strict abstention thresholds. Use when adding scholarly sources, tuning search relevance, or fixing citation retrieval bugs.
---
# Ilmi Scholarly Hadith RAG Pipeline Skill

1. **Dual-Field Invariant**: Never mutate vocalized `matn_vocalized` or literary `matn_urdu`. Always compute search keys via `pipeline/normalizer.py` or `scripts/normalize_urdu_arabic.py` (decomposing Presentation Forms `\uFB50-\uFDFF` and `\uFE70-\uFEFF`).
2. **Parallel Hybrid Retrieval**: Enforce identical metadata filters (`book_id`, `mohdith_id`, `rawi_id`, `grade_bucket`) on both `BM25 (k1=1.2, b=0.75)` and `Dense Concept/N-gram Vector` branches before fusing via `RRF (k=60)`.
3. **Reranking & Abstention**: Score top RRF candidates with the Scholarly Cross-Encoder Reranker in `backend/hybrid_rag_engine.py` and enforce the abstention floor in `references/retrieval-thresholds.md` (`0.22`). Never use HyDE.
4. **Verification**: Run `.venv/bin/python evals/run_all_evals.py` to confirm `Recall@5` uplift over baseline and `RAGAS Faithfulness >= 0.85`.
