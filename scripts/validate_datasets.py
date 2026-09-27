from __future__ import annotations

import argparse
import json
from pathlib import Path

from dataset_utils import RAW_ROOT, SUPPORTED_RASTERS, classify_path, ensure_dataset_tree, iter_rasters, read_sidecar


def inspect_image(path: Path) -> tuple[bool, str]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
        return True, "readable"
    except ImportError:
        return True, "Pillow unavailable; extension checked only"
    except Exception as exc:
        return False, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate locally staged public Earth-observation files.")
    parser.add_argument("--root", type=Path, default=RAW_ROOT)
    parser.add_argument("--report", type=Path, default=Path("data/manifests/validation_report.json"))
    args = parser.parse_args()
    ensure_dataset_tree()
    records = []
    for path in iter_rasters(args.root):
        source, year = classify_path(path)
        metadata = read_sidecar(path)
        readable, detail = inspect_image(path)
        records.append({"file_path": str(path), "source_group": source, "year": year, "readable": readable, "detail": detail, "has_sidecar": bool(metadata), "metadata": metadata})
    invalid = [record for record in records if not record["readable"] or record["source_group"] == "unknown" or not record["has_sidecar"]]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"files": records, "invalid_count": len(invalid)}, indent=2), encoding="utf-8")
    for record in records:
        state = "OK" if record["readable"] and record["source_group"] != "unknown" and record["has_sidecar"] else "CHECK"
        print(f"{state}: {record['file_path']} ({record['detail']})")
    print(f"Validated {len(records)} raster files; {len(invalid)} need attention. Report: {args.report}")


if __name__ == "__main__":
    main()
