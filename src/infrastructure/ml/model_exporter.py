"""
Módulo de Exportação e Empacotamento de Pesos (best.pt e ONNX) para o SolarGuard Vision.
Salva pesos com manifesto de metadados, checksum SHA256 e validação de classes.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import shutil
import hashlib
import json
from datetime import datetime

from src.infrastructure.ml.training_metrics import ValidationMetrics
from src.infrastructure.ml.dataset_loader import PV_CLASSES
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("ModelExporter")


class ModelExporter:
    """
    Gerencia a exportação, versionamento e distribuição dos pesos treinados do YOLOv11.
    """

    def __init__(self, models_dir: Optional[Path | str] = None) -> None:
        self.models_dir = Path(models_dir) if models_dir else settings.models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calcula o hash SHA256 do arquivo para validação de integridade."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def export_best_weights(
        self,
        source_weights: str | Path,
        model_name: str = "best.pt",
        metrics: Optional[ValidationMetrics] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Copia e registra o arquivo best.pt gerado pelo treinamento no diretório oficial de modelos,
        acompanhado por um manifesto JSON com métricas e checksum de segurança.
        
        :param source_weights: Caminho do arquivo best.pt original (dentro de runs/detect/...).
        :param model_name: Nome de destino do arquivo (padrão: best.pt ou solarguard_best.pt).
        :param metrics: Métricas de validação obtidas pelo modelo.
        :param extra_metadata: Dados adicionais de versão, dataset ou parâmetros de treino.
        :return: Path do arquivo de pesos exportado em models/.
        """
        source_weights = Path(source_weights).resolve()
        if not source_weights.exists():
            raise FileNotFoundError(f"Arquivo de pesos original não encontrado: {source_weights}")

        target_weights = self.models_dir / model_name
        shutil.copy2(source_weights, target_weights)
        checksum = self.calculate_sha256(target_weights)

        # Manifesto com metadados do modelo de IA
        manifest: Dict[str, Any] = {
            "model_name": model_name,
            "architecture": "YOLOv11",
            "framework": "Ultralytics / PyTorch",
            "exported_at": datetime.now().isoformat(),
            "sha256": checksum,
            "classes": PV_CLASSES,
            "num_classes": len(PV_CLASSES),
        }

        if metrics:
            manifest["metrics"] = metrics.to_dict()

        if extra_metadata:
            manifest["extra_metadata"] = extra_metadata

        manifest_path = target_weights.with_suffix(".json")
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Modelo {model_name} exportado com sucesso para {target_weights} (SHA256: {checksum[:8]}...)")
        return target_weights

    def export_to_onnx(
        self,
        weights_path: str | Path,
        imgsz: int = 640,
        dynamic: bool = False,
        opset: int = 17,
    ) -> Path:
        """
        Converte o modelo PyTorch (.pt) para formato aberto ONNX para inferência otimizada.
        """
        from ultralytics import YOLO

        weights_path = Path(weights_path).resolve()
        if not weights_path.exists():
            raise FileNotFoundError(f"Pesos para exportação ONNX não encontrados: {weights_path}")

        logger.info(f"Iniciando exportação para ONNX (imgsz={imgsz}, opset={opset})...")
        model = YOLO(str(weights_path))
        onnx_file = model.export(format="onnx", imgsz=imgsz, dynamic=dynamic, opset=opset)

        onnx_path = Path(onnx_file).resolve()
        logger.info(f"Modelo ONNX gerado com sucesso: {onnx_path}")
        return onnx_path
