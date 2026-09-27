from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel

from app.db.database import get_connection
from app.services.semantic_search_service import SemanticSearchService

router = APIRouter()
service: SemanticSearchService | None = None


def get_search_service() -> SemanticSearchService:
    global service
    if service is None:
        service = SemanticSearchService()
    return service


class SearchRequest(BaseModel):
    query: str
    date_from: str | None = None
    date_to: str | None = None
    sensor: str | None = None
    source: str | None = None
    aoi: str | None = None
    max_cloud_cover: float | None = None
    min_confidence: float | None = None


@router.get("/search/filters")
def search_filter_options() -> dict:
    conn = get_connection()
    scene_rows = conn.execute(
        "SELECT DISTINCT sensor, source, file_path FROM scenes WHERE sensor IS NOT NULL"
    ).fetchall()
    aoi_rows = conn.execute("SELECT id, name FROM aoi ORDER BY name").fetchall()
    conn.close()
    sensors = sorted(
        {
            row["sensor"]
            for row in scene_rows
            if row["sensor"] != "synthetic"
            and row["source"] != "synthetic-test-data"
            and Path(row["file_path"] or "").is_file()
        },
        key=str.casefold,
    )
    return {"sensors": sensors, "aois": [dict(row) for row in aoi_rows]}


@router.post("/search/semantic")
def semantic_search(payload: SearchRequest) -> dict:
    results = get_search_service().search(payload.query, payload.model_dump(exclude={"query"}))
    return {"ok": True, "results": results}


@router.post("/search/image")
def image_similarity(payload: dict) -> dict:
    tile_id = payload.get("tile_id")
    if not tile_id:
        raise HTTPException(status_code=400, detail="tile_id is required")
    return {"ok": True, "results": get_search_service().similar_to_image(tile_id)}


@router.get("/tiles/{tile_id}/image")
def tile_image(tile_id: str) -> Response:
    conn = get_connection()
    tile = conn.execute("SELECT image_path, thumbnail_path FROM tiles WHERE id = ?", (tile_id,)).fetchone()
    conn.close()
    if tile is None:
        raise HTTPException(status_code=404, detail="Tile not found")

    image_path = Path(tile["thumbnail_path"] or "")
    if not image_path.is_file():
        image_path = Path(tile["image_path"] or "")
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Tile image is unavailable")

    try:
        with Image.open(image_path) as image:
            image.thumbnail((1200, 1200))
            preview = image.convert("RGB")
            output = BytesIO()
            preview.save(output, format="PNG")
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=415, detail="Tile image cannot be previewed") from exc

    return Response(content=output.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.get("/clusters")
def list_clusters() -> dict:
    return {"ok": True, "clusters": get_search_service().get_clusters()}
