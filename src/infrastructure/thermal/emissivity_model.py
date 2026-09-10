"""
Modelo Científico de Emissividade para Inspeção Termográfica Fotovoltaica.
Calcula emissividade em função do tipo de material, estado de sujidade superficial e ângulo de visada (incidência).
Em conformidade com as normas IEC TS 62446-3 e ISO 18434-1.
"""

from enum import Enum
from typing import Optional, Dict
import math


class MaterialType(str, Enum):
    """Tipos de materiais constituintes e estados superficiais em sistemas fotovoltaicos."""
    PV_GLASS_CLEAN = "pv_glass_clean"              # Vidro temperado solar limpo (padrão de fábrica)
    PV_GLASS_SOILED = "pv_glass_soiled"            # Vidro com acúmulo de poeira/sujidade superficial
    SILICON_CELL = "silicon_cell"                  # Célula fotovoltaica de silício (revestimento antirreflexo ARC)
    ALUMINUM_FRAME_ANODIZED = "aluminum_frame"    # Moldura de alumínio anodizado da placa
    EVA_BACKSHEET = "eva_backsheet"                # Polímero de encapsulamento / face posterior (EVA/Tedlar)
    CUSTOM = "custom"                              # Material customizado com emissividade definida pelo operador


# Tabela de referência de emissividades hemisféricas normais (theta = 0) na banda LWIR (8 - 14 um)
DEFAULT_EMISSIVITIES: Dict[MaterialType, float] = {
    MaterialType.PV_GLASS_CLEAN: 0.93,
    MaterialType.PV_GLASS_SOILED: 0.90,
    MaterialType.SILICON_CELL: 0.91,
    MaterialType.ALUMINUM_FRAME_ANODIZED: 0.82,
    MaterialType.EVA_BACKSHEET: 0.92,
}


class EmissivityModel:
    """
    Motor de modelagem e correção angular de emissividade para termografia aérea.
    
    A emissividade de superfícies dielétricas como o vidro fotovoltaico é praticamente
    constante para ângulos de incidência de 0° a 45°, decaindo de forma acentuada para
    ângulos superiores a 60° (efeito Fresnel térmico e aumento da refletância).
    """

    @staticmethod
    def get_base_emissivity(material: MaterialType, custom_value: Optional[float] = None) -> float:
        """
        Retorna a emissividade normal (perpendicular) para o material selecionado.
        
        :param material: Tipo de material fotovoltaico.
        :param custom_value: Valor customizado (obrigatório se material for CUSTOM).
        :return: Coeficiente de emissividade normal no intervalo (0.0, 1.0].
        """
        if material == MaterialType.CUSTOM:
            if custom_value is None or not (0.01 <= custom_value <= 1.0):
                raise ValueError("Para material CUSTOM, é necessário fornecer custom_value entre 0.01 e 1.0.")
            return float(custom_value)

        return DEFAULT_EMISSIVITIES[material]

    @classmethod
    def calculate_angular_emissivity(
        cls,
        base_emissivity: float,
        angle_degrees: float,
    ) -> float:
        """
        Aplica a correção angular de emissividade em função do ângulo de visada (nadir = 0°).
        
        Utiliza a curva empírica para vidro dielétrico solar (IEC TS 62446-3):
        Para theta <= 45°: variação insignificante (< 1%).
        Para theta > 45°: atenuação progressiva conforme a relação de Fresnel no infravermelho termal.
        
        :param base_emissivity: Emissividade na direção normal (0°).
        :param angle_degrees: Ângulo entre a normal da superfície e o eixo óptico da câmera (em graus).
        :return: Emissividade efetiva aparente ajustada.
        """
        if not (0.01 <= base_emissivity <= 1.0):
            raise ValueError(f"Emissividade base deve estar no intervalo (0.0, 1.0]. Recebido: {base_emissivity}")

        theta = abs(float(angle_degrees))
        if theta > 89.0:
            theta = 89.0  # Limite assintótico para evitar singularidade em rasante (90°)

        if theta <= 45.0:
            # Comportamento quase-lambertiano do vidro fotovoltaico
            effective = base_emissivity * (1.0 - 0.015 * (theta / 45.0) ** 2)
        else:
            # Queda acentuada pós-45° típica de dielétricos no espectro LWIR
            excess_angle = (theta - 45.0) / 45.0  # Varia de 0 a 1 entre 45° e 90°
            factor = 0.985 - 0.35 * (excess_angle ** 2.2)
            effective = base_emissivity * factor

        # Garante limites físicos
        return round(float(max(0.05, min(1.0, effective))), 4)

    @classmethod
    def evaluate(
        cls,
        material: MaterialType = MaterialType.PV_GLASS_CLEAN,
        view_angle_degrees: float = 0.0,
        custom_emissivity: Optional[float] = None,
    ) -> float:
        """
        Avalia a emissividade final combinando material e geometria de observação.
        
        :param material: Material da superfície inspecionada.
        :param view_angle_degrees: Ângulo de observação em graus em relação à normal.
        :param custom_emissivity: Valor customizado opcional.
        :return: Emissividade corrigida.
        """
        base_eps = cls.get_base_emissivity(material, custom_emissivity)
        return cls.calculate_angular_emissivity(base_eps, view_angle_degrees)
