"""
scripts/generate_embeddings.py — Destination Embedding Generator
═════════════════════════════════════════════════════════════════

Generates 384-dim text embeddings for all Destination rows that don't
have one yet, using the local all-MiniLM-L6-v2 model via sentence-transformers.

No API key required — runs fully in-process.

Embeddings enable semantic similarity in the discovery engine:
  - "Find places with old architecture and peaceful vibes"
  - "Travelers who liked Udaipur also liked Jodhpur"

Usage:
  python -m backend.scripts.generate_embeddings

The script is also called nightly by the embedding_sync Celery task.
"""

import os
import structlog

log = structlog.get_logger(__name__)

BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
MODEL_NAME = "all-MiniLM-L6-v2"

_model = None


def _get_model():
    """Lazy-load the sentence-transformers model (cached after first call)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info("embedding.model_loading", model=MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        log.info("embedding.model_ready", model=MODEL_NAME)
    return _model


def _build_destination_text(destination) -> str:
    """Construct a rich text representation of a destination for embedding."""
    parts = [destination.name or ""]
    if destination.description:
        parts.append(destination.description[:300])
    elif destination.desc:
        parts.append(destination.desc[:300])
    vibe_tags = destination.vibe_tags or []
    if vibe_tags:
        parts.append(f"Vibes: {', '.join(vibe_tags)}")
    highlights = destination.highlights or []
    if highlights:
        parts.append(f"Highlights: {', '.join(str(h) for h in highlights[:5])}")
    budget_category = destination.budget_category or ""
    if budget_category:
        parts.append(f"Budget: {budget_category}")
    traveler_types = destination.compatible_traveler_types or []
    if traveler_types:
        parts.append(f"Best for: {', '.join(traveler_types)}")
    return " | ".join(p for p in parts if p)


def run_embedding_generation() -> dict:
    """
    Main entry point: generate embeddings for all destinations without one.
    Returns {generated: N, skipped: N, failed: N}.
    """
    from backend.database import SessionLocal
    from backend.models import Destination

    session = SessionLocal()
    generated = skipped = failed = 0

    try:
        destinations = (
            session.query(Destination)
            .filter(Destination.embedding.is_(None))
            .limit(500)
            .all()
        )

        if not destinations:
            log.info("embedding.all_up_to_date")
            return {"generated": 0, "skipped": 0, "failed": 0}

        model = _get_model()

        for batch_start in range(0, len(destinations), BATCH_SIZE):
            batch = destinations[batch_start: batch_start + BATCH_SIZE]
            texts = [_build_destination_text(d) for d in batch]

            try:
                vectors = model.encode(
                    texts,
                    batch_size=BATCH_SIZE,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
            except Exception as exc:
                log.warning("embedding.encode_failed", error=str(exc))
                failed += len(batch)
                continue

            for dest, vector in zip(batch, vectors):
                try:
                    dest.embedding = vector.tolist()
                    generated += 1
                except Exception as exc:
                    log.warning("embedding.set_failed", dest_id=dest.id, error=str(exc))
                    failed += 1

            session.commit()
            log.info(
                "embedding.batch_done",
                batch_start=batch_start,
                batch_size=len(batch),
                generated=generated,
            )

        result = {"generated": generated, "skipped": skipped, "failed": failed}
        log.info("embedding.generation_complete", **result)
        return result

    except Exception:
        session.rollback()
        log.exception("embedding.generation_failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_embedding_generation()
