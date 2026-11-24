# -*- coding: utf-8 -*-
"""
Deterministic Validator for Google's 4-Layer Production Agent Harness
=====================================================================
Verifies that ZERO Antigravity rules, skills, subagents, or hooks suffer from
silent syntax rejection (camelCase triggers, >24KB size, >1024-char descriptions,
broken JSON, or non-executable hook scripts) and tests live PreToolUse blocking!
"""

import json
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VALID_RULE_TRIGGERS = {"always_on", "model_decision", "glob", "manual"}


def _parse_frontmatter(md_text: str) -> tuple[dict, str]:
    if not md_text.startswith("---\n"):
        return {}, md_text
    end = md_text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Unclosed YAML frontmatter delimiter")
    raw_yaml = md_text[4:end]
    body = md_text[end + 5 :]
    meta: dict = {}
    cur_list_key = None
    for line in raw_yaml.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if cur_list_key is None:
                raise ValueError(f"Orphan list item in YAML: {line}")
            meta.setdefault(cur_list_key, []).append(line.split("- ", 1)[1].strip().strip("\"'"))
            continue
        if ":" not in line:
            raise ValueError(f"Invalid YAML line: {line}")
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip().strip("\"'")
        meta[k] = [] if v == "" else v
        cur_list_key = k if v == "" else None
    return meta, body


