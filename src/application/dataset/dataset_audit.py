"""
Orquestrador central e fachada de auditoria avançada de datasets YOLOv11.
Integra validação estrutural, estatísticas descritivas e diagnóstico de balanceamento.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from src.application.dataset.dataset_validator import DatasetValidator, DatasetValidationReport
from src.application.dataset.dataset_statistics import DatasetStatisticsCalculator, DatasetStatistics
from src.application.dataset.balance_analyzer import DatasetBalanceAnalyzer, BalanceAnalysisResult, BalanceSeverity
from src.infrastructure.ml.dataset_loader import PV_CLASSES
from src.core.logger import get_logger

logger = get_logger("DatasetAuditor")


@dataclass
class DatasetAuditResult:
    """Resultado executivo consolidado da auditoria de dataset."""
    dataset_path: str
    is_approved_for_training: bool
    audit_timestamp: datetime
    validation: DatasetValidationReport
    statistics: DatasetStatistics
    balance: BalanceAnalysisResult
    executive_summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o resultado da auditoria em formato serializável."""
        return {
            "dataset_path": self.dataset_path,
            "is_approved_for_training": self.is_approved_for_training,
            "audit_timestamp": self.audit_timestamp.isoformat(),
            "summary": {
                "total_images": self.validation.total_images,
                "total_annotations": self.statistics.total_annotations,
                "orphan_labels_count": len(self.validation.orphan_labels),
                "images_without_label_count": len(self.validation.images_without_label_file),
                "invalid_classes_count": len(self.validation.invalid_class_errors),
                "balance_severity": self.balance.severity.value,
                "imbalance_ratio": self.balance.imbalance_ratio,
            },
            "class_distribution": {
                item.class_name: {
                    "count": item.instance_count,
                    "percentage": item.percentage,
                }
                for item in self.statistics.class_distribution
            },
            "recommendations": self.balance.recommendations,
        }


class DatasetAuditor:
    """
    Fachada que executa a auditoria completa de um dataset YOLOv11 para o SolarGuard Vision.
    """

    def __init__(self, allowed_classes: Optional[Dict[int, str]] = None) -> None:
        self.explicit_classes = allowed_classes is not None
        self.allowed_classes = allowed_classes or PV_CLASSES
        self.validator = DatasetValidator(allowed_classes=self.allowed_classes)
        self.stats_calculator = DatasetStatisticsCalculator(allowed_classes=self.allowed_classes)

    def _resolve_classes_from_path(self, path: Path) -> Dict[int, str]:
        """Tenta inferir classes a partir do data.yaml se não fornecidas explicitamente."""
        yaml_file = path if path.is_file() and path.suffix.lower() in [".yaml", ".yml"] else path / "data.yaml"
        if yaml_file.exists():
            try:
                import yaml
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and "names" in data:
                    raw_names = data["names"]
                    if isinstance(raw_names, list):
                        return {idx: str(name) for idx, name in enumerate(raw_names)}
                    elif isinstance(raw_names, dict):
                        return {int(idx): str(name) for idx, name in raw_names.items()}
            except Exception as ex:
                logger.warning(f"Não foi possível carregar classes de {yaml_file}: {ex}")
        return self.allowed_classes

    def audit(self, dataset_path: str | Path) -> DatasetAuditResult:
        """
        Executa todas as etapas de auditoria e emite diagnóstico executivo.
        
        :param dataset_path: Caminho raiz do dataset YOLO ou caminho para data.yaml.
        :return: DatasetAuditResult consolidado.
        """
        path = Path(dataset_path).resolve()
        logger.info(f"Iniciando auditoria completa do dataset: {path}")

        # Se classes não foram explicitadas, tenta resolver via data.yaml
        if not self.explicit_classes:
            resolved_classes = self._resolve_classes_from_path(path)
            self.allowed_classes = resolved_classes
            self.validator = DatasetValidator(allowed_classes=resolved_classes)
            self.stats_calculator = DatasetStatisticsCalculator(allowed_classes=resolved_classes)

        # 1. Validação Estrutural e Sintática
        val_report = self.validator.validate(path)

        # 2. Cálculo Estatístico
        stats = self.stats_calculator.calculate(val_report)

        # 3. Análise de Balanceamento
        balance = DatasetBalanceAnalyzer.analyze(stats.counts_by_class_name)

        # 4. Critério de Aprovação para Treinamento
        # Um dataset só é aprovado se:
        # - Possuir imagens e anotações (> 0)
        # - Não possuir labels órfãos
        # - Não possuir classes inválidas desconhecidas
        # - Não possuir classes completamente zeradas (vazias)
        has_critical_errors = (
            val_report.total_images == 0
            or stats.total_annotations == 0
            or len(val_report.orphan_labels) > 0
            or len(val_report.invalid_class_errors) > 0
            or len(balance.empty_classes) > 0
        )

        is_approved = not has_critical_errors

        # Resumo executivo textual
        if is_approved:
            summary = (
                f"Dataset APROVADO para treinamento YOLOv11. Total de {val_report.total_images} imagens "
                f"e {stats.total_annotations} anotações íntegras. "
                f"Status de balanceamento: {balance.severity.display_name}."
            )
        else:
            reasons = []
            if val_report.total_images == 0:
                reasons.append("nenhuma imagem encontrada")
            if len(val_report.orphan_labels) > 0:
                reasons.append(f"{len(val_report.orphan_labels)} labels órfãos sem imagem")
            if len(val_report.invalid_class_errors) > 0:
                reasons.append(f"{len(val_report.invalid_class_errors)} anotações com classes inválidas")
            if len(balance.empty_classes) > 0:
                reasons.append(f"classes sem amostras: {balance.empty_classes}")

            summary = f"Dataset REPROVADO para treinamento imediato. Pendências críticas: {'; '.join(reasons)}."

        result = DatasetAuditResult(
            dataset_path=str(path),
            is_approved_for_training=is_approved,
            audit_timestamp=datetime.now(),
            validation=val_report,
            statistics=stats,
            balance=balance,
            executive_summary=summary,
        )

        logger.info(f"Auditoria concluída. Aprovado: {is_approved}. {summary}")
        return result
