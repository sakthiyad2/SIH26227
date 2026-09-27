import json
import uuid
from pathlib import Path

import numpy as np

from app.db.database import get_connection
from app.ml.change_model import BaselineChangeDetector
from app.ml.quality_model import QualityModel
from app.services.false_alarm_service import FalseAlarmService
from app.services.preprocessing_service import PreprocessingService


class ChangeDetectionService:
    def __init__(self) -> None:
        self.detector = BaselineChangeDetector()
        self.quality_model = QualityModel()
        self.preprocessor = PreprocessingService()
        self.false_alarm_service = FalseAlarmService()

    def detect_change(self, payload: dict) -> dict:
        scene_a_id = payload["scene_a_id"]
        scene_b_id = payload["scene_b_id"]
        conn = get_connection()
        scene_a = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_a_id,)).fetchone()
        scene_b = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_b_id,)).fetchone()
        if scene_a is None or scene_b is None:
            conn.close()
            raise ValueError("Both scenes must exist")
        before_path = scene_a["file_path"]
        after_path = scene_b["file_path"]
        conn.close()

        before, after = self.preprocessor.align_and_resample(before_path, after_path)
        before, after, quality_mask = self.preprocessor.apply_quality_masks(before, after)
        change_mask = self.detector.detect(before, after)
        filtered_mask = self.false_alarm_service.suppress_false_alarms(change_mask, quality_mask)
        quality_score = self.quality_model.score(
            cloud_cover=0.05,
            valid_pixels=float(np.mean(quality_mask)),
            registration_quality=0.92,
            illumination_consistency=0.88,
            overlap_ratio=0.91,
            sensor_compatibility=0.9,
        )
        confidence = self.detector.calculate_confidence(filtered_mask, quality_score)
        change_type = self.detector.classify_change(before, after)
        changed_area = float(np.mean(filtered_mask > 0))
        earliest_supporting_observation = scene_b["acquisition_datetime"]
        change_id = str(uuid.uuid4())

        conn = get_connection()
        conn.execute(
            "INSERT INTO change_detections (id, scene_a_id, scene_b_id, tile_a_id, tile_b_id, change_type, confidence, quality_score, changed_area, earliest_supporting_observation, metadata, change_map_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                change_id,
                scene_a_id,
                scene_b_id,
                payload.get("tile_a_id"),
                payload.get("tile_b_id"),
                change_type,
                confidence,
                quality_score,
                changed_area,
                earliest_supporting_observation,
                json.dumps({"quality_mask": bool(np.any(quality_mask)), "source": "baseline"}),
                str(Path(scene_b["file_path"]).with_suffix(".change.png")),
            ),
        )
        conn.execute(
            "INSERT INTO quality_metrics (id, change_id, cloud_coverage, valid_pixels, registration_quality, illumination_consistency, overlap_ratio, sensor_compatibility, quality_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                change_id,
                0.05,
                float(np.mean(quality_mask)),
                0.92,
                0.88,
                0.91,
                0.9,
                quality_score,
            ),
        )
        conn.commit()
        conn.close()
        return {
            "change_id": change_id,
            "change_type": change_type,
            "confidence": confidence,
            "quality_score": quality_score,
            "changed_area_percentage": changed_area * 100,
            "earliest_supporting_observation": earliest_supporting_observation,
            "scene_a_id": scene_a_id,
            "scene_b_id": scene_b_id,
        }

    def list_changes(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM change_detections ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_change(self, change_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM change_detections WHERE id = ?", (change_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
