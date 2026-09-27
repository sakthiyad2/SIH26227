import json
from pathlib import Path

import numpy as np

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None


class VectorService:
    def __init__(self, index_dir: str | Path | None = None) -> None:
        self.index_dir = Path(index_dir) if index_dir else Path(__file__).resolve().parents[2] / "indexes"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "satellite_index.faiss"
        self.metadata_path = self.index_dir / "satellite_index_meta.json"
        self._vectors = []
        self._ids = []
        self._index = None

    def add_vectors(self, vectors: list[np.ndarray], tile_ids: list[str]) -> None:
        if not vectors:
            return
        matrix = np.vstack(vectors).astype(np.float32)
        if faiss is not None:
            dim = matrix.shape[1]
            index = faiss.IndexFlatL2(dim)
            index.add(matrix)
            if self._index is None:
                self._index = index
            else:
                self._index.add(matrix)
            self._ids.extend(tile_ids)
            self._vectors.extend(matrix.tolist())
            self._save_metadata()
            return
        self._vectors.extend(matrix.tolist())
        self._ids.extend(tile_ids)
        self._save_metadata()

    def replace_vectors(self, vectors: list[np.ndarray], tile_ids: list[str]) -> None:
        self._vectors = []
        self._ids = []
        self._index = None
        self.add_vectors(vectors, tile_ids)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        if not self._vectors:
            return []
        matrix = np.asarray(self._vectors, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        query = query_vector.astype(np.float32).ravel()
        if matrix.shape[1] != query.shape[0]:
            aligned_query = np.zeros(matrix.shape[1], dtype=np.float32)
            width = min(matrix.shape[1], query.shape[0])
            aligned_query[:width] = query[:width]
            query = aligned_query
        scores = matrix @ query
        order = np.argsort(scores)[::-1][:top_k]
        return [(self._ids[i], float(scores[i])) for i in order]

    def _save_metadata(self) -> None:
        self.metadata_path.write_text(json.dumps({"tile_ids": self._ids, "vectors": self._vectors}, indent=2))

    def load_from_disk(self) -> None:
        if self.metadata_path.exists():
            payload = json.loads(self.metadata_path.read_text())
            self._ids = payload.get("tile_ids", [])
            self._vectors = payload.get("vectors", [])
            if len(self._ids) != len(self._vectors):
                self._ids = []
                self._vectors = []

    def get_count(self) -> int:
        return len(self._ids)
