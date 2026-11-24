#!/usr/bin/env bash
# Layer 2 Guard: PostToolUse syntax & AST linter after file edits
set -euo pipefail

PAYLOAD="$(cat || true)"
python3 - "$PAYLOAD" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

raw = sys.argv[1] if len(sys.argv) > 1 else ""
target = ""
try:
    data = json.loads(raw) if raw.strip() else {}
    inp = data.get("tool_input") or data.get("parameters") or data
    target = str(inp.get("TargetFile") or inp.get("file_path") or "")
except Exception:
    pass

p = Path(target) if target else None
if p and p.is_file():
    if p.suffix == ".py":
        subprocess.run([sys.executable, "-m", "py_compile", str(p)], check=True)
    elif p.suffix == ".json":
        json.loads(p.read_text(encoding="utf-8"))
    elif p.suffix == ".js":
        subprocess.run(["node", "--check", str(p)], check=True)

print(json.dumps({"status": "ok"}))
PY
