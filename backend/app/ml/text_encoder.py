from __future__ import annotations

import numpy as np


class LocalTextEncoder:
    def encode(self, text: str) -> np.ndarray:
        tokens = [part.lower() for part in text.replace("-", " ").split()]
        vocab = {
            "river": 2.0,
            "road": 2.4,
            "construction": 2.6,
            "build": 2.1,
            "new": 1.7,
            "structure": 2.0,
            "vegetation": 1.8,
            "water": 2.0,
            "forest": 1.5,
            "clearance": 1.9,
            "urban": 1.6,
            "cloud": 1.1,
            "shadow": 1.1,
        }
        vector = np.zeros(32, dtype=np.float32)
        for i, key in enumerate(sorted(vocab.keys())):
            if key in tokens:
                vector[i] = vocab[key]
        return vector / (np.linalg.norm(vector) + 1e-8)

    def encode_batch(self, texts: list[str]) -> list[np.ndarray]:
        return [self.encode(text) for text in texts]
