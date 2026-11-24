# Scholarly Hadith Retrieval & Abstention Thresholds

- **BM25 Parameters**: `k1 = 1.2`, `b = 0.75` over `dorar_hadiths_fts`, `canonical_hadiths_fts`, and `hadeethenc_fts`.
- **Dense Vector Branch**: 256-dim L2-normalized bilingual Hadith theological/fiqhi concept + character 3/4-gram cosine similarity (`min_cosine = 0.14`).
- **Reciprocal Rank Fusion**: `k = 60` (`score = sum(1.0 / (60 + rank_i))`).
- **Cross-Encoder Reranker Floor (`ABSTENTION_THRESHOLD`)**: `0.22` on `[0.0, 1.0]` calibrated scale.
- **Abstention Message (Mandatory Salafi Urdu)**: `"دستیاب مستند ذخیرے میں اس سوال کا واضح حوالہ موجود نہیں۔"`
- **HyDE Policy**: Strictly disabled (`use_hyde = False`) to prevent fabricated Hadith wording from polluting exact reference lookups.
