"""
memory/indexer.py

Indexes prior pipeline runs and project files into memory_chunks for
Phase 9 retrieval. Only meaningful when memory.retrieval_enabled is true
-- see run.py's wiring and memory/retriever.py's retrieve_context().
"""

import struct
from pathlib import Path

from memory.chunking import chunk_text
from memory.embeddings import embed
from orchestrator.config_loader import get_memory_config, get_model_for_role
from orchestrator.database import load_run_by_id, save_memory_chunk


def _pack_embedding(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def index_run(run_id: int) -> int:
    """
    Chunk and embed a completed run's final_output, storing each chunk in
    memory_chunks with source_type="run". Returns the number of chunks
    indexed (0 if the run doesn't exist or has no final_output).
    """
    run = load_run_by_id(run_id)
    if not run or not run.get("final_output"):
        return 0

    chunk_size = get_memory_config().get("chunk_size_tokens", 512)
    chunks = chunk_text(run["final_output"], chunk_size_tokens=chunk_size)

    for chunk in chunks:
        vector = embed(chunk)
        save_memory_chunk(
            source_type="run", source_ref=str(run_id),
            chunk_text=chunk, embedding=_pack_embedding(vector),
        )
    return len(chunks)


def index_project_file(path: str) -> int:
    """
    Chunk and embed a project file's text contents, storing each chunk in
    memory_chunks with source_type="project_file". Returns the number of
    chunks indexed (0 if the file doesn't exist or isn't a regular file).
    """
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return 0

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    chunk_size = get_memory_config().get("chunk_size_tokens", 512)
    chunks = chunk_text(text, chunk_size_tokens=chunk_size)

    for chunk in chunks:
        vector = embed(chunk)
        save_memory_chunk(
            source_type="project_file", source_ref=str(file_path),
            chunk_text=chunk, embedding=_pack_embedding(vector),
        )
    return len(chunks)


def summarize_run(run_id: int) -> str:
    """
    Generate a short model-produced summary of a past run's goal and
    outcome ("reflection memory"), using a cheap local role model (a real
    generation task, unlike the rest of this module, which is
    deterministic chunking/embedding). Returns an empty string if the run
    doesn't exist.
    """
    run = load_run_by_id(run_id)
    if not run:
        return ""

    from orchestrator.resilience import call_with_resilience

    model = get_model_for_role("planner", run.get("mode", "general"))
    prompt = (
        "Summarize this pipeline run in 2-3 sentences: what the goal was, "
        "what was produced, and whether it passed. Be concise.\n\n"
        f"GOAL: {run['goal']}\n"
        f"MODE: {run.get('mode', 'general')}\n"
        f"FINAL SCORE: {run.get('final_score', 0)}/100\n"
        f"PASSED: {run.get('passed', False)}\n"
        f"STOP REASON: {run.get('stop_reason', '')}\n"
    )
    return call_with_resilience(
        model=model, prompt=prompt, temperature=0.3, num_ctx=2048, role="planner",
    )
