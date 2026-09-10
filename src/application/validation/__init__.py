"""
Pacote de validação científica de modelos e métricas avançadas do SolarGuard Vision.
"""

from src.application.validation.classification_metrics import (
    ClassMetrics,
    GlobalClassificationMetrics,
    ClassificationMetricsCalculator,
)
from src.application.validation.confusion_matrix_service import ConfusionMatrixService
from src.application.validation.roc_curve_service import RocCurveData, RocCurveService
from src.application.validation.benchmark_service import ModelBenchmarkResult, BenchmarkService
from src.application.validation.scientific_validation_report import (
    ScientificValidationReportData,
    ScientificValidationReport,
)

__all__ = [
    "ClassMetrics",
    "GlobalClassificationMetrics",
    "ClassificationMetricsCalculator",
    "ConfusionMatrixService",
    "RocCurveData",
    "RocCurveService",
    "ModelBenchmarkResult",
    "BenchmarkService",
    "ScientificValidationReportData",
    "ScientificValidationReport",
]
