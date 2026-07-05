#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Strict acceptance test: a genuine output-quality gate, not a smoke test.
# Uses a stronger local model (llama3.1:8b) than scripts/local_acceptance.sh
# and actually requires the final output to satisfy a precise constraint
# (an exact word count, with tolerance). This is expected to be slower and
# more model-dependent than the smoke test, and is OPTIONAL/RECOMMENDED for
# the immediate v2.0 tag, not a required release gate -- see README.md's
# "Release gates" section.
#
# This script never pulls a model automatically. If the required model is
# missing, it reports exactly which `ollama pull` command to run and exits.

STRICT_MODEL="llama3.1:8b"

echo "=== Strict Acceptance (quality gate) ==="

curl --fail http://localhost:11434 > /dev/null
echo "  Ollama reachable."

if ! ollama list | awk '{print $1}' | grep -qx "${STRICT_MODEL}"; then
  echo
  echo "  SKIPPED: required model '${STRICT_MODEL}' is not pulled locally."
  echo "  This script never downloads models automatically."
  echo "  To run this check, pull it yourself first:"
  echo
  echo "      ollama pull ${STRICT_MODEL}"
  echo
  echo "  Then re-run: bash scripts/strict_acceptance.sh"
  exit 2
fi
echo "  Required model '${STRICT_MODEL}' is available."

python run.py \
  --goal "Write a 50-word summary of why sleep matters." \
  --model-main "${STRICT_MODEL}" \
  --model-fast "${STRICT_MODEL}" \
  --max-loops 3 \
  --threshold 50

latest_run=$(ls -td runs/*/ | head -1)
test -f "${latest_run}run_summary.json"
test -f "${latest_run}final_output.txt"

# The actual quality gate: the final output must genuinely satisfy the
# stated constraint. Unlike scripts/local_acceptance.sh, this is allowed
# to fail the run if the constraint is violated -- that is the entire
# point of this stricter check.
python -c "
import json
import sys
from orchestrator.validators import check_word_limit

with open('${latest_run}run_summary.json', encoding='utf-8') as f:
    summary = json.load(f)

final_output = open('${latest_run}final_output.txt', encoding='utf-8').read()
result = check_word_limit(final_output, limit=50, mode='exact', tolerance=20)

print(f'    real validator     : {result.detail}')
print(f'    run_summary.passed : {summary.get(\"passed\")}')
print(f'    stop_reason        : {summary.get(\"stop_reason\")}')

if not result.passed:
    print()
    print('    STRICT ACCEPTANCE FAILURE: final output violates the required')
    print('    50-word (+/-20 tolerance) constraint even with a stronger')
    print('    model. This is a genuine quality gate failure, not expected')
    print('    behavior -- investigate before treating this as a known issue.')
    sys.exit(1)

print('    OK: final output satisfies the strict word-count constraint.')
"

echo "Strict acceptance passed: ${latest_run}"
