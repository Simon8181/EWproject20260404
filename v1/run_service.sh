#!/usr/bin/env bash
# 在终端保持运行；浏览器访问 http://127.0.0.1:8000/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
exec python -m uvicorn function.ew_service:app --host 127.0.0.1 --port 8000 --reload
