---
name: dev-component-inspector
description: Generates and updates the development-only Component Inspector mode (?__inspector=1) for isolated visual QA of Hadith cards, Nastaliq clipping tests, StagedProposalCard diffs, Abstention states, and 3-Tier Memory cards with zero impact on production users.
---
# Dev-Only Component Inspector Skill

1. **Zero Production Surface**: Activate the inspector ONLY when `location.search.includes("__inspector=1")` or `location.hash === "#__inspector"`. Normal users experience zero extra DOM nodes or network requests.
2. **Required Isolated States**:
   - Vocalized Arabic + Salafi Urdu Hadith Card (`Sahih` & `Da'if` badges)
   - Nastaliq `ک/گ` Ascender/Descender Clipping Torture Sample (`line-height >= 2.25`)
   - `<StagedProposalCard />` (`pending` Diff + Risk Summary + Approve/Reject)
   - Hybrid RAG Abstention Alert (`score < 0.22`)
   - 3-Tier Living Memory Row (`valid_from`, `superseded_by`, `[حذف کریں]`)
   - Rekhta & Qari Lexicon Entry Card (`<bdi>` BiDi root & metadata)
3. See `references/inspector-guide.md` for usage and extension steps.
