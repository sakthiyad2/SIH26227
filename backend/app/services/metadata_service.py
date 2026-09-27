import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


class MetadataService:
    def extract_metadata(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        suffix = path.suffix.lower()
        if suffix not in {".tif", ".tiff", ".geotiff", ".png", ".jpg", ".jpeg"}:
            raise ValueError(f"Unsupported raster format: {suffix}")

        checksum = self._checksum(path)
        try:
            with Image.open(path) as img:
                width, height = img.size
                bands = len(img.getbands())
                mode = img.mode
        except Exception as exc:
            raise ValueError(f"Corrupted image or unreadable raster: {path}") from exc

        sidecar = path.with_suffix(path.suffix + ".json")
        metadata: dict[str, Any] = {
            "source": "local-staged",
            "sensor": "unknown",
            "acquisition_datetime": None,
            "file_path": str(path),
            "checksum": checksum,
            "crs": "",
            "bounding_box": "",
            "resolution": f"{width}x{height}",
            "bands": bands,
            "mode": mode,
            "width": width,
            "height": height,
            "cloud_cover": None,
        }

        if sidecar.exists():
            try:
                extra = json.loads(sidecar.read_text())
                metadata.update(extra)
            except Exception:
                pass

        cloud_cover = metadata.get("cloud_cover")
        if cloud_cover is not None:
            try:
                cloud_text = str(cloud_cover).strip()
                has_percent_suffix = cloud_text.endswith("%")
                cloud_value = float(cloud_text.removesuffix("%").strip())
                if has_percent_suffix or cloud_value > 1:
                    cloud_value /= 100
                metadata["cloud_cover"] = cloud_value if 0 <= cloud_value <= 1 else None
            except ValueError:
                metadata["cloud_cover"] = None

        return metadata

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
