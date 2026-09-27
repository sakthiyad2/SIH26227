from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.change_detection_service import ChangeDetectionService

router = APIRouter()
service = ChangeDetectionService()


class AnalysisRequest(BaseModel):
    scene_a_id: str
    scene_b_id: str
    tile_a_id: str | None = None
    tile_b_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@router.post("/change/analyze")
def analyze_change(payload: AnalysisRequest) -> dict:
    result = service.detect_change(payload.model_dump())
    return {"ok": True, "result": result}


@router.get("/change")
def list_changes() -> dict:
    return {"ok": True, "changes": service.list_changes()}


@router.get("/change/{change_id}")
def get_change(change_id: str) -> dict:
    item = service.get_change(change_id)
    if not item:
        raise HTTPException(status_code=404, detail="Change not found")
    return {"ok": True, "change": item}
