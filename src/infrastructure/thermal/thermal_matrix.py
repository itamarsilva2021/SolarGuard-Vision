"""
Estrutura de Dados Científica de Matriz Térmica Calibrada (ScientificThermalMatrix).
Encapsula os valores de temperatura pontual por pixel (°C), metadados de calibração utilizados
e métodos estatísticos de alta precisão para diagnóstico pericial.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, List
import numpy as np
import cv2

from src.domain.value_objects.thermal_metrics import ThermalMetrics
from src.domain.value_objects.thermal_matrix_meta import ThermalMatrixMeta
from src.domain.enums.severity_level import SeverityLevel


@dataclass
class RadiometricMetadata:
    """Parâmetros físicos e ambientais empregados na calibração da matriz."""
    emissivity: float
    reflected_temp_celsius: float
    ambient_temp_celsius: float
    atmospheric_transmittance: float
    distance_meters: float
    relative_humidity: float
    sensor_profile: str
    camera_model: str = "DJI Matrice 4T Thermal"


class ScientificThermalMatrix:
    """
    Matriz radiométrica científica de alta fidelidade com temperaturas absolutas por pixel.
    Suporta fatiamento (ROI), estatísticas zonais, cálculo de gradientes e compatibilidade nativa com NumPy.
    """

    def __init__(
        self,
        data: np.ndarray,
        metadata: RadiometricMetadata,
    ) -> None:
        if data.ndim != 2:
            raise ValueError(f"A matriz térmica deve ser estritamente 2D. Dimensões fornecidas: {data.ndim}")

        self._data = data.astype(np.float32)
        self.metadata = metadata
        self.height, self.width = self._data.shape

    @property
    def data(self) -> np.ndarray:
        """Array bidimensional float32 com valores de temperatura em graus Celsius (°C)."""
        return self._data

    @property
    def shape(self) -> Tuple[int, int]:
        return self._data.shape

    @property
    def size(self) -> int:
        return self._data.size

    @property
    def ndim(self) -> int:
        return self._data.ndim

    @property
    def dtype(self):
        return self._data.dtype

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, item):
        return self._data[item]

    @property
    def min_temp(self) -> float:
        return round(float(np.min(self._data)), 2)

    @property
    def max_temp(self) -> float:
        return round(float(np.max(self._data)), 2)

    @property
    def mean_temp(self) -> float:
        return round(float(np.mean(self._data)), 2)

    @property
    def median_temp(self) -> float:
        return round(float(np.median(self._data)), 2)

    def __array__(self) -> np.ndarray:
        """Permite que a instância seja passada diretamente para funções NumPy e OpenCV."""
        return self._data

    def get_temperature_at(self, x: int, y: int) -> float:
        """Retorna a temperatura pontual exata do pixel (x, y) em °C."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Coordenadas ({x}, {y}) fora dos limites da matriz ({self.width}x{self.height}).")
        return round(float(self._data[y, x]), 2)

    def get_roi(self, x1: int, y1: int, x2: int, y2: int) -> "ScientificThermalMatrix":
        """
        Extrai uma sub-região de interesse (ROI) preservando os metadados de calibração.
        """
        x_start = max(0, min(x1, x2))
        x_end = min(self.width, max(x1, x2))
        y_start = max(0, min(y1, y2))
        y_end = min(self.height, max(y1, y2))

        sub_data = self._data[y_start:y_end, x_start:x_end].copy()
        if sub_data.size == 0:
            raise ValueError(f"Região delimitada inválida ou com área zero: ({x1},{y1}) a ({x2},{y2})")

        return ScientificThermalMatrix(sub_data, self.metadata)

    def calculate_metrics(
        self,
        reference_temp: Optional[float] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> ThermalMetrics:
        """
        Calcula estatísticas térmicas zonais ou globais e gradiente Delta T conforme IEC TS 62446-3.
        
        :param reference_temp: Temperatura de referência (módulo saudável). Se None, usa a mediana da cena.
        :param roi: Bounding box opcional (x1, y1, x2, y2).
        :return: Objeto ThermalMetrics com todas as métricas calculadas.
        """
        target_matrix = self._data
        offset_x, offset_y = 0, 0

        if roi:
            x1, y1, x2, y2 = roi
            x_start, x_end = max(0, min(x1, x2)), min(self.width, max(x1, x2))
            y_start, y_end = max(0, min(y1, y2)), min(self.height, max(y1, y2))
            target_matrix = self._data[y_start:y_end, x_start:x_end]
            offset_x, offset_y = x_start, y_start

        min_val = float(np.min(target_matrix))
        max_val = float(np.max(target_matrix))
        avg_val = float(np.mean(target_matrix))
        median_val = float(np.median(target_matrix))
        std_val = float(np.std(target_matrix))

        min_idx = np.unravel_index(np.argmin(target_matrix), target_matrix.shape)
        max_idx = np.unravel_index(np.argmax(target_matrix), target_matrix.shape)

        min_loc = (int(min_idx[1]) + offset_x, int(min_idx[0]) + offset_y)
        max_loc = (int(max_idx[1]) + offset_x, int(max_idx[0]) + offset_y)

        ref = float(reference_temp) if reference_temp is not None else median_val
        delta_val = round(max_val - ref, 2)
        severity = SeverityLevel.from_delta_t(delta_val)

        return ThermalMetrics(
            min_temp=round(min_val, 2),
            max_temp=round(max_val, 2),
            avg_temp=round(avg_val, 2),
            median_temp=round(median_val, 2),
            std_temp=round(std_val, 2),
            delta_t=delta_val,
            max_location=max_loc,
            min_location=min_loc,
            ref_temp=round(ref, 2),
            severity=severity,
        )

    def calculate_gradient_magnitude(self) -> np.ndarray:
        """
        Calcula a magnitude do gradiente térmico espacial (|nabla T|) em °C por pixel.
        Útil para detectar bordas de células fotovoltaicas rachadas ou pontos quentes isolados.
        """
        grad_x = cv2.Sobel(self._data, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(self._data, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = np.sqrt(grad_x ** 2 + grad_y ** 2)
        return np.round(magnitude, 2)

    def to_domain_meta(self) -> ThermalMatrixMeta:
        """Exporta para a estrutura de metadados do domínio (ThermalMatrixMeta)."""
        return ThermalMatrixMeta(
            emissivity=self.metadata.emissivity,
            reflected_temp_celsius=self.metadata.reflected_temp_celsius,
            ambient_temp_celsius=self.metadata.ambient_temp_celsius,
            relative_humidity=self.metadata.relative_humidity,
            distance_meters=self.metadata.distance_meters,
            min_temp_celsius=self.min_temp,
            max_temp_celsius=self.max_temp,
            avg_temp_celsius=self.mean_temp,
            sensor_width=self.width,
            sensor_height=self.height,
        )
