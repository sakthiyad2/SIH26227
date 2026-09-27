import json
import uuid
from datetime import datetime

from app.db.database import get_connection


class ProvenanceService:
    def record(self, entity_type: str, entity_id: str, payload: dict) -> dict:
        provenance_id = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO provenance (id, entity_type, entity_id, input_files, input_checksums, model_name, model_version, model_source, model_license, steps, parameters, software_version, timestamp, hardware) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                provenance_id,
                entity_type,
                entity_id,
                json.dumps(payload.get("input_files", [])),
                json.dumps(payload.get("input_checksums", [])),
                payload.get("model_name", "Unspecified local model"),
                payload.get("model_version", "Not recorded"),
                payload.get("model_source", "Not recorded"),
                payload.get("model_license", "Not verified"),
                json.dumps(payload.get("steps", [])),
                json.dumps(payload.get("parameters", {})),
                payload.get("software_version", "0.1.0"),
                datetime.utcnow().isoformat(),
                payload.get("hardware", "CPU"),
            ),
        )
        conn.commit()
        conn.close()
        return {"id": provenance_id, **payload}

    def get_provenance(self, entity_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM provenance WHERE entity_id = ? ORDER BY timestamp DESC LIMIT 1", (entity_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
