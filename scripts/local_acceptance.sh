#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

curl --fail http://localhost:11434

python run.py \
  --goal "Write a 50-word summary of why sleep matters." \
  --model-main llama3.2:3b \
  --model-fast llama3.2:3b \
  --max-loops 1 \
  --threshold 50

latest_run=$(ls -td runs/*/ | head -1)
test -f "${latest_run}run_summary.json"
test -f "${latest_run}final_output.txt"

# Regression guard for the Phase 6b bug: a Supervisor that drops the
# 50-word constraint from its refined goal must not let a long essay pass
# this smoke test silently. Reuse the real validator logic (not a
# duplicated bash word-count check) so this stays in sync with whatever
# tolerance orchestrator/validators.py actually enforces.
python -c "
import sys
from orchestrator.validators import check_word_limit

final_output = open('${latest_run}final_output.txt', encoding='utf-8').read()
result = check_word_limit(final_output, limit=50, mode='exact', tolerance=20)
print(f'    word count check: {result.detail}')
sys.exit(0 if result.passed else 1)
"

echo "Local acceptance check passed: ${latest_run}"
