from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_search import router as search_router
from app.api.routes_change import router as change_router
from app.api.routes_sites import router as sites_router
from app.api.routes_review import router as review_router
from app.api.routes_provenance import router as provenance_router
from app.api.routes_evaluation import router as evaluation_router
from app.api.routes_auth import router as auth_router
from app.api.routes_datasets import router as datasets_router
from app.db.database import init_db

app = FastAPI(title="Satellite Intelligence Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(ingestion_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(change_router, prefix="/api")
app.include_router(sites_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(provenance_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/")
def read_root() -> dict:
    return {"message": "Satellite Intelligence API"}
