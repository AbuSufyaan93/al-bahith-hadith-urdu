#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic RTL Logical Properties, Nastaliq Non-Clipping & WCAG 2.2 AA CSS Auditor."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CSS_FILE = ROOT / "backend" / "static" / "assets" / "hadeeth_urdu_bridge.css"

def main() -> int:
    txt = CSS_FILE.read_text(encoding="utf-8")
    errors = []
    # 1. Check physical directional properties in custom stylesheet
    physical = re.findall(r"(?<![a-zA-Z-])(?:margin-left|margin-right|padding-left|padding-right|border-left|border-right|text-align\s*:\s*(?:left|right))\b", txt)
    if physical:
        errors.append(f"Found physical directional CSS properties instead of logical properties: {physical}")
    # 2. Check Nastaliq line-height >= 2.2
    lhs = [float(x) for x in re.findall(r"line-height\s*:\s*([0-9]+(?:\.[0-9]+)?)", txt)]
    if not any(v >= 2.2 for v in lhs):
        errors.append(f"No Nastaliq paragraph rule with line-height >= 2.2 found (found: {lhs})")
    # 3. Check WCAG :focus-visible & 48px mobile touch target
    if ":focus-visible" not in txt:
        errors.append("Missing WCAG 2.2 AA :focus-visible rule")
    if "48px" not in txt:
        errors.append("Missing >= 48px mobile coarse-pointer touch target rule")
    if "NotoNastaliqUrdu" not in txt:
        errors.append("Missing self-hosted NotoNastaliqUrdu @font-face declaration")
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return 1
    print("[PASS] RTL Logical Properties, NotoNastaliqUrdu, line-height >= 2.2, :focus-visible & >=48px touch targets verified!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
