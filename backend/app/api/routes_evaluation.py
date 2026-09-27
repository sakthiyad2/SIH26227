from fastapi import APIRouter
from pydantic import BaseModel

from app.services.evaluation_service import EvaluationService

router = APIRouter()
service = EvaluationService()


class EvalRequest(BaseModel):
    limit: int = 10


@router.post("/evaluation/run")
def run_evaluation(payload: EvalRequest | None = None) -> dict:
    payload = payload or EvalRequest()
    result = service.run_evaluation(limit=payload.limit)
    return {"ok": True, "evaluation": result}


@router.get("/evaluation/results")
def get_results() -> dict:
    return {"ok": True, "results": service.get_latest_results()}
