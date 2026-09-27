from __future__ import annotations

import argparse
from pathlib import Path

from dataset_utils import RAW_ROOT, ensure_dataset_tree, iter_rasters, sha256, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute SHA-256 checksums for staged raster files.")
    parser.add_argument("--root", type=Path, default=RAW_ROOT)
    parser.add_argument("--output", type=Path, default=Path("data/manifests/checksums.csv"))
    args = parser.parse_args()
    ensure_dataset_tree()
    rows = [{"file_path": str(path), "sha256": sha256(path), "size_bytes": path.stat().st_size} for path in iter_rasters(args.root)]
    write_csv(args.output, rows, ["file_path", "sha256", "size_bytes"])
    print(f"Wrote {len(rows)} checksums to {args.output}")


if __name__ == "__main__":
    main()
