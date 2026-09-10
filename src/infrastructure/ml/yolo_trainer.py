"""
Módulo de Treinamento do Modelo YOLOv11 para Detecção de Anomalias Fotovoltaicas.
Encapsula o pipeline de treinamento da Ultralytics com hiperparâmetros otimizados para termografia.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from src.infrastructure.ml.augmentation import ThermalDataAugmentation
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("YoloV11Trainer")


class YoloV11Trainer:
    """
    Gerenciador de treinamento do modelo YOLOv11 (Nano, Small ou Medium)
    para reconhecimento das 6 classes de falhas em usinas solares.
    """

    def __init__(
        self,
        base_model: str = "yolo11n.pt",
        output_dir: Optional[Path | str] = None,
    ) -> None:
        """
        :param base_model: Nome do modelo base ('yolo11n.pt', 'yolo11s.pt', 'yolo11m.pt') ou caminho customizado.
        :param output_dir: Diretório raiz onde os experimentos de treino serão gravados.
        """
        self.base_model = base_model
        self.output_dir = Path(output_dir) if output_dir else settings.base_dir / "runs" / "detect"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def train(
        self,
        data_yaml: str | Path,
        epochs: int = 50,
        imgsz: int = 640,
        batch_size: int = 16,
        device: str = "auto",
        patience: int = 15,
        learning_rate: float = 0.01,
        experiment_name: Optional[str] = None,
        use_thermal_augmentations: bool = True,
        extra_args: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Inicia a rotina de treinamento supervisionado do YOLOv11.
        
        :param data_yaml: Caminho do arquivo data.yaml gerado pelo YoloDatasetLoader.
        :param epochs: Número máximo de épocas de treinamento.
        :param imgsz: Resolução da imagem de entrada (padrão 640).
        :param batch_size: Tamanho do minilote.
        :param device: Dispositivo de execução ('0' para GPU CUDA, 'cpu' ou 'auto').
        :param patience: Épocas de tolerância para Early Stopping sem melhora no mAP.
        :param learning_rate: Taxa de aprendizado inicial (lr0).
        :param experiment_name: Nome do experimento para a pasta de saída.
        :param use_thermal_augmentations: Se True, injeta hiperparâmetros calibrados para termografia.
        :param extra_args: Argumentos adicionais para a função model.train() do Ultralytics.
        :return: Path do arquivo de pesos best.pt gerado.
        """
        from ultralytics import YOLO

        data_yaml = Path(data_yaml).resolve()
        if not data_yaml.exists():
            raise FileNotFoundError(f"Arquivo data.yaml não encontrado em: {data_yaml}")

        if experiment_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            experiment_name = f"train_solarguard_{timestamp}"

        # Carregar arquitetura do modelo
        logger.info(f"Carregando modelo base: {self.base_model}")
        model = YOLO(self.base_model)

        # Configurar argumentos base de treinamento
        train_kwargs: Dict[str, Any] = {
            "data": str(data_yaml),
            "epochs": epochs,
            "imgsz": imgsz,
            "batch": batch_size,
            "patience": patience,
            "lr0": learning_rate,
            "project": str(self.output_dir),
            "name": experiment_name,
            "exist_ok": True,
            "save": True,
            "plots": True,
            "verbose": True,
        }

        # Resolução de dispositivo (auto detecta CUDA se disponível)
        if device != "auto":
            train_kwargs["device"] = device

        # Injeção dos hiperparâmetros de termografia
        if use_thermal_augmentations:
            aug_params = ThermalDataAugmentation.get_yolo_augmentation_hyperparameters()
            train_kwargs.update(aug_params)

        # Sobrescrever com argumentos extras se fornecidos
        if extra_args:
            train_kwargs.update(extra_args)

        logger.info(f"Iniciando treinamento ({epochs} épocas, imgsz={imgsz}, batch={batch_size})...")
        results = model.train(**train_kwargs)

        # Localizar o peso best.pt resultante
        save_dir = Path(results.save_dir) if hasattr(results, "save_dir") else self.output_dir / experiment_name
        best_weight = save_dir / "weights" / "best.pt"

        if not best_weight.exists():
            last_weight = save_dir / "weights" / "last.pt"
            if last_weight.exists():
                logger.warning(f"best.pt não encontrado, utilizando last.pt: {last_weight}")
                return last_weight
            raise FileNotFoundError(f"Nenhum arquivo de pesos gerado em: {save_dir / 'weights'}")

        logger.info(f"Treinamento concluído com sucesso! Pesos salvos em: {best_weight}")
        return best_weight