def main() -> int:
    errors: list[str] = []

    # 1. Validate root AGENTS.md (<12 KB, NO YAML frontmatter)
    agents_md = BASE_DIR / "AGENTS.md"
    if not agents_md.is_file():
        errors.append("Missing root AGENTS.md")
    else:
        txt = agents_md.read_text(encoding="utf-8")
        sz = len(txt.encode("utf-8"))
        if txt.startswith("---\n"):
            errors.append("AGENTS.md must NOT contain YAML frontmatter")
        if sz > 12_000:
            errors.append(f"AGENTS.md exceeds 12 KB budget ({sz} bytes)")

    # 2. Validate flat .agents/rules/*.md (snake_case triggers, <24 KB, no nested subdirs)
    rules_dir = BASE_DIR / ".agents" / "rules"
    rule_files = sorted(rules_dir.glob("*.md")) if rules_dir.is_dir() else []
    if len(rule_files) < 3:
        errors.append(f"Expected >= 3 flat rule files in .agents/rules/, found {len(rule_files)}")
    for item in (rules_dir.iterdir() if rules_dir.is_dir() else []):
        if item.is_dir():
            errors.append(f"Unregistered subdirectory in .agents/rules/: {item.name}")
    for rf in rule_files:
        raw = rf.read_text(encoding="utf-8")
        if len(raw.encode("utf-8")) > 24_000:
            errors.append(f"Rule {rf.name} exceeds 24,000-byte limit")
        fm, _ = _parse_frontmatter(raw)
        if not fm:
            errors.append(f"Rule {rf.name} is missing YAML frontmatter")
        for key in fm:
            if re.search(r"[A-Z]", key):
                errors.append(f"Rule {rf.name} uses camelCase key '{key}' (causes silent discard!)")
        trig = fm.get("trigger", "")
        if trig not in VALID_RULE_TRIGGERS:
            errors.append(f"Rule {rf.name} has invalid trigger '{trig}'")
        if not fm.get("description"):
            errors.append(f"Rule {rf.name} missing description")

    # 3. Validate 4 Progressive-Disclosure Skills (.agents/skills/*/SKILL.md, desc < 1024 chars)
    skills_dir = BASE_DIR / ".agents" / "skills"
    expected_skills = {"ilmi-rag-pipeline", "ilmi-eval-scorer", "dev-component-inspector", "urdu-rtl-visual-qa"}
    found_skills = set()
    if skills_dir.is_dir():
        for sd in sorted(skills_dir.iterdir()):
            if not sd.is_dir():
                continue
            sk_md = sd / "SKILL.md"
            if not sk_md.is_file():
                errors.append(f"Skill {sd.name} missing SKILL.md")
                continue
            found_skills.add(sd.name)
            fm, _ = _parse_frontmatter(sk_md.read_text(encoding="utf-8"))
            if fm.get("name") != sd.name:
                errors.append(f"Skill {sd.name} YAML name mismatch: {fm.get('name')}")
            desc = fm.get("description", "")
            if not desc or len(desc) >= 1024:
                errors.append(f"Skill {sd.name} description length invalid ({len(desc)} chars; must be 1..1023)")
    missing_sk = expected_skills - found_skills
    if missing_sk:
        errors.append(f"Missing required skills: {sorted(missing_sk)}")

    # 4. Validate .agents/agents/ilmi-code-auditor.md (read-only tools only!)
    auditor_md = BASE_DIR / ".agents" / "agents" / "ilmi-code-auditor.md"
    if not auditor_md.is_file():
        errors.append("Missing .agents/agents/ilmi-code-auditor.md")
    else:
        fm, _ = _parse_frontmatter(auditor_md.read_text(encoding="utf-8"))
        tools = set(fm.get("tools") or [])
        forbidden_write = tools & {"write_to_file", "replace_file_content", "multi_replace_file_content"}
        if forbidden_write:
            errors.append(f"Auditor subagent must be read-only, found write tools: {forbidden_write}")

    # 5. Validate .agents/hooks.json & test live PreToolUse Slopsquatting + Anti-Tampering decisions!
    hooks_json = BASE_DIR / ".agents" / "hooks.json"
    if not hooks_json.is_file():
        errors.append("Missing .agents/hooks.json")
    else:
        hdata = json.loads(hooks_json.read_text(encoding="utf-8"))
        guard_cfg = hdata.get("ilmi-supply-chain-and-test-guard") or {}
        if not guard_cfg.get("enabled"):
            errors.append("Hook group ilmi-supply-chain-and-test-guard is not enabled")

        # Test A: Slopsquatting package install -> must return "force_ask"
        r_slop = subprocess.run(
            [str(BASE_DIR / "scripts/hooks/guard-commands.sh")],
            input=json.dumps({"tool_input": {"CommandLine": "pip install hallucinated-hadith-pkg"}}),
            text=True,
            capture_output=True,
            check=True,
        )
        if json.loads(r_slop.stdout).get("decision") != "force_ask":
            errors.append(f"Slopsquatting guard failed to return force_ask: {r_slop.stdout}")

        # Test B: Destructive --no-verify or deleting evals -> must return "deny"
        r_deny = subprocess.run(
            [str(BASE_DIR / "scripts/hooks/guard-commands.sh")],
            input=json.dumps({"tool_input": {"CommandLine": "rm -rf evals/"}}),
            text=True,
            capture_output=True,
            check=True,
        )
        if json.loads(r_deny.stdout).get("decision") != "deny":
            errors.append(f"Destructive command guard failed to return deny: {r_deny.stdout}")

        # Test C: Writing .env secret -> must return "deny"
        r_env = subprocess.run(
            [str(BASE_DIR / "scripts/hooks/guard-secrets-and-tests.sh")],
            input=json.dumps({"tool_input": {"TargetFile": "/app/.env", "CodeContent": "SECRET=1"}}),
            text=True,
            capture_output=True,
            check=True,
        )
        if json.loads(r_env.stdout).get("decision") != "deny":
            errors.append(f".env secret guard failed to return deny: {r_env.stdout}")

        # Test D: Weakening assertions in evals/ -> must return "force_ask"
        r_tamper = subprocess.run(
            [str(BASE_DIR / "scripts/hooks/guard-secrets-and-tests.sh")],
            input=json.dumps({
                "tool_input": {
                    "TargetFile": "/app/evals/run_all_evals.py",
                    "TargetContent": "assert score >= 0.85\nassert count > 0",
                    "ReplacementContent": "pass",
                }
            }),
            text=True,
            capture_output=True,
            check=True,
        )
        if json.loads(r_tamper.stdout).get("decision") != "force_ask":
            errors.append(f"Test tampering guard failed to return force_ask: {r_tamper.stdout}")

    if errors:
        for e in errors:
            print(f"[HARNESS FAIL] {e}")
        return 1

    print(
        f"[HARNESS PASS] AGENTS.md ({len(agents_md.read_bytes())} B), "
        f"{len(rule_files)} snake_case rules, {len(found_skills)} progressive skills, "
        f"read-only ilmi-code-auditor, and 4/4 live PreToolUse Guardrail checks PASSED!"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
