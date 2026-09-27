import json
import math
from pathlib import Path

from app.db.database import get_connection


class EvaluationService:
    def __init__(self) -> None:
        self.latest_results = {}

    @staticmethod
    def _has_location(value: str | None) -> bool:
        if not value:
            return False
        try:
            coordinates = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            coordinates = value.strip().strip("[]()").split(",")
        if isinstance(coordinates, dict):
            coordinates = [
                coordinates.get("lat", coordinates.get("latitude")),
                coordinates.get("lon", coordinates.get("longitude")),
            ]
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            return False
        try:
            point = [float(coordinates[0]), float(coordinates[1])]
        except (TypeError, ValueError):
            return False
        return all(math.isfinite(value) for value in point) and any(abs(value) > 1e-9 for value in point)

    @staticmethod
    def _label_count(labels_dir: Path, filename: str) -> int:
        try:
            labels = json.loads((labels_dir / filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        return len(labels) if isinstance(labels, (list, dict)) else 0

    def run_evaluation(self, limit: int = 10) -> dict:
        conn = get_connection()
        scenes = conn.execute("SELECT id FROM scenes").fetchall()
        tiles = conn.execute("SELECT centroid, image_path FROM tiles").fetchall()
        scene_count = len(scenes)
        tile_count = len(tiles)
        change_count = conn.execute("SELECT COUNT(*) FROM change_detections").fetchone()[0]
        scenes_with_provenance = conn.execute(
            "SELECT COUNT(DISTINCT p.entity_id) FROM provenance p "
            "JOIN scenes s ON s.id = p.entity_id WHERE p.entity_type = 'scene'"
        ).fetchone()[0]
        conn.close()

        labels_dir = Path(__file__).resolve().parents[3] / "data" / "labels"
        ground_truth = {
            "retrieval_queries": self._label_count(labels_dir, "retrieval_queries.json"),
            "change_labels": self._label_count(labels_dir, "change_labels.json"),
            "quality_labels": self._label_count(labels_dir, "quality_labels.json"),
        }
        result = {
            "status": "diagnostics_complete",
            "message": "Coverage diagnostics completed. Model-quality scores are not computed without labeled evaluation data.",
            "limit": limit,
            "scene_count": scene_count,
            "tile_count": tile_count,
            "change_count": change_count,
            "ground_truth": ground_truth,
            "coverage": {
                "images": {"available": sum(Path(tile["image_path"]).is_file() for tile in tiles if tile["image_path"]), "total": tile_count},
                "locations": {"available": sum(self._has_location(tile["centroid"]) for tile in tiles), "total": tile_count},
                "provenance": {"available": scenes_with_provenance, "total": scene_count},
            },
            "quality_metrics": None,
        }
        self.latest_results = result
        return result

    def get_latest_results(self) -> dict:
        return self.latest_results or {"status": "No evaluation run yet"}
