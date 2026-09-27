from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dataset_utils import RAW_ROOT, ensure_dataset_tree, iter_rasters, read_sidecar

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ingestion_service import IngestionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest validated local imagery into the offline SQLite/vector pipeline.")
    parser.add_argument("--root", type=Path, default=RAW_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ensure_dataset_tree()
    files = list(iter_rasters(args.root))
    if args.dry_run:
        for path in files:
            print(f"WOULD INGEST: {path}")
        return
    service = IngestionService()
    for path in files:
        try:
            metadata = read_sidecar(path)
            if not metadata.get("product_id") or not metadata.get("original_source_url") or not metadata.get("license_terms"):
                print(f"SKIPPED: {path}: required product, source URL, and licence metadata are missing")
                continue
            result = service.ingest_path(str(path))
            print(f"{result['status'].upper()}: {path} -> {result.get('scene_id')}")
        except Exception as exc:
            print(f"FAILED: {path}: {exc}")


if __name__ == "__main__":
    main()
