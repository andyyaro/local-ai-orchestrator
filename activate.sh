#!/bin/bash
# Run this from the project root to activate the virtual environment:
# source activate.sh

cd "$(dirname "${BASH_SOURCE[0]}")"
source .venv/bin/activate
echo "Virtual environment activated: $(python --version)"
echo "Ollama server check: $(curl -s http://localhost:11434 || echo 'NOT RUNNING')"
