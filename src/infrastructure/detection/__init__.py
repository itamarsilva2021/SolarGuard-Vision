"""
Módulo da Engine de Detecção e Reconhecimento de Anomalias Térmicas.
Exporta ModelLoader, DefectClassifier e Detector.
"""

from src.infrastructure.detection.model_loader import ModelLoader
from src.infrastructure.detection.defect_classifier import DefectClassifier
from src.infrastructure.detection.detector import Detector

__all__ = [
    "ModelLoader",
    "DefectClassifier",
    "Detector",
]
