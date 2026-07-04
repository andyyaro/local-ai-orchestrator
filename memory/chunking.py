"""
memory/chunking.py

Simple, deterministic text chunking for Phase 9 retrieval.
"""


def chunk_text(text: str, chunk_size_tokens: int = 512) -> list[str]:
    """
    Split `text` into chunks of roughly `chunk_size_tokens` words each,
    splitting on paragraph boundaries and merging small paragraphs up to
    the target size, rather than cutting mid-sentence.

    A "token" here is approximated as one whitespace-separated word --
    this is not real tokenization (which varies by model and is usually
    finer-grained than whole words), but is a simple, deterministic
    approximation that keeps retrieval chunks a roughly consistent size.

    Returns an empty list for empty/whitespace-only text, and a single
    chunk for text shorter than one chunk_size_tokens.
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current_parts: list[str] = []
    current_word_count = 0

    for paragraph in paragraphs:
        paragraph_word_count = len(paragraph.split())

        if current_word_count and current_word_count + paragraph_word_count > chunk_size_tokens:
            chunks.append("\n\n".join(current_parts))
            current_parts = []
            current_word_count = 0

        current_parts.append(paragraph)
        current_word_count += paragraph_word_count

        # A paragraph that alone reaches the target size becomes its own
        # chunk immediately, rather than accumulating past the target
        # waiting for a natural paragraph boundary that may never come.
        if current_word_count >= chunk_size_tokens:
            chunks.append("\n\n".join(current_parts))
            current_parts = []
            current_word_count = 0

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks
