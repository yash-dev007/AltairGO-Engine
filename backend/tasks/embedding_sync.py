"""
tasks/embedding_sync.py — Nightly Embedding Sync Task
═══════════════════════════════════════════════════════

Celery task wrapper for generate_embeddings.py.
Runs nightly after destination enrichment to keep embeddings fresh for
newly added or updated destinations.
"""

import structlog

log = structlog.get_logger(__name__)


def sync_embeddings() -> dict:
    """
    Generate embeddings for any destinations missing them.
    Called by the Celery beat schedule and also by run_embedding_sync task.
    """
    from backend.scripts.generate_embeddings import run_embedding_generation

    result = run_embedding_generation()
    log.info("embedding_sync.done", **result)
    return result
