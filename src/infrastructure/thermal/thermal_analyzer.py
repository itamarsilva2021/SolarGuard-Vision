"""
Módulo de Análise Termográfica Quantitativa e Diagnóstico Normativo (IEC TS 62446-3).
Implementa ThermalAnalyzer para cálculo de gradientes térmicos (Delta T) e detecção de pontos quentes.
"""

from typing import Optional, List, Tuple
import cv2
import numpy as np

from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.delta_t import DeltaT
from src.domain.value_objects.thermal_metrics import ThermalMetrics
from src.domain.enums.severity_level import SeverityLevel
from src.core.logger import get_logger

logger = get_logger("ThermalAnalyzer")


class ThermalAnalyzer:
    """
    Motor analítico para quantificação termográfica de usinas fotovoltaicas.
    Executa cálculos de gradiente térmico (Delta T), estatísticas zonais,
    detecção de picos de calor e classificação automática conforme IEC TS 62446-3.
    """

    def calculate_delta_t(self, t_target: float, t_reference: float) -> DeltaT:
        """
        Calcula o diferencial térmico (Delta T) entre um ponto/região de interesse
        e uma temperatura de referência (módulo saudável adjacente ou ambiente).
        
        :param t_target: Temperatura máxima medida na região do defeito (°C).
        :param t_reference: Temperatura de referência do módulo saudável (°C).
        :return: Objeto de valor DeltaT com classificação IEC TS 62446-3 embutida.
        """
        return DeltaT(t_max_celsius=float(t_target), t_ref_celsius=float(t_reference))

    def analyze_matrix(
        self,
        matrix: np.ndarray,
        ref_temp: Optional[float] = None,
    ) -> ThermalMetrics:
        """
        Calcula métricas quantitativas completas de uma matriz térmica 2D.
        
        :param matrix: Matriz bidimensional de temperaturas em float32 (°C).
        :param ref_temp: Temperatura de referência manual. Se None, utiliza a mediana.
        :return: Objeto ThermalMetrics com todas as medições estatísticas.
        """
        if matrix.size == 0:
            raise ValueError("A matriz térmica fornecida está vazia.")

        min_val = float(np.min(matrix))
        max_val = float(np.max(matrix))
        avg_val = float(np.mean(matrix))
        median_val = float(np.median(matrix))
        std_val = float(np.std(matrix))

        # Localização dos extremos em pixels (x, y)
        min_idx = np.unravel_index(np.argmin(matrix), matrix.shape)
        max_idx = np.unravel_index(np.argmax(matrix), matrix.shape)

        min_location = (int(min_idx[1]), int(min_idx[0]))
        max_location = (int(max_idx[1]), int(max_idx[0]))

        # Temperatura de referência: mediana da cena (representa a operação nominal)
        chosen_ref = float(ref_temp) if ref_temp is not None else median_val
        delta_val = round(max_val - chosen_ref, 2)
        severity = SeverityLevel.from_delta_t(delta_val)

        return ThermalMetrics(
            min_temp=round(min_val, 2),
            max_temp=round(max_val, 2),
            avg_temp=round(avg_val, 2),
            median_temp=round(median_val, 2),
            std_temp=round(std_val, 2),
            delta_t=delta_val,
            max_location=max_location,
            min_location=min_location,
            ref_temp=round(chosen_ref, 2),
            severity=severity,
        )

    def extract_submatrix(self, matrix: np.ndarray, bbox: BoundingBox) -> np.ndarray:
        """
        Extrai o recorte da matriz térmica correspondente à bounding box,
        com proteção de limites e suporte a coordenadas normalizadas ou absolutas.
        """
        h, w = matrix.shape[:2]
        pixel_bbox = bbox.to_pixels(w, h)

        x1 = max(0, min(w - 1, int(pixel_bbox.x_min)))
        y1 = max(0, min(h - 1, int(pixel_bbox.y_min)))
        x2 = max(x1 + 1, min(w, int(pixel_bbox.x_max)))
        y2 = max(y1 + 1, min(h, int(pixel_bbox.y_max)))

        return matrix[y1:y2, x1:x2]

    def analyze_region(
        self,
        matrix: np.ndarray,
        bbox: BoundingBox,
        ref_temp: Optional[float] = None,
    ) -> ThermalMetrics:
        """
        Analisa uma região recortada (ex: um módulo solar ou uma caixa de anomalia)
        e mapeia as coordenadas máximas para o sistema global da imagem.
        """
        h, w = matrix.shape[:2]
        pixel_bbox = bbox.to_pixels(w, h)

        x1 = max(0, min(w - 1, int(pixel_bbox.x_min)))
        y1 = max(0, min(h - 1, int(pixel_bbox.y_min)))
        x2 = max(x1 + 1, min(w, int(pixel_bbox.x_max)))
        y2 = max(y1 + 1, min(h, int(pixel_bbox.y_max)))

        sub = matrix[y1:y2, x1:x2]
        if sub.size == 0:
            raise ValueError("Região demarcada pela bounding box possui dimensão nula.")

        # Se ref_temp não foi dada, calcula da mediana do fundo externo à caixa
        if ref_temp is None:
            # Mediana geral da imagem como linha de base
            chosen_ref = float(np.median(matrix))
        else:
            chosen_ref = float(ref_temp)

        min_val = float(np.min(sub))
        max_val = float(np.max(sub))
        avg_val = float(np.mean(sub))
        median_val = float(np.median(sub))
        std_val = float(np.std(sub))

        # Localização relativa na submatriz
        local_min = np.unravel_index(np.argmin(sub), sub.shape)
        local_max = np.unravel_index(np.argmax(sub), sub.shape)

        # Mapeia de volta para coordenadas globais da imagem original
        global_min = (int(x1 + local_min[1]), int(y1 + local_min[0]))
        global_max = (int(x1 + local_max[1]), int(y1 + local_max[0]))

        delta_val = round(max_val - chosen_ref, 2)
        severity = SeverityLevel.from_delta_t(delta_val)

        return ThermalMetrics(
            min_temp=round(min_val, 2),
            max_temp=round(max_val, 2),
            avg_temp=round(avg_val, 2),
            median_temp=round(median_val, 2),
            std_temp=round(std_val, 2),
            delta_t=delta_val,
            max_location=global_max,
            min_location=global_min,
            ref_temp=round(chosen_ref, 2),
            severity=severity,
        )

    def find_hotspots(
        self,
        matrix: np.ndarray,
        min_delta_celsius: float = 8.0,
        min_area_pixels: int = 4,
        max_results: int = 15,
    ) -> list[dict]:
        """
        Detecta hotspots automaticamente através de limiarização adaptativa e componentes conexos.
        Útil como motor heurístico e validação cruzada com o modelo de IA.
        
        :param matrix: Matriz térmica 2D float32.
        :param min_delta_celsius: Gradiente mínimo acima da mediana para ser considerado candidato.
        :param min_area_pixels: Área mínima de pixels para filtrar ruído de sensor.
        :param max_results: Quantidade máxima de pontos retornados.
        :return: Lista de dicionários com bbox, max_temp, delta_t, location e severity.
        """
        h, w = matrix.shape[:2]
        baseline = float(np.median(matrix))
        threshold_temp = baseline + min_delta_celsius

        hot_mask = (matrix >= threshold_temp).astype(np.uint8) * 255

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            hot_mask, connectivity=8
        )

        candidates = []
        for label_id in range(1, num_labels):
            area = stats[label_id, cv2.CC_STAT_AREA]
            if area < min_area_pixels:
                continue

            x = stats[label_id, cv2.CC_STAT_LEFT]
            y = stats[label_id, cv2.CC_STAT_TOP]
            bw = stats[label_id, cv2.CC_STAT_WIDTH]
            bh = stats[label_id, cv2.CC_STAT_HEIGHT]

            sub_mask = (labels[y : y + bh, x : x + bw] == label_id)
            sub_temps = matrix[y : y + bh, x : x + bw]
            peak_temp = float(np.max(sub_temps[sub_mask]))

            local_peak = np.unravel_index(np.argmax(sub_temps * sub_mask), sub_temps.shape)
            peak_x = int(x + local_peak[1])
            peak_y = int(y + local_peak[0])

            delta_t = round(peak_temp - baseline, 2)
            severity = SeverityLevel.from_delta_t(delta_t)

            bbox = BoundingBox(
                x_min=round(x / w, 4),
                y_min=round(y / h, 4),
                x_max=round((x + bw) / w, 4),
                y_max=round((y + bh) / h, 4),
                is_normalized=True,
            )

            candidates.append({
                "bbox": bbox,
                "peak_temperature": peak_temp,
                "delta_t": delta_t,
                "peak_location": (peak_x, peak_y),
                "severity": severity,
                "area_pixels": area,
            })

        # Ordenar pelos maiores gradientes térmicos Delta T
        candidates.sort(key=lambda c: c["delta_t"], reverse=True)
        return candidates[:max_results]

    def compare_modules(
        self,
        module_a_matrix: np.ndarray,
        module_b_matrix: np.ndarray,
    ) -> dict:
        """
        Compara a assinatura térmica entre dois módulos adjacentes da mesma string.
        Identifica módulos desconectados ou operando em circuito aberto.
        """
        avg_a = float(np.mean(module_a_matrix))
        avg_b = float(np.mean(module_b_matrix))
        delta_avg = round(abs(avg_a - avg_b), 2)

        max_a = float(np.max(module_a_matrix))
        max_b = float(np.max(module_b_matrix))
        delta_max = round(abs(max_a - max_b), 2)

        # Módulos desconectados geralmente aquecem de forma homogênea entre 3°C e 8°C a mais
        is_suspicious_disconnected = bool(3.0 <= delta_avg <= 15.0 and float(np.std(module_a_matrix)) < 4.0)

        return {
            "module_a_avg": round(avg_a, 2),
            "module_b_avg": round(avg_b, 2),
            "delta_avg_celsius": delta_avg,
            "delta_max_celsius": delta_max,
            "severity": SeverityLevel.from_delta_t(delta_max),
            "possible_disconnected_module": is_suspicious_disconnected,
        }
