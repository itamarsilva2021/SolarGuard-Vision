"""
Serviço de Aplicação para Orquestração do Pipeline de Treinamento, Validação e Exportação do YOLOv11.
"""

from pathlib import Path
from typing import Optional
import time

from src.core.result import Result, Success, Failure
from src.core.logger import get_logger
from src.infrastructure.ml.dataset_loader import YoloDatasetLoader
from src.infrastructure.ml.yolo_trainer import YoloV11Trainer
from src.infrastructure.ml.yolo_validator import YoloV11Validator
from src.infrastructure.ml.model_exporter import ModelExporter
from src.application.dtos.training_dtos import (
    TrainingPipelineRequest,
    TrainingPipelineResponse,
)

logger = get_logger("TrainingPipelineService")


class TrainingPipelineService:
    """
    Orquestra o ciclo completo de vida de aprendizado do YOLOv11:
    Verificação de dataset -> Treinamento -> Avaliação (mAP) -> Exportação de best.pt e manifesto.
    """

    def __init__(
        self,
        dataset_loader: Optional[YoloDatasetLoader] = None,
        trainer: Optional[YoloV11Trainer] = None,
        validator: Optional[YoloV11Validator] = None,
        exporter: Optional[ModelExporter] = None,
    ) -> None:
        self.dataset_loader = dataset_loader or YoloDatasetLoader()
        self.trainer = trainer or YoloV11Trainer()
        self.validator = validator or YoloV11Validator()
        self.exporter = exporter or ModelExporter()

    def run_pipeline(self, request: TrainingPipelineRequest) -> Result[TrainingPipelineResponse, str]:
        """
        Executa o pipeline completo de forma transacional e reportável.
        """
        start_time = time.time()
        dataset_path = Path(request.dataset_dir).resolve()

        # 1. Validar e preparar data.yaml
        if not dataset_path.exists():
            return Failure(f"Diretório do dataset não encontrado: {dataset_path}")

        yaml_path = dataset_path / "data.yaml"
        if not yaml_path.exists():
            yaml_path = self.dataset_loader.create_yaml_config(dataset_path)

        validation_summary = self.dataset_loader.validate_dataset(dataset_path)
        if not validation_summary["valid"]:
            err_msg = "; ".join(validation_summary["errors"])
            return Failure(f"Dataset inválido: {err_msg}")

        logger.info(
            f"Dataset validado: {validation_summary['train_images']} imagens de treino, "
            f"{validation_summary['val_images']} de validação."
        )

        try:
            # 2. Executar Treinamento
            best_weights_path = self.trainer.train(
                data_yaml=yaml_path,
                epochs=request.epochs,
                imgsz=request.imgsz,
                batch_size=request.batch_size,
                device=request.device,
                patience=request.patience,
                learning_rate=request.learning_rate,
                experiment_name=request.experiment_name,
            )

            # 3. Executar Validação formal
            metrics = self.validator.evaluate(
                weights_path=best_weights_path,
                data_yaml=yaml_path,
                imgsz=request.imgsz,
                device=request.device,
            )

            # 4. Exportar best.pt oficial e Manifesto JSON
            exported_weights = self.exporter.export_best_weights(
                source_weights=best_weights_path,
                model_name=request.export_model_name,
                metrics=metrics,
                extra_metadata={
                    "base_model": request.base_model,
                    "epochs": request.epochs,
                    "imgsz": request.imgsz,
                    "batch_size": request.batch_size,
                    "train_images_count": validation_summary["train_images"],
                    "val_images_count": validation_summary["val_images"],
                },
            )

            onnx_path_str = None
            if request.export_onnx:
                try:
                    onnx_path = self.exporter.export_to_onnx(exported_weights, imgsz=request.imgsz)
                    onnx_path_str = str(onnx_path)
                except Exception as onnx_err:
                    logger.warning(f"Falha na exportação secundária para ONNX: {onnx_err}")

            elapsed = round(time.time() - start_time, 2)
            manifest_file = exported_weights.with_suffix(".json")

            response = TrainingPipelineResponse(
                success=True,
                weights_path=str(exported_weights),
                manifest_path=str(manifest_file),
                metrics=metrics,
                dataset_yaml_path=str(yaml_path),
                onnx_path=onnx_path_str,
                total_time_seconds=elapsed,
                message=(
                    f"Pipeline finalizado com sucesso em {elapsed}s. "
                    f"mAP50: {metrics.map50:.4f}, mAP50-95: {metrics.map50_95:.4f}."
                ),
            )
            return Success(response)

        except Exception as ex:
            logger.error(f"Falha na execução do pipeline de treinamento: {ex}", exc_info=True)
            return Failure(f"Erro durante o pipeline: {str(ex)}")
