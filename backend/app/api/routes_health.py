from fastapi import APIRouter

from app.core.config import settings
from app.db.database import get_connection

router = APIRouter()


@router.get("/health")
def health() -> dict:
    conn = get_connection()
    try:
        conn.execute("SELECT 1")
        db_status = "Connected"
    except Exception:
        db_status = "Unavailable"
    finally:
        conn.close()
    return {
        "status": "ok",
        "database": db_status,
        "offline_mode": settings.offline_mode,
        "model": settings.embedding_model,
    }


@router.get("/stats")
def stats() -> dict:
    conn = get_connection()
    try:
        scene_count = conn.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
        tile_count = conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
        change_count = conn.execute("SELECT COUNT(*) FROM change_detections").fetchone()[0]
        pending_reviews = conn.execute(
            "SELECT COUNT(*) FROM change_detections c LEFT JOIN analyst_reviews r ON c.id = r.change_id WHERE r.id IS NULL"
        ).fetchone()[0]
        high_confidence = conn.execute(
            "SELECT COUNT(*) FROM change_detections WHERE confidence >= 0.8"
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "total_scenes": scene_count,
        "total_tiles": tile_count,
        "indexed_images": tile_count,
        "detected_changes": change_count,
        "pending_reviews": pending_reviews,
        "high_confidence_changes": high_confidence,
    }
