from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np

from app.db.database import get_connection
from app.ml.image_encoder import LocalImageEncoder, build_text_embedding
from app.ml.model_loader import ModelLoader


class EmbeddingService:
    def __init__(self) -> None:
        self.model = LocalImageEncoder()
        self.model_info = ModelLoader().get_model_info()

    def encode_image(self, image_path: str | Path) -> np.ndarray:
        return self.model.encode(image_path)

    def encode_text(self, text: str) -> np.ndarray:
        return build_text_embedding(text)

    def persist_embedding(self, scene_id: str, tile_id: str, vector: np.ndarray, source: str) -> str:
        embedding_id = str(uuid.uuid4())
        conn = get_connection()
        conn.execute(
            "INSERT INTO embeddings (id, scene_id, tile_id, vector, source, model_name, model_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                embedding_id,
                scene_id,
                tile_id,
                json.dumps(vector.tolist()),
                source,
                self.model_info.name,
                self.model_info.version,
            ),
        )
        conn.commit()
        conn.close()
        return embedding_id

    def get_embeddings_by_scene(self, scene_id: str) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM embeddings WHERE scene_id = ?", (scene_id,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]
