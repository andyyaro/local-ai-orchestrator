"""
test_ollama.py

Simplest possible test: send one prompt to a local Ollama model and print
the response. Run this to confirm Python can communicate with Ollama before
building the full pipeline.

Usage:
    python test_ollama.py
"""

import requests
import json
import sys


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
PROMPT = "In exactly two sentences, explain what a neural network is."


def call_ollama(model: str, prompt: str, url: str = OLLAMA_URL) -> str:
    """Send a prompt to Ollama and return the complete response text."""

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Could not connect to Ollama.")
        print("  Make sure Ollama is running: open the Ollama app or run 'ollama serve'")
        print("  Then verify with: curl http://localhost:11434")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\n[ERROR] Request timed out after 120 seconds.")
        print("  The model may be too large or your Mac is under memory pressure.")
        print("  Try: ollama run llama3.2:3b 'hello' in Terminal to test directly.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] HTTP error from Ollama: {e}")
        print(f"  Status code: {response.status_code}")
        print(f"  Response body: {response.text[:500]}")
        sys.exit(1)

    data = response.json()
    return data.get("response", "").strip()


def main():
    print(f"Model  : {MODEL}")
    print(f"Prompt : {PROMPT}")
    print("-" * 60)
    print("Calling Ollama... (may take 10–30 seconds on first load)")
    print()

    result = call_ollama(MODEL, PROMPT)

    print("Response:")
    print(result)
    print()
    print("[SUCCESS] Ollama is working correctly.")


if __name__ == "__main__":
    main()
