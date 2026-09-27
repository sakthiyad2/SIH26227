from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SceneRecord(BaseModel):
    id: str
    source: str
    sensor: str
    acquisition_datetime: Optional[str] = None
    file_path: str
    checksum: str
    crs: Optional[str] = None
    bounding_box: Optional[str] = None
    resolution: Optional[str] = None
    band_count: int = 0
    cloud_cover: Optional[float] = 0.0
    processing_status: str = "pending"


class TileRecord(BaseModel):
    id: str
    scene_id: str
    bounds: str
    centroid: str
    image_path: str
    thumbnail_path: str
    embedding_id: Optional[str] = None


class SearchResult(BaseModel):
    tile_id: str
    relevance_score: float
    location: str
    acquisition_date: Optional[str]
    sensor: str
    thumbnail: Optional[str]
    source: str
    bounds: str


class ChangePayload(BaseModel):
    scene_a_id: str
    scene_b_id: str
    tile_a_id: Optional[str] = None
    tile_b_id: Optional[str] = None
    change_type: Optional[str] = None
    confidence: Optional[float] = None
    quality_score: Optional[float] = None
    changed_area: Optional[float] = None
    earliest_supporting_observation: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvalMetrics(BaseModel):
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    mean_reciprocal_rank: float = 0.0
    f1: float = 0.0
    iou: float = 0.0
    latency_ms: float = 0.0


class ReviewDecision(BaseModel):
    decision: str
    reason: Optional[str] = None
    reviewer: str = "analyst"


class ApiResponse(BaseModel):
    ok: bool = True
    message: str = "success"
    data: Optional[Dict[str, Any]] = None
