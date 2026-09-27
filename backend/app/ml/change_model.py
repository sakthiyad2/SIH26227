import numpy as np


class ChangeDetector:
    def detect(self, before, after):
        raise NotImplementedError

    def calculate_confidence(self, mask, quality_score):
        raise NotImplementedError

    def classify_change(self, before, after):
        raise NotImplementedError


class BaselineChangeDetector(ChangeDetector):
    def detect(self, before, after):
        before = np.asarray(before, dtype=np.float32)
        after = np.asarray(after, dtype=np.float32)
        diff = np.abs(after - before)
        mask = diff > 25
        return mask.astype(np.uint8)

    def calculate_confidence(self, mask, quality_score):
        change_ratio = float(np.mean(mask)) if hasattr(mask, 'mean') else 0.0
        confidence = min(1.0, max(0.0, change_ratio * 2.0 + quality_score * 0.5))
        return round(confidence, 4)

    def classify_change(self, before, after):
        before_values = np.asarray(before).mean()
        after_values = np.asarray(after).mean()
        if after_values > before_values + 8:
            return "construction"
        if after_values < before_values - 8:
            return "clearance"
        return "vegetation change"
