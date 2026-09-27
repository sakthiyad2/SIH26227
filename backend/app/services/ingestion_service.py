import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.db.database import get_connection
from app.services.embedding_service import EmbeddingService
from app.services.metadata_service import MetadataService
from app.services.provenance_service import ProvenanceService
from app.services.vector_service import VectorService


class IngestionService:
    def __init__(self) -> None:
        self.metadata_service = MetadataService()
        self.embedding_service = EmbeddingService()
        self.vector_service = VectorService()
        self.provenance_service = ProvenanceService()

    async def ingest_uploaded_file(self, file: UploadFile) -> dict:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Uploaded file is missing a filename")
        allowed = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
        suffix = Path(file.filename).suffix.lower()
        if suffix not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: {suffix}")

        raw_dir = Path(__file__).resolve().parents[2] / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        target_path = raw_dir / Path(file.filename).name
        with target_path.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)

        return self.ingest_path(str(target_path))

    def ingest_path(self, file_path: str) -> dict:
        meta = self.metadata_service.extract_metadata(file_path)
        conn = get_connection()
        existing = conn.execute("SELECT id, file_path FROM scenes WHERE checksum = ?", (meta["checksum"],)).fetchone()
        if existing:
            tile = conn.execute("SELECT id, image_path FROM tiles WHERE scene_id = ? ORDER BY created_at LIMIT 1", (existing["id"],)).fetchone()
            if tile and (not Path(existing["file_path"] or "").is_file() or not Path(tile["image_path"] or "").is_file()):
                replacement_path = str(Path(file_path).resolve())
                thumbnail_path = str(Path(replacement_path).with_suffix(".thumb.png"))
                conn.execute("UPDATE scenes SET file_path = ? WHERE id = ?", (replacement_path, existing["id"]))
                conn.execute(
                    "UPDATE tiles SET image_path = ?, thumbnail_path = ? WHERE scene_id = ?",
                    (replacement_path, thumbnail_path, existing["id"]),
                )
                conn.commit()
            conn.close()
            return {"scene_id": existing["id"], "tile_id": tile["id"] if tile else None, "status": "duplicate"}

        scene_id = str(uuid.uuid4())
        scene = {
            "id": scene_id,
                "source": meta.get("source") or "local-staged",
                "sensor": meta.get("sensor") or "unknown",
                "acquisition_datetime": meta.get("acquisition_datetime"),
            "file_path": file_path,
            "checksum": meta["checksum"],
            "crs": meta.get("crs") or "",
            "bounding_box": meta.get("bounding_box") or "",
            "resolution": meta.get("resolution"),
            "band_count": meta.get("bands", 0),
            "cloud_cover": meta.get("cloud_cover", 0.0),
            "processing_status": "indexed",
        }

        conn.execute(
            "INSERT INTO scenes (id, source, sensor, acquisition_datetime, file_path, checksum, crs, bounding_box, resolution, band_count, cloud_cover, processing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scene["id"],
                scene["source"],
                scene["sensor"],
                scene["acquisition_datetime"],
                scene["file_path"],
                scene["checksum"],
                scene["crs"],
                scene["bounding_box"],
                scene["resolution"],
                scene["band_count"],
                scene["cloud_cover"],
                scene["processing_status"],
            ),
        )
        conn.commit()

        thumbnail_path = str(Path(file_path).with_suffix(".thumb.png"))
        tile_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO tiles (id, scene_id, bounds, centroid, image_path, thumbnail_path, embedding_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tile_id, scene_id, scene["bounding_box"], meta.get("centroid") or "", file_path, thumbnail_path, None),
        )
        conn.commit()

        vector = self.embedding_service.encode_image(file_path)
        embedding_id = self.embedding_service.persist_embedding(scene_id, tile_id, vector, scene["source"])
        conn.execute("UPDATE tiles SET embedding_id = ? WHERE id = ?", (embedding_id, tile_id))
        self.vector_service.add_vectors([vector], [tile_id])
        conn.commit()
        conn.close()

        self.provenance_service.record(
            "scene",
            scene_id,
            {
                "input_files": [file_path],
                "input_checksums": [meta["checksum"]],
                "model_name": self.embedding_service.model_info.name,
                "model_version": self.embedding_service.model_info.version,
                "model_source": self.embedding_service.model_info.source,
                "model_license": self.embedding_service.model_info.license,
                "steps": ["validate", "extract metadata", "generate embedding", "index tile"],
                "parameters": {"offline_mode": True, "source": scene["source"]},
            },
        )

        return {
            "scene_id": scene_id,
            "tile_id": tile_id,
            "status": "indexed",
            "checksum": meta["checksum"],
            "sensor": scene["sensor"],
            "acquisition_datetime": scene["acquisition_datetime"],
        }

    def list_scenes(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM scenes ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_scene(self, scene_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
