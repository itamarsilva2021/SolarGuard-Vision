"""
Módulo de Carregamento e Gerenciamento do Modelo YOLOv11.
Implementa a classe ModelLoader com suporte a aceleração por hardware (CUDA/CPU) e cache de modelo.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import torch

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("ModelLoader")


class ModelLoader:
    """
    Carregador e gerenciador de ciclo de vida de modelos YOLOv11.
    Garante inicialização segura com detecção automática de GPU CUDA, fallback para CPU,
    e cache em memória para evitar re-carregamentos desnecessários durante inspeções em lote.
    """

    _cached_model = None
    _cached_weights_path: Optional[str] = None
    _cached_device: Optional[str] = None

    @classmethod
    def get_optimal_device(cls, preferred_device: str = "auto") -> str:
        """
        Detecta e seleciona o dispositivo de computação mais veloz disponível.
        
        :param preferred_device: 'auto', 'cuda', '0', 'cpu'.
        :return: String indicando o dispositivo ('cuda:0' ou 'cpu').
        """
        if preferred_device != "auto":
            return preferred_device

        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"GPU CUDA detectada e ativada: {device_name}")
            return "cuda:0"
        
        logger.info("Nenhuma GPU CUDA detectada. Utilizando CPU para inferência.")
        return "cpu"

    @classmethod
    def resolve_model_path(cls, custom_path: Optional[str | Path] = None) -> Path:
        """
        Localiza os pesos do modelo YOLOv11 no sistema.
        Prioridade:
        1. Caminho customizado fornecido.
        2. models/best.pt oficial.
        3. models/solarguard_yolo11_best.pt
        4. yolo11n.pt (fallback padrão da Ultralytics).
        """
        if custom_path:
            p = Path(custom_path)
            if p.exists():
                return p
            raise FileNotFoundError(f"Pesos do modelo especificados não existem: {custom_path}")

        candidates = [
            settings.models_dir / "best.pt",
            settings.models_dir / "solarguard_yolo11_best.pt",
            settings.models_dir / "yolo11n.pt",
            Path("yolo11n.pt"),
        ]

        for cand in candidates:
            if cand.exists():
                return cand.resolve()

        # Se nenhum peso treinado local foi encontrado, retorna o padrão para download automático da Ultralytics
        return Path("yolo11n.pt")

    @classmethod
    def load_model(
        cls,
        model_path: Optional[str | Path] = None,
        device: str = "auto",
        force_reload: bool = False,
    ):
        """
        Carrega a instância do modelo YOLOv11 com cache em memória.
        
        :param model_path: Caminho para os pesos .pt.
        :param device: Dispositivo de execução ('auto', 'cpu', 'cuda:0').
        :param force_reload: Se True, ignora o cache e recarrega do disco.
        :return: Instância de ultralytics.YOLO pronta para predição.
        """
        from ultralytics import YOLO

        resolved_path = cls.resolve_model_path(model_path)
        target_device = cls.get_optimal_device(device)

        path_str = str(resolved_path)

        # Retorna instância já em cache caso os parâmetros sejam idênticos
        if (
            not force_reload
            and cls._cached_model is not None
            and cls._cached_weights_path == path_str
            and cls._cached_device == target_device
        ):
            return cls._cached_model

        logger.info(f"Carregando YOLOv11 de '{path_str}' no dispositivo [{target_device}]...")
        model = YOLO(path_str)
        model.to(target_device)

        cls._cached_model = model
        cls._cached_weights_path = path_str
        cls._cached_device = target_device

        logger.info("Modelo YOLOv11 carregado e pronto para inferência.")
        return model

    @classmethod
    def warmup(cls, imgsz: int = 640) -> None:
        """Executa uma inferência vazia para inicializar caches e buffers da GPU/CPU."""
        if cls._cached_model is not None:
            try:
                import numpy as np
                dummy = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
                cls._cached_model.predict(dummy, verbose=False)
                logger.info("Warmup do modelo executado com sucesso.")
            except Exception as ex:
                logger.warning(f"Não foi possível executar o warmup do modelo: {ex}")

    @classmethod
    def clear_cache(cls) -> None:
        """Libera a memória e remove a instância em cache."""
        cls._cached_model = None
        cls._cached_weights_path = None
        cls._cached_device = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
