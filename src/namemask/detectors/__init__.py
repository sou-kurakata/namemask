"""検出層。"""

from namemask.detectors.base import Detector
from namemask.detectors.normalizing import (
    FoldNormalizingDetector,
    NormalizingDetector,
    ShadowDetector,
)
from namemask.detectors.stub import GoldenStubDetector

__all__ = [
    "Detector",
    "FoldNormalizingDetector",
    "GoldenStubDetector",
    "NormalizingDetector",
    "ShadowDetector",
]
