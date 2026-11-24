---
description: Enforces Dual-Field Unicode normalization, 3-stage Hybrid BM25+Vector+RRF+Rerank retrieval, strict Abstention Thresholds, source-grounded Hadith citations, and Staged Human-in-the-Loop mutations.
trigger: model_decision
---
# Scholarly Hadith RAG, Dual-Field Unicode & Citation Integrity Rule

1. **Dual-Field Storage & Normalization**: Preserve vocalized Arabic (`matn_vocalized`) and literary Urdu (`matn_urdu`) bit-for-bit for display. Compute normalized search columns (`matn_normalized`, `matn_urdu_norm`) separately by decomposing Arabic Presentation Forms (`\uFB50-\uFDFF`, `\uFE70-\uFEFF`, e.g. `ﻻ -> ل+ا`), stripping tashkeel/tatweel (`U+0640`), and unifying Hamza/Alef, Ta-Marbuta, Alef-Maqsura, and Urdu/Arabic `ی/ي`, `ک/ك`, `ہ/ه`.
2. **3-Stage Hybrid Retrieval (Zero HyDE)**: Execute lexical `BM25 (k1=1.2, b=0.75)` and `Dense Concept/N-gram Vector` retrieval in parallel under identical metadata filters (`book_id`, `mohdith_id`, `rawi_id`, `grade_bucket`), fuse via `Reciprocal Rank Fusion (RRF, k=60)`, and score top candidates with the Scholarly Cross-Encoder Reranker. Never use HyDE on Hadith reference lookups.
3. **Mandatory Abstention**: Whenever the top reranked score falls below `0.22` (or zero grounded passages match), abstain immediately with `"دستیاب مستند ذخیرے میں اس سوال کا واضح حوالہ موجود نہیں۔"`.
4. **Atomic Citations & Staged HITL Mutations**: Every claim must carry a clickable citation (`book`, `author`, `number_or_page`, `grade`, and verbatim snapshot). All AI/user translation edits or scholarly notes must enter `staged_proposals` as `pending` first and mutate active overrides ONLY after explicit human approval.
