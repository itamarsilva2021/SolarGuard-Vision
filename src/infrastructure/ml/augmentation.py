"""
Módulo de Aumento de Dados (Data Augmentation) especializado para Termografia Fotovoltaica.
Configurações integradas para o YOLOv11 e rotinas de aumento offline para pequenos datasets.
"""

from typing import Dict, Any, List, Tuple
import random
import cv2
import numpy as np

from src.domain.value_objects.bounding_box import BoundingBox


class ThermalDataAugmentation:
    """
    Estratégias de Data Augmentation calibradas para imagens térmicas aéreas de usinas solares.
    Respeita a física dos painéis solares (simetria espacial e preservação de assinaturas de calor).
    """

    @classmethod
    def get_yolo_augmentation_hyperparameters(cls) -> Dict[str, Any]:
        """
        Retorna o dicionário de hiperparâmetros de aumento de dados do Ultralytics YOLOv11
        otimizado para detecção de anomalias térmicas fotovoltaicas por drone.
        """
        return {
            # Variação sutil de matiz e intensidade térmica (simula variações de ganho de bolômetro)
            "hsv_h": 0.015,  # Variação mínima de matiz (cores térmicas tem significado físico)
            "hsv_s": 0.40,   # Saturação moderada
            "hsv_v": 0.35,   # Brilho/Intensidade (simula voos sob diferentes irradiâncias solares)
            
            # Variações geométricas (simula oscilações e altitude do drone DJI)
            "degrees": 10.0,      # Rotação angular angular leve (+- 10 graus)
            "translate": 0.10,    # Translação de enquadramento
            "scale": 0.40,        # Escala (+- 40%, simulando altitudes de voo de 15m a 45m)
            "shear": 2.0,         # Deformação em corte leve
            "perspective": 0.0005, # Deformação de perspectiva
            
            # Espelhamento espacial (válido pois fileiras solares são simétricas)
            "fliplr": 0.5,        # Espelhamento horizontal (50% de probabilidade)
            "flipud": 0.5,        # Espelhamento vertical (50% de probabilidade)
            
            # Mosaico e Composição (essenciais para detecção de hotspots minúsculos)
            "mosaic": 1.0,        # Mosaico ativado (combina 4 imagens em 1)
            "mixup": 0.15,        # Mixup leve
            "copy_paste": 0.10,   # Copy-paste de caixas de hotspot
        }

    @staticmethod
    def horizontal_flip(
        image: np.ndarray, bboxes: List[Tuple[int, float, float, float, float]]
    ) -> Tuple[np.ndarray, List[Tuple[int, float, float, float, float]]]:
        """
        Espelha a imagem horizontalmente e recalcula as coordenadas normalizadas YOLO [x_center, y_center, w, h].
        """
        flipped_img = cv2.flip(image, 1)
        flipped_bboxes = []
        for cls_id, cx, cy, w, h in bboxes:
            new_cx = 1.0 - cx
            flipped_bboxes.append((cls_id, round(new_cx, 4), cy, w, h))
        return flipped_img, flipped_bboxes

    @staticmethod
    def vertical_flip(
        image: np.ndarray, bboxes: List[Tuple[int, float, float, float, float]]
    ) -> Tuple[np.ndarray, List[Tuple[int, float, float, float, float]]]:
        """
        Espelha a imagem verticalmente e recalcula as coordenadas normalizadas YOLO.
        """
        flipped_img = cv2.flip(image, 0)
        flipped_bboxes = []
        for cls_id, cx, cy, w, h in bboxes:
            new_cy = 1.0 - cy
            flipped_bboxes.append((cls_id, cx, round(new_cy, 4), w, h))
        return flipped_img, flipped_bboxes

    @staticmethod
    def inject_thermal_sensor_noise(image: np.ndarray, sigma: float = 6.0) -> np.ndarray:
        """
        Injeta ruído gaussiano simulando o ruído intrínseco (NETD) de sensores termográficos não refrigerados.
        """
        noise = np.random.normal(0, sigma, image.shape).astype(np.float32)
        noisy_image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return noisy_image

    @staticmethod
    def adjust_thermal_contrast_and_gain(
        image: np.ndarray, alpha: float = 1.15, beta: float = -10.0
    ) -> np.ndarray:
        """
        Ajusta contraste e ganho da imagem para simular mudanças de irradiação solar incidente.
        """
        adjusted = np.clip(image.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
        return adjusted
