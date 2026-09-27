import numpy as np


class QualityModel:
    def score(self, cloud_cover: float, valid_pixels: float, registration_quality: float, illumination_consistency: float, overlap_ratio: float, sensor_compatibility: float) -> float:
        score = (
            (1.0 - cloud_cover) * 0.25
            + valid_pixels * 0.25
            + registration_quality * 0.2
            + illumination_consistency * 0.15
            + overlap_ratio * 0.1
            + sensor_compatibility * 0.05
        )
        return float(np.clip(score, 0.0, 1.0))
