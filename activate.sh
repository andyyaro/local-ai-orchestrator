#!/bin/bash
# Run this from the project root to activate the virtual environment:
# source activate.sh

cd "$(dirname "${BASH_SOURCE[0]}")"
source .venv/bin/activate

# Load .env if it exists. This is mainly for future API providers.
# The default build uses local Ollama and does not require API keys.
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "Virtual environment activated: $(python --version)"
echo "Ollama server check: $(curl -s http://localhost:11434 || echo 'NOT RUNNING')"
