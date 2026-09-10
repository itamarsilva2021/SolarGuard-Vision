"""
Entidade de Domínio representando uma anomalia ou falha térmica detectada em painel fotovoltaico.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.delta_t import DeltaT
from src.domain.exceptions import DomainError


@dataclass
class ThermalAnomaly:
    """
    Representa uma anomalia térmica individual localizada em uma imagem ou módulo fotovoltaico.
    
    :param id: Identificador único universal (UUID).
    :param anomaly_type: Tipo da falha térmica (Hotspot, Módulo Desconectado, PID, etc.).
    :param severity: Nível de severidade normativo (IEC TS 62446-3).
    :param confidence: Grau de confiança da inferência YOLOv11 (0.0 a 1.0).
    :param bbox: Caixa delimitadora da anomalia na imagem.
    :param max_temp_celsius: Temperatura de pico medida no ponto anômalo (°C).
    :param delta_t: Objeto com o gradiente térmico em relação à referência saudável.
    :param min_temp_celsius: Temperatura mínima na região da anomalia (°C).
    :param avg_temp_celsius: Temperatura média na região da anomalia (°C).
    :param crop_path: Caminho do arquivo de recorte da anomalia em disco.
    :param notes: Observações técnicas do inspetor.
    :param created_at: Data e hora do registro da detecção.
    """
    anomaly_type: AnomalyType
    severity: SeverityLevel
    confidence: float
    bbox: BoundingBox
    max_temp_celsius: float
    delta_t: Optional[DeltaT] = None
    min_temp_celsius: Optional[float] = None
    avg_temp_celsius: Optional[float] = None
    crop_path: Optional[str] = None
    notes: Optional[str] = None
    image_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise DomainError(f"Confiança de detecção inválida: {self.confidence}. Deve estar em [0.0, 1.0].")

    def update_severity_from_delta_t(self) -> None:
        """Recalcula a severidade automaticamente com base nas regras IEC TS 62446-3."""
        if self.delta_t is not None:
            self.severity = self.delta_t.classify_iec_62446_3()

    @property
    def is_critical(self) -> bool:
        """Indica se a anomalia atingiu o nível crítico (Classe 3)."""
        return self.severity == SeverityLevel.CRITICAL
