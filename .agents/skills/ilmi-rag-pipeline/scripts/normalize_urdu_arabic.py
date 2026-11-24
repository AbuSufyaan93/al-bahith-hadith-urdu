#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI utility for Dual-Field Urdu/Arabic normalization check (0 LLM tokens)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.normalizer import normalize_arabic_search, normalize_urdu_search

if __name__ == "__main__":
    sample = " ".join(sys.argv[1:]) or "قَالَ رَسُولُ ﷲِ ﷺ: إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ — ﻻ ضرر ولا ضرار"
    print(json.dumps({
        "canonical_text": sample,
        "arabic_search_norm": normalize_arabic_search(sample),
        "urdu_search_norm": normalize_urdu_search(sample),
    }, ensure_ascii=False, indent=2))
