import uuid
from datetime import datetime

from app.db.database import get_connection


class ReviewService:
    def get_queue(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT c.*, q.decision, q.reason
            FROM change_detections c
            LEFT JOIN analyst_reviews q
                ON q.id = (
                    SELECT q2.id
                    FROM analyst_reviews q2
                    WHERE q2.change_id = c.id
                    ORDER BY q2.processed_at DESC
                    LIMIT 1
                )
            ORDER BY c.created_at DESC
            """
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def record_decision(self, change_id: str, payload: dict) -> dict:
        decision = payload.get("decision", "reject")
        reason = payload.get("reason")
        reviewer = payload.get("reviewer", "analyst")
        run_id = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO processing_runs (id, run_type, status, notes) VALUES (?, ?, ?, ?)",
            (run_id, "analyst_review", "completed", reason),
        )
        existing = conn.execute(
            "SELECT id FROM analyst_reviews WHERE change_id = ? ORDER BY processed_at DESC LIMIT 1",
            (change_id,),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE analyst_reviews SET decision = ?, reason = ?, reviewer = ?, processing_run_id = ?, processed_at = ? WHERE id = ?",
                (decision, reason, reviewer, run_id, datetime.utcnow().isoformat(), existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO analyst_reviews (id, change_id, decision, reason, reviewer, processing_run_id) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), change_id, decision, reason, reviewer, run_id),
            )

        conn.commit()
        conn.close()
        return {
            "change_id": change_id,
            "decision": decision,
            "reason": reason,
            "reviewer": reviewer,
            "processed_at": datetime.utcnow().isoformat(),
        }
