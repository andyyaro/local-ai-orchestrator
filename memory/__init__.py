"""
memory/

Phase 9 retrieval and long-context-equivalent memory: local embeddings
plus hybrid keyword/vector search over prior run history and project
files, stored entirely in SQLite (orchestrator/database.py's
memory_chunks table). Off by default -- see config/models.yaml's
`memory.retrieval_enabled`.
"""
