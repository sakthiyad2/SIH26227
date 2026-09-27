from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from dataset_utils import PROCESSED_ROOT, RAW_ROOT, ensure_dataset_tree, iter_rasters


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare local imagery without modifying originals.")
    parser.add_argument("--root", type=Path, default=RAW_ROOT)
    parser.add_argument("--copy-raster", action="store_true", help="Copy source rasters into processed/tiles; disabled by default")
    args = parser.parse_args()
    ensure_dataset_tree()
    count = 0
    for source_path in iter_rasters(args.root):
        count += 1
        if args.copy_raster:
            relative = source_path.relative_to(args.root)
            target = PROCESSED_ROOT / "tiles" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
    print(f"Prepared directory layout for {count} raster files.")
    if not args.copy_raster:
        print("No source files copied. Pass --copy-raster to create processed tile copies; raw files remain unchanged.")


if __name__ == "__main__":
    main()
