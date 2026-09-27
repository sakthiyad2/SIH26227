from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
RAW_ROOT = DATA_ROOT / "raw"
PROCESSED_ROOT = DATA_ROOT / "processed"
MANIFEST_ROOT = DATA_ROOT / "manifests"
LABEL_ROOT = DATA_ROOT / "labels"
SYNTHETIC_ROOT = DATA_ROOT / "synthetic"
SUPPORTED_RASTERS = {".tif", ".tiff", ".geotiff", ".png", ".jpg", ".jpeg"}
SOURCE_NAMES = {"sentinel1", "sentinel2", "landsat", "bhuvan"}


def ensure_dataset_tree() -> None:
    for source in ("sentinel1", "sentinel2", "landsat"):
        for year in ("2023", "2024", "2025", "2026"):
            (RAW_ROOT / source / year).mkdir(parents=True, exist_ok=True)
    for product in ("resourcesat", "cartosat", "thematic"):
        (RAW_ROOT / "bhuvan" / product).mkdir(parents=True, exist_ok=True)
    for name in ("tiles", "thumbnails", "masks", "aligned", "normalized"):
        (PROCESSED_ROOT / name).mkdir(parents=True, exist_ok=True)
    for root in (LABEL_ROOT, MANIFEST_ROOT, SYNTHETIC_ROOT / "scenes", SYNTHETIC_ROOT / "labels"):
        root.mkdir(parents=True, exist_ok=True)


def iter_rasters(root: Path = RAW_ROOT) -> Iterable[Path]:
    if not root.exists():
        return []
    return (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_RASTERS)


def sidecar_for(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".json")


def read_sidecar(path: Path) -> dict[str, Any]:
    sidecar = sidecar_for(path)
    if not sidecar.exists():
        return {}
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid sidecar JSON: {sidecar}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Sidecar must contain an object: {sidecar}")
    return payload


def classify_path(path: Path) -> tuple[str, str]:
    relative = path.resolve().relative_to(RAW_ROOT.resolve())
    parts = [part.lower() for part in relative.parts]
    source = next((part for part in parts if part in SOURCE_NAMES), "unknown")
    year = next((part for part in parts if part.isdigit() and len(part) == 4), "")
    return source, year


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
