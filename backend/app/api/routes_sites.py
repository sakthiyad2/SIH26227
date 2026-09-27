from fastapi import APIRouter, HTTPException

from app.services.similarity_service import SimilarityService

router = APIRouter()
service = SimilarityService()


@router.get("/sites/similar/{tile_id}")
def similar_sites(tile_id: str) -> dict:
    results = service.get_similar_sites(tile_id)
    if not results:
        raise HTTPException(status_code=404, detail="No similar sites found")
    return {"ok": True, "results": results}
