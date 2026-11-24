#!/usr/bin/env bash
# Layer 2 Guard: PreToolUse hook for run_command
# Blocks destructive commands ("deny") and intercepts unverified package installs ("force_ask") to prevent Slopsquatting.
set -euo pipefail

PAYLOAD="$(cat || true)"
python3 - "$PAYLOAD" <<'PY'
import json
import re
import sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
cmd = ""
try:
    data = json.loads(raw) if raw.strip() else {}
    inp = data.get("tool_input") or data.get("parameters") or data
    cmd = str(inp.get("CommandLine") or inp.get("command") or "")
except Exception:
    cmd = raw

# 1. Hard-block destructive / anti-verification commands
deny_patterns = [
    (r"\brm\s+-rf\s+/(?:\s|$)", "Blocked destructive root deletion (rm -rf /)."),
    (r"--no-verify\b", "Blocked bypassing Git verification hooks (--no-verify)."),
    (r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*\s+.*(?:evals/|verify_platform\.py)", "Blocked deleting evaluation or verification suites (Anti-Reward-Hacking)."),
]
for pat, reason in deny_patterns:
    if re.search(pat, cmd):
        print(json.dumps({"decision": "deny", "reason": reason}))
        sys.exit(0)

# 2. Force human approval on unpinned/ad-hoc package installation (Slopsquatting defense)
install_pat = r"\b(?:pip|pip3)\s+install\b|\b(?:npm|pnpm)\s+(?:install|add|i)\b|\byarn\s+add\b|\buv\s+(?:add|pip\s+install)\b"
if re.search(install_pat, cmd) and "-r requirements.txt" not in cmd:
    print(json.dumps({
        "decision": "force_ask",
        "reason": "Slopsquatting Supply-Chain Guard: Verify package publisher, age, and download count before installing."
    }))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
PY
