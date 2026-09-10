"""
Classificador e Refinador Radiométrico de Defeitos Fotovoltaicos.
Mapeia classes de IA para a taxonomia de falhas e calcula severidade normativa IEC TS 62446-3.
"""

from typing import Optional, Dict, Tuple
import numpy as np

from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.delta_t import DeltaT
from src.domain.value_objects.thermal_metrics import ThermalMetrics
from src.infrastructure.thermal.thermal_analyzer import ThermalAnalyzer
from src.core.logger import get_logger

logger = get_logger("DefectClassifier")


class DefectClassifier:
    """
    Classificador e pós-processador radiométrico de falhas fotovoltaicas.
    
    Classes suportadas:
    - HOTSPOT: Ponto quente em célula isolada (defeito de solda, microfissura, diodo de bypass).
    - DISCONNECTED_MODULE: Módulo em circuito aberto (aquecimento homogêneo em toda a área do painel).
    - PID: Degradação Induzida por Potencial (gradiente térmico concentrado nas bordas próximas à moldura aterrada).
    - SOILING: Sujidade/poeira acumulada na superfície do vidro.
    - SHADING: Sombreamento parcial por vegetação, postes ou relevo.
    """

    # Mapeamento canônico entre identificadores/strings e o Enum de domínio
    CLASS_MAPPING: Dict[str, AnomalyType] = {
        "0": AnomalyType.HOTSPOT,
        "1": AnomalyType.DISCONNECTED_MODULE,
        "2": AnomalyType.PID,
        "3": AnomalyType.SOILING,
        "4": AnomalyType.SHADING,
        "5": AnomalyType.HEALTHY_MODULE,
        "hotspot": AnomalyType.HOTSPOT,
        "disconnected_module": AnomalyType.DISCONNECTED_MODULE,
        "modulo_desconectado": AnomalyType.DISCONNECTED_MODULE,
        "pid": AnomalyType.PID,
        "soiling": AnomalyType.SOILING,
        "sujidade": AnomalyType.SOILING,
        "shading": AnomalyType.SHADING,
        "sombreamento": AnomalyType.SHADING,
        "healthy_module": AnomalyType.HEALTHY_MODULE,
        "modulo_saudavel": AnomalyType.HEALTHY_MODULE,
    }

    def __init__(self, thermal_analyzer: Optional[ThermalAnalyzer] = None) -> None:
        self.analyzer = thermal_analyzer or ThermalAnalyzer()

    def parse_anomaly_type(self, raw_label: str | int) -> AnomalyType:
        """
        Converte o rótulo retornado pela inferência da IA para a enumeração AnomalyType do domínio.
        """
        key = str(raw_label).strip().lower()
        if key in self.CLASS_MAPPING:
            return self.CLASS_MAPPING[key]

        logger.warning(f"Rótulo de classe desconhecido '{raw_label}'. Classificando como Hotspot.")
        return AnomalyType.HOTSPOT

    def evaluate_thermal_diagnosis(
        self,
        anomaly_type: AnomalyType,
        bbox: BoundingBox,
        temperature_matrix: Optional[np.ndarray] = None,
        reference_temperature: Optional[float] = None,
    ) -> Tuple[SeverityLevel, Optional[DeltaT], float, Optional[float], Optional[float], str]:
        """
        Correlaciona a detecção espacial com a matriz de temperatura física para
        determinar a temperatura máxima de pico, o gradiente Delta T e a severidade IEC.
        
        :param anomaly_type: Tipo de falha identificado.
        :param bbox: Posição do defeito na imagem.
        :param temperature_matrix: Matriz radiométrica 2D de temperaturas (°C).
        :param reference_temperature: Temperatura de referência do painel/ambiente (°C).
        :return: Tupla (severity, delta_t, max_temp, min_temp, avg_temp, technical_notes).
        """
        if temperature_matrix is None or temperature_matrix.size == 0:
            # Sem matriz radiométrica física: severidade padrão conservadora
            default_sev = SeverityLevel.LOW if anomaly_type.is_fault else SeverityLevel.INFORMATIVE
            return default_sev, None, 45.0, 30.0, 38.0, "Medição térmica física indisponível (inferência óptica)."

        # Extração de métricas quantitativas dentro da Bounding Box do defeito
        try:
            metrics: ThermalMetrics = self.analyzer.analyze_region(
                matrix=temperature_matrix,
                bbox=bbox,
                ref_temp=reference_temperature,
            )
        except Exception as ex:
            logger.warning(f"Erro ao extrair região térmica da anomalia: {ex}")
            metrics = self.analyzer.analyze_matrix(temperature_matrix, ref_temp=reference_temperature)

        delta_t_obj = metrics.to_delta_t_object()
        severity = delta_t_obj.classify_iec_62446_3()

        # Elaboração do parecer técnico formatado para relatórios
        notes = self._build_technical_notes(anomaly_type, metrics)

        return (
            severity,
            delta_t_obj,
            metrics.max_temp,
            metrics.min_temp,
            metrics.avg_temp,
            notes,
        )

    def _build_technical_notes(self, anomaly_type: AnomalyType, metrics: ThermalMetrics) -> str:
        """Gera parecer técnico descritivo em conformidade com as normas do setor fotovoltaico."""
        delta_str = f"Delta T = {metrics.delta_t:.1f} °C (Ref: {metrics.ref_temp:.1f} °C)"
        peak_str = f"Pico: {metrics.max_temp:.1f} °C"

        if anomaly_type == AnomalyType.HOTSPOT:
            if metrics.severity == SeverityLevel.CRITICAL:
                return f"Hotspot Crítico IEC Classe 3. {delta_str}, {peak_str}. Risco imediato de delaminação ou queima de célula."
            elif metrics.severity == SeverityLevel.MEDIUM:
                return f"Hotspot Médio IEC Classe 2. {delta_str}, {peak_str}. Programar manutenção corretiva para mitigar perda de geração."
            else:
                return f"Hotspot Leve IEC Classe 1. {delta_str}, {peak_str}. Manter em observação na próxima inspeção termográfica."

        elif anomaly_type == AnomalyType.DISCONNECTED_MODULE:
            return f"Módulo Desconectado em circuito aberto. Aquecimento homogêneo de string: {delta_str}, {peak_str}."

        elif anomaly_type == AnomalyType.PID:
            return f"Padrão característico de Degradação Induzida por Potencial (PID). {delta_str}. Verificar aterramento dos inversores."

        elif anomaly_type == AnomalyType.SOILING:
            return f"Aquecimento localizado por acúmulo de sujidade / poeira superficial. {delta_str}. Recomenda-se lavagem técnica dos módulos."

        elif anomaly_type == AnomalyType.SHADING:
            return f"Sombreamento parcial identificado. {delta_str}. Verificar desbaste de vegetação ou obstáculos no entorno da usina."

        else:
            return f"Módulo operando sob parâmetros normais. {peak_str}."
