import json
import uuid

import numpy as np
from sklearn.cluster import KMeans

from app.db.database import get_connection


class ClusteringService:
    def __init__(self, n_clusters: int = 3) -> None:
        self.n_clusters = n_clusters

    def build_clusters(self, embeddings: list[dict], tile_ids: list[str]) -> list[dict]:
        if not embeddings:
            return []
        matrix = np.asarray([np.asarray(json.loads(item["vector"]), dtype=np.float32) for item in embeddings], dtype=np.float32)
        labels = KMeans(n_clusters=min(self.n_clusters, len(matrix)), random_state=0).fit_predict(matrix)
        conn = get_connection()
        results = []
        for idx, tile_id in enumerate(tile_ids):
            cluster_id = f"cluster-{labels[idx]}"
            cluster_key = str(uuid.uuid4())
            conn.execute(
                "INSERT OR REPLACE INTO clustering_results (id, cluster_id, tile_id, centroid) VALUES (?, ?, ?, ?)",
                (cluster_key, cluster_id, tile_id, str(np.mean(matrix[idx]).round(4))),
            )
            results.append({"cluster_id": cluster_id, "tile_id": tile_id, "centroid": str(np.mean(matrix[idx]).round(4))})
        conn.commit()
        conn.close()
        return results
