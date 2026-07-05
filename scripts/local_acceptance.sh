#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Lightweight smoke test: verifies Ollama is reachable and the pipeline
# runs end-to-end with a small local model, completing (or failing safely)
# without crashing. This intentionally does NOT require a tiny model like
# llama3.2:3b to satisfy a strict output-quality constraint (e.g. an exact
# word count) -- that is scripts/strict_acceptance.sh's job. A small model
# correctly detecting and reporting its own constraint violation is a
# PASS for this smoke test, not a failure.

echo "=== Local Acceptance (smoke test) ==="

curl --fail http://localhost:11434 > /dev/null
echo "  Ollama reachable."

# --max-loops 3 (not 1): leaves room for the Phase 6c repair loop to run a
# Critic/Fixer pass before giving up, so the run exercises the real repair
# path rather than stopping after a single attempt.
python run.py \
  --goal "Write a 50-word summary of why sleep matters." \
  --model-main llama3.2:3b \
  --model-fast llama3.2:3b \
  --max-loops 3 \
  --threshold 50

latest_run=$(ls -td runs/*/ | head -1)
test -f "${latest_run}run_summary.json"
test -f "${latest_run}final_output.txt"
echo "  Pipeline completed: run_summary.json and final_output.txt produced."

# Regression guard for the Phase 6b silent-pass bug: the pipeline must
# never report passed=true for output that actually violates the stated
# constraint. This does NOT require llama3.2:3b to satisfy the strict
# 50-word constraint itself (small models routinely can't, and the system
# correctly detecting and reporting that as a failure is expected, healthy
# behavior) -- it only requires that self-reported status never lies.
python -c "
import json
import sys
from orchestrator.validators import check_word_limit

with open('${latest_run}run_summary.json', encoding='utf-8') as f:
    summary = json.load(f)

final_output = open('${latest_run}final_output.txt', encoding='utf-8').read()
result = check_word_limit(final_output, limit=50, mode='exact', tolerance=20)
reported_passed = summary.get('passed')

print(f'    real validator     : {result.detail}')
print(f'    run_summary.passed : {reported_passed}')
print(f'    stop_reason        : {summary.get(\"stop_reason\")}')

if result.passed is False and reported_passed is True:
    print('    SMOKE TEST FAILURE: pipeline reported passed=true for output')
    print('    that the real validator says violates the constraint -- this')
    print('    is the Phase 6b silent-pass regression.')
    sys.exit(1)

print('    OK: no silent-pass regression. A small model failing to hit an')
print('    exact word count and safely reporting that failure is expected')
print('    -- see scripts/strict_acceptance.sh for a strict quality check.')
"

echo "Local acceptance (smoke test) passed: ${latest_run}"
