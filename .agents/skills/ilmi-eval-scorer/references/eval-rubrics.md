# Evaluation Rubrics & Merge-Blocking Floors

| Metric | Floor / Target | Gate Type |
|---|---|---|
| Unit, Integration & 15-Gate Platform Suite | `100% PASS` | Merge-Blocking |
| OWASP ASI01–ASI10 Red-Team Suite | `100% PASS` | Merge-Blocking |
| ADK Pattern 1: `tool_trajectory_avg_score` | `>= 0.98` (Target `1.00`) | Merge-Blocking |
| RAGAS `Faithfulness` | `>= 0.85` | Merge-Blocking |
| RAGAS `Answer Relevancy` | `>= 0.85` | Merge-Blocking |
| 3D Citation `Support %` & `Coverage %` | `>= 95%`, `0` broken refs | Merge-Blocking |
| Hybrid RRF + Reranker `Recall@5` vs BM25 | Positive uplift verified | Diagnostic + Gate |
