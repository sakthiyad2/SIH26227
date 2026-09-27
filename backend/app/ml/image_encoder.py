import json
from pathlib import Path

import numpy as np
from PIL import Image


class LocalImageEncoder:
    def __init__(self, dim: int = 32):
        self.dim = dim

    def encode(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        img = Image.open(path).convert("RGB")
        arr = np.asarray(img, dtype=np.float32)
        rgb = arr.reshape(-1, 3)
        hist = np.histogramdd(rgb / 255.0, bins=(4, 4, 4), range=((0, 1), (0, 1), (0, 1)))[0].astype(np.float32).ravel()
        texture = np.std(arr, axis=(0, 1)).astype(np.float32)
        vector = np.concatenate([hist[: self.dim], texture[:3]])
        return vector / (np.linalg.norm(vector) + 1e-8)

    def encode_batch(self, paths: list[str | Path]) -> list[np.ndarray]:
        return [self.encode(path) for path in paths]


def build_text_embedding(text: str) -> np.ndarray:
    tokens = [piece.lower() for piece in text.replace("/", " ").replace("-", " ").split()]
    vocab = {
        "new": 1.0,
        "structure": 2.0,
        "built": 1.5,
        "river": 2.5,
        "road": 2.2,
        "vegetation": 1.8,
        "water": 2.0,
        "clearance": 2.0,
        "construction": 2.25,
        "forest": 1.6,
        "urban": 1.7,
        "field": 1.3,
        "cloud": 1.1,
        "shadow": 1.1,
        "seasonal": 1.2,
    }
    vector = np.zeros(32, dtype=np.float32)
    for idx, token in enumerate(sorted(vocab.keys())):
        if token in tokens:
            vector[idx] = vocab[token]
    return vector / (np.linalg.norm(vector) + 1e-8)
