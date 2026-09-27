import hashlib
from pathlib import Path


def sha256_file(file_path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
