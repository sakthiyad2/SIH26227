# GeoWatch Intelligence Console

This prototype implements a local-first satellite intelligence workflow for SIH 2026. It combines a Vite React dashboard with a FastAPI backend that ingests imagery, stores metadata in SQLite, builds local embeddings, and scores change detection events without relying on cloud APIs.

## Features

- Local ingestion and checksum validation for geospatial imagery
- SQLite-backed scene and tile indexes
- Offline embedding generation with a lightweight local fallback model
- Change-detection scoring pipeline with quality and confidence signals
- Analyst review queue surfaced in the dashboard
- FastAPI endpoints for health, ingestion, statistics, and change analysis
- Offline-first public dataset staging for Copernicus Sentinel-1/2, USGS Landsat Collection 2, and NRSC/ISRO Bhuvan

## Public dataset preparation

Only publicly accessible or organiser-provided imagery may be staged. Do not use classified, operational, service-generated, private, or restricted military data. The application does not require network access after data, models, and libraries have been staged locally.

The supported layout is created by the preparation script:

```bash
python scripts/prepare_dataset.py
```

Place permitted files under `data/raw/sentinel1/`, `data/raw/sentinel2/`, `data/raw/landsat/`, or the appropriate `data/raw/bhuvan/` product directory. Keep verified metadata in a sidecar file next to each raster, for example `scene.tif.json`; the manifest will leave unverified fields blank rather than inventing them.

Run the local pipeline in this order:

```bash
python scripts/validate_datasets.py
python scripts/compute_checksums.py
python scripts/generate_manifest.py
python scripts/prepare_dataset.py --copy-raster
python scripts/ingest_data.py
```

`download_data.py` is optional and refuses to run unless you provide an explicit official URL and pass `--confirm-public-source`. It has no hard-coded mirrors or runtime cloud dependency. Official source references are listed in the application Data Sources view.

## Runtime requirements

- Python 3.12.x
- Node.js 18+

## Run the backend

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` before starting the backend to create its initial administrator account. The app intentionally has no built-in administrator credentials.

## Run the frontend

```bash
npm install
npm run dev
```

Then open http://localhost:5173. To use a backend on another host, set `VITE_API_BASE_URL` to its base URL without `/api` before building the frontend.

## Free deployment on Render

The repository includes a `render.yaml` Blueprint for a static frontend and FastAPI backend. Push the repository to GitHub, create a new Blueprint on Render from that repository, and provide `ADMIN_EMAIL` and a strong `ADMIN_PASSWORD` when prompted. Render builds the frontend and connects it to the API automatically.

Render's free web service sleeps when idle and has an ephemeral filesystem. This prototype stores its SQLite database, uploaded imagery, and search index on that filesystem, so those records and files can be lost on restart or redeploy. Use persistent storage and a managed database/object store before relying on it for ongoing data.

## Validation

The backend smoke tests pass with:

```bash
cd backend
C:/Users/admin/AppData/Local/Programs/Python/Python312/python.exe -m pytest -q
```

The frontend build passes with:

```bash
npm run build
```
