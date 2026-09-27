from pathlib import Path


def sanitize_filename(name: str) -> str:
    return Path(name).name.replace("..", "")


def ensure_directory(path: str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
