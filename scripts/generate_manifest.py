from __future__ import annotations

import argparse
from pathlib import Path

from dataset_utils import MANIFEST_ROOT, RAW_ROOT, classify_path, ensure_dataset_tree, iter_rasters, read_sidecar, sha256, write_csv

FIELDS = ["file_path", "source_group", "product_id", "acquisition_datetime", "platform", "sensor", "processing_level", "orbit", "polarization", "acquisition_mode", "crs", "bounding_box", "resolution", "bands", "cloud_cover", "product_type", "license_terms", "original_source_url", "size_bytes", "sha256"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a normalized scene manifest without inventing missing metadata.")
    parser.add_argument("--root", type=Path, default=RAW_ROOT)
    parser.add_argument("--output", type=Path, default=MANIFEST_ROOT / "scenes.csv")
    args = parser.parse_args()
    ensure_dataset_tree()
    rows = []
    for path in iter_rasters(args.root):
        source_group, _ = classify_path(path)
        metadata = read_sidecar(path)
        rows.append({"file_path": str(path), "source_group": source_group, "product_id": metadata.get("product_id", ""), "acquisition_datetime": metadata.get("acquisition_datetime", ""), "platform": metadata.get("platform", ""), "sensor": metadata.get("sensor", ""), "processing_level": metadata.get("processing_level", ""), "orbit": metadata.get("orbit", ""), "polarization": metadata.get("polarization", ""), "acquisition_mode": metadata.get("acquisition_mode", ""), "crs": metadata.get("crs", ""), "bounding_box": metadata.get("bounding_box", ""), "resolution": metadata.get("resolution", ""), "bands": metadata.get("bands", ""), "cloud_cover": metadata.get("cloud_cover", ""), "product_type": metadata.get("product_type", ""), "license_terms": metadata.get("license_terms", ""), "original_source_url": metadata.get("original_source_url", ""), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    write_csv(args.output, rows, FIELDS)
    print(f"Wrote {len(rows)} manifest rows to {args.output}")


if __name__ == "__main__":
    main()
