#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/evals/run_all_evals.py" "$@"
