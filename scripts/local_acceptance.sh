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
echo "Local acceptance check passed: ${latest_run}"
