from __future__ import annotations

import numpy as np
from PIL import Image


class PreprocessingService:
    def align_and_resample(self, before_path: str, after_path: str, size: tuple[int, int] = (64, 64)) -> tuple[np.ndarray, np.ndarray]:
        before = np.asarray(Image.open(before_path).convert("RGB"), dtype=np.float32)
        after = np.asarray(Image.open(after_path).convert("RGB"), dtype=np.float32)
        before = self._resize(before, size)
        after = self._resize(after, size)
        return before, after

    @staticmethod
    def _resize(arr: np.ndarray, size: tuple[int, int]) -> np.ndarray:
        image = Image.fromarray(np.uint8(np.clip(arr, 0, 255)))
        return np.asarray(image.resize(size), dtype=np.float32)

    def apply_quality_masks(self, before: np.ndarray, after: np.ndarray, cloud_mask=None, shadow_mask=None):
        mask = np.ones(before.shape[:2], dtype=bool)
        if cloud_mask is not None:
            mask &= ~cloud_mask.astype(bool)
        if shadow_mask is not None:
            mask &= ~shadow_mask.astype(bool)
        return before, after, mask
