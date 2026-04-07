#!/usr/bin/env bash
# v3 Debug Web：限制重载监视目录、略加重载延迟，减少「长时间任务进行到一半被 reload 打断」导致页面一直卡住。
# 执行超长 merge+AI 时仍建议：不加 --reload，例如：
#   python3 -m uvicorn app.web:app --host 127.0.0.1 --port 8011
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m uvicorn app.web:app --host 127.0.0.1 --port 8011 \
  --reload \
  --reload-dir "$(pwd)/app" \
  --reload-dir "$(pwd)/core" \
  --reload-delay 1.5
