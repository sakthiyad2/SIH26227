from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.review_service import ReviewService

router = APIRouter()
service = ReviewService()


class ReviewPayload(BaseModel):
    decision: str
    reason: str | None = None
    reviewer: str = "analyst"


@router.get("/review/queue")
def review_queue() -> dict:
    return {"ok": True, "queue": service.get_queue()}


@router.post("/review/{change_id}/confirm")
def confirm(change_id: str, payload: ReviewPayload) -> dict:
    item = service.record_decision(change_id, payload.model_dump())
    return {"ok": True, "decision": item}


@router.post("/review/{change_id}/reject")
def reject(change_id: str, payload: ReviewPayload) -> dict:
    item = service.record_decision(change_id, payload.model_dump())
    return {"ok": True, "decision": item}
