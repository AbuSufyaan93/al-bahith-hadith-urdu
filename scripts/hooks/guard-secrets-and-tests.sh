#!/usr/bin/env bash
# Layer 2 Guard: PreToolUse hook for file edits
# Blocks writing .env secrets/API keys ("deny") and prevents weakening/deleting test assertions ("force_ask"/"deny").
set -euo pipefail

PAYLOAD="$(cat || true)"
python3 - "$PAYLOAD" <<'PY'
import json
import re
import sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
target = ""
content = ""
old_target = ""
try:
    data = json.loads(raw) if raw.strip() else {}
    inp = data.get("tool_input") or data.get("parameters") or data
    target = str(inp.get("TargetFile") or inp.get("file_path") or "")
    content = str(inp.get("CodeContent") or inp.get("ReplacementContent") or "")
    old_target = str(inp.get("TargetContent") or "")
except Exception:
    pass

# 1. Block writing .env files
if re.search(r"(?:^|/)\.env(?:\.[a-zA-Z0-9_-]+)?$", target):
    print(json.dumps({"decision": "deny", "reason": "Blocked writing .env secret file via agent tool."}))
    sys.exit(0)

# 2. Block hardcoded API keys / tokens
secret_patterns = [
    r"AIza[0-9A-Za-z\-_]{35}",
    r"ghp_[0-9A-Za-z]{36}",
    r"sk-[0-9A-Za-z]{32,}",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]
for sp in secret_patterns:
    if re.search(sp, content):
        print(json.dumps({"decision": "deny", "reason": "Blocked potential hardcoded secret/API key in file content."}))
        sys.exit(0)

# 3. Red-Green-Refactor Test Integrity Guard
if ("verify_platform.py" in target or "/evals/" in target or "/tests/" in target) and old_target:
    old_asserts = len(re.findall(r"\bassert\b", old_target))
    new_asserts = len(re.findall(r"\bassert\b", content))
    if old_asserts > 0 and new_asserts < old_asserts:
        print(json.dumps({
            "decision": "force_ask",
            "reason": f"Anti-Reward-Hacking Guard: Edit reduces assertion count ({old_asserts} -> {new_asserts}) in protected test/eval file."
        }))
        sys.exit(0)

print(json.dumps({"decision": "allow"}))
PY
