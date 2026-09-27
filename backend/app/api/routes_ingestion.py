from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingestion_service import IngestionService

router = APIRouter()
service = IngestionService()


@router.post("/ingestion")
async def ingest_files(files: List[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    records = []
    for file in files:
        result = await service.ingest_uploaded_file(file)
        records.append(result)
    return {"ok": True, "files": records}


@router.get("/scenes")
def list_scenes() -> list:
    return service.list_scenes()


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: str) -> dict:
    scene = service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene
