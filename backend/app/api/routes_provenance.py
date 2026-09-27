from fastapi import APIRouter, HTTPException

from app.services.provenance_service import ProvenanceService

router = APIRouter()
service = ProvenanceService()


@router.get("/provenance/{entity_id}")
def provenance(entity_id: str) -> dict:
    item = service.get_provenance(entity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Provenance entry not found")
    return {"ok": True, "provenance": item}
