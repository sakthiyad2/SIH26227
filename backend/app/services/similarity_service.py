import json

import numpy as np

from app.db.database import get_connection
from app.services.vector_service import VectorService


class SimilarityService:
    def __init__(self) -> None:
        self.vector_service = VectorService()
        self.vector_service.load_from_disk()

    def get_similar_sites(self, tile_id: str) -> list[dict]:
        conn = get_connection()
        embedding_row = conn.execute("SELECT * FROM embeddings WHERE tile_id = ?", (tile_id,)).fetchone()
        if embedding_row is None:
            conn.close()
            return []
        query_vector = np.asarray(json.loads(embedding_row["vector"]), dtype=np.float32)
        results = self.vector_service.search(query_vector, top_k=5)
        out = []
        for other_tile_id, score in results:
            if other_tile_id == tile_id:
                continue
            item = conn.execute(
                "SELECT t.*, s.sensor, s.acquisition_datetime, s.source, s.crs AS scene_crs FROM tiles t JOIN scenes s ON s.id = t.scene_id WHERE t.id = ?",
                (other_tile_id,),
            ).fetchone()
            if item:
                out.append(
                    {
                        "tile_id": item["id"],
                        "scene_id": item["scene_id"],
                        "similarity": float(score),
                        "coordinates": item["centroid"],
                        "location": item["centroid"],
                        "crs": item["scene_crs"],
                        "date": item["acquisition_datetime"],
                        "sensor": item["sensor"],
                        "source": item["source"],
                        "thumbnail": item["thumbnail_path"],
                    }
                )
        conn.close()
        return out
