from __future__ import annotations

import argparse
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from dataset_utils import RAW_ROOT, ensure_dataset_tree


def destination(source: str, year: str, product: str | None, filename: str) -> Path:
    source = source.lower()
    if source not in {"sentinel1", "sentinel2", "landsat", "bhuvan"}:
        raise ValueError("source must be sentinel1, sentinel2, landsat, or bhuvan")
    if source == "bhuvan":
        if product not in {"resourcesat", "cartosat", "thematic"}:
            raise ValueError("Bhuvan downloads require product: resourcesat, cartosat, or thematic")
        return RAW_ROOT / source / product / filename
    if not year or not year.isdigit() or len(year) != 4:
        raise ValueError("Sentinel and Landsat downloads require a four-digit year")
    return RAW_ROOT / source / year / filename


def main() -> None:
    parser = argparse.ArgumentParser(description="Download one explicitly supplied official dataset file.")
    parser.add_argument("--url", required=True, help="Official HTTPS or HTTP source URL supplied by the user")
    parser.add_argument("--source", required=True, choices=("sentinel1", "sentinel2", "landsat", "bhuvan"))
    parser.add_argument("--year", default="", help="Four-digit acquisition/product year for Sentinel or Landsat")
    parser.add_argument("--product", help="Bhuvan product directory: resourcesat, cartosat, or thematic")
    parser.add_argument("--filename", help="Local filename; otherwise use the URL path filename")
    parser.add_argument("--confirm-public-source", action="store_true", help="Explicitly confirm the supplied URL is public and permitted")
    args = parser.parse_args()
    if not args.confirm_public_source:
        parser.error("Refusing download: pass --confirm-public-source for an explicitly approved public source")
    parsed = urllib.parse.urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        parser.error("--url must be a complete HTTP(S) URL")
    ensure_dataset_tree()
    filename = args.filename or Path(parsed.path).name
    if not filename:
        parser.error("Could not infer a filename; pass --filename")
    target = destination(args.source, args.year, args.product, Path(filename).name)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    print(f"Downloading only the explicitly supplied source to {target}")
    with urllib.request.urlopen(args.url, timeout=60) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output)
    partial.replace(target)
    print(f"Staged: {target}")
    print("Next: add a sidecar JSON with verified product metadata, then run validate_datasets.py.")


if __name__ == "__main__":
    main()
