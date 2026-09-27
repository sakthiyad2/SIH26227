import numpy as np


class FalseAlarmService:
    def suppress_false_alarms(self, change_mask: np.ndarray, quality_mask: np.ndarray) -> np.ndarray:
        mask = np.asarray(change_mask, dtype=bool)
        if mask.ndim == 3 and mask.shape[-1] in (3, 4):
            mask = np.any(mask, axis=-1)
        quality = np.asarray(quality_mask, dtype=bool)
        filtered = mask & quality

        # Morphological filter using a 3x3 neighborhood to remove speckle
        kernel = np.ones((3, 3), dtype=np.uint8)
        filtered = self._dilate(self._erode(filtered, kernel), kernel)
        return filtered.astype(np.uint8)

    @staticmethod
    def _erode(mask: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        out = np.zeros_like(mask, dtype=np.uint8)
        pad = kernel.shape[0] // 2
        for row in range(mask.shape[0]):
            for col in range(mask.shape[1]):
                window = mask[max(0, row - pad):min(mask.shape[0], row + pad + 1), max(0, col - pad):min(mask.shape[1], col + pad + 1)]
                if window.size and np.all(window):
                    out[row, col] = 1
        return out

    @staticmethod
    def _dilate(mask: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        out = np.zeros_like(mask, dtype=np.uint8)
        pad = kernel.shape[0] // 2
        for row in range(mask.shape[0]):
            for col in range(mask.shape[1]):
                window = mask[max(0, row - pad):min(mask.shape[0], row + pad + 1), max(0, col - pad):min(mask.shape[1], col + pad + 1)]
                if window.size and np.any(window):
                    out[row, col] = 1
        return out
