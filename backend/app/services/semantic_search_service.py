import json
from pathlib import Path

import numpy as np

from app.db.database import get_connection
from app.ml.text_encoder import LocalTextEncoder
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService


class SemanticSearchService:
    def __init__(self) -> None:
        self.encoder = LocalTextEncoder()
        self.embedding_service = EmbeddingService()
        self.vector_service = VectorService()
        self.vector_service.load_from_disk()
        self._sync_index()

    def _sync_index(self) -> None:
        conn = get_connection()
        embedding_count = conn.execute("SELECT COUNT(*) FROM embeddings WHERE tile_id IS NOT NULL").fetchone()[0]
        conn.close()
        if self.vector_service.get_count() != embedding_count:
            self._rebuild_index_from_embeddings()

    def _rebuild_index_from_embeddings(self) -> None:
        conn = get_connection()
        rows = conn.execute("SELECT tile_id, vector FROM embeddings WHERE tile_id IS NOT NULL ORDER BY created_at").fetchall()
        conn.close()
        vectors = []
        tile_ids = []
        for row in rows:
            try:
                vectors.append(np.asarray(json.loads(row["vector"]), dtype=np.float32))
                tile_ids.append(row["tile_id"])
            except (TypeError, json.JSONDecodeError):
                continue
        self.vector_service.replace_vectors(vectors, tile_ids)

    @staticmethod
    def _point_in_ring(longitude: float, latitude: float, ring: list) -> bool:
        inside = False
        previous = ring[-1]
        for current in ring:
            current_lon, current_lat = current[:2]
            previous_lon, previous_lat = previous[:2]
            if (current_lat > latitude) != (previous_lat > latitude):
                crossing_lon = (previous_lon - current_lon) * (latitude - current_lat) / (previous_lat - current_lat) + current_lon
                if longitude < crossing_lon:
                    inside = not inside
            previous = current
        return inside

    @classmethod
    def _matches_aoi(cls, centroid: str | None, geometry: dict | list) -> bool:
        try:
            coordinates = [float(value.strip()) for value in (centroid or "").split(",")]
            if len(coordinates) != 2:
                return False
            longitude, latitude = coordinates
        except (TypeError, ValueError):
            return False

        if isinstance(geometry, list) and len(geometry) == 4:
            try:
                west, south, east, north = map(float, geometry)
                return west <= longitude <= east and south <= latitude <= north
            except (TypeError, ValueError):
                return False

        if geometry.get("type") == "Feature":
            geometry = geometry.get("geometry") or {}
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        polygons = [coordinates] if geometry_type == "Polygon" else coordinates if geometry_type == "MultiPolygon" else []

        for polygon in polygons:
            if not polygon or not polygon[0] or not cls._point_in_ring(longitude, latitude, polygon[0]):
                continue
            if not any(cls._point_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
                return True
        return False

    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        self.vector_service.load_from_disk()
        self._sync_index()
        qvec = self.encoder.encode(query)
        if not np.any(qvec):
            return []
        hits = self.vector_service.search(qvec, top_k=self.vector_service.get_count())
        items = []
        conn = get_connection()
        aoi_geometry = None
        aoi_crs = None
        if filters.get("aoi"):
            aoi = conn.execute("SELECT geometry, crs FROM aoi WHERE id = ?", (filters["aoi"],)).fetchone()
            if aoi is None:
                conn.close()
                return []
            try:
                aoi_geometry = json.loads(aoi["geometry"])
            except (TypeError, json.JSONDecodeError):
                conn.close()
                return []
            aoi_crs = aoi["crs"]

        for tile_id, score in hits:
            row = conn.execute(
                "SELECT t.*, s.sensor, s.acquisition_datetime, s.source, s.file_path, s.crs AS scene_crs, s.cloud_cover FROM tiles t JOIN scenes s ON s.id = t.scene_id WHERE t.id = ?",
                (tile_id,),
            ).fetchone()
            if row is None:
                continue
            if row["source"] == "synthetic-test-data" or not Path(row["file_path"] or "").is_file():
                continue
            if filters.get("sensor") and row["sensor"] != filters.get("sensor"):
                continue
            if filters.get("source") and row["source"] != filters.get("source"):
                continue
            acquisition_date = row["acquisition_datetime"]
            if filters.get("date_from") and (not acquisition_date or acquisition_date < filters["date_from"]):
                continue
            if filters.get("date_to") and (not acquisition_date or acquisition_date > filters["date_to"]):
                continue
            if filters.get("max_cloud_cover") is not None:
                cloud_cover = row["cloud_cover"]
                if cloud_cover is None or float(cloud_cover) > float(filters["max_cloud_cover"]):
                    continue
            if aoi_geometry is not None:
                if aoi_crs and row["scene_crs"] and aoi_crs != row["scene_crs"]:
                    continue
                if not self._matches_aoi(row["centroid"], aoi_geometry):
                    continue
            items.append(
                {
                    "tile_id": row["id"],
                    "scene_id": row["scene_id"],
                    "relevance_score": float(score),
                    "location": row["centroid"],
                    "crs": row["scene_crs"],
                    "acquisition_date": row["acquisition_datetime"],
                    "sensor": row["sensor"],
                    "thumbnail": row["thumbnail_path"],
                    "source": row["source"],
                    "bounds": row["bounds"],
                }
            )
        conn.close()
        return items[:10]

    def similar_to_image(self, tile_id: str) -> list[dict]:
        self.vector_service.load_from_disk()
        self._sync_index()
        conn = get_connection()
        row = conn.execute("SELECT * FROM tiles WHERE id = ?", (tile_id,)).fetchone()
        if row is None:
            conn.close()
            return []
        embeddings = conn.execute("SELECT * FROM embeddings WHERE tile_id = ?", (tile_id,)).fetchall()
        conn.close()
        if not embeddings:
            return []
        query_vector = np.asarray(json.loads(embeddings[0]["vector"]), dtype=np.float32)
        hits = self.vector_service.search(query_vector, top_k=6)
        out = []
        conn = get_connection()
        for other_tile, score in hits:
            if other_tile == tile_id:
                continue
            item = conn.execute(
                "SELECT t.*, s.sensor, s.acquisition_datetime, s.source, s.file_path, s.crs AS scene_crs FROM tiles t JOIN scenes s ON s.id = t.scene_id WHERE t.id = ?",
                (other_tile,),
            ).fetchone()
            if item and item["source"] != "synthetic-test-data" and Path(item["file_path"] or "").is_file():
                out.append(
                    {
                        "tile_id": item["id"],
                        "scene_id": item["scene_id"],
                        "similarity": float(score),
                        "location": item["centroid"],
                        "crs": item["scene_crs"],
                        "date": item["acquisition_datetime"],
                        "sensor": item["sensor"],
                        "source": item["source"],
                        "bounds": item["bounds"],
                        "thumbnail": item["thumbnail_path"],
                    }
                )
        conn.close()
        return out

    def get_clusters(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM clustering_results ORDER BY created_at DESC LIMIT 50").fetchall()
        conn.close()
        return [dict(row) for row in rows]
