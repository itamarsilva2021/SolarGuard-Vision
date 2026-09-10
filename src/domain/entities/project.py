"""
Entidade Raiz de Agregado (Aggregate Root) representando uma Usina Fotovoltaica / Projeto.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.domain.entities.inspection import Inspection
from src.domain.value_objects.geo_coordinate import GeoCoordinate


@dataclass
class Project:
    """
    Representa uma usina solar fotovoltaica / projeto cadastrado no sistema.
    
    :param id: Identificador único universal.
    :param name: Nome da usina (ex: 'UFV Solar Esperança 5MW').
    :param client_name: Nome do cliente / proprietário do ativo.
    :param location_name: Cidade/Estado da usina.
    :param capacity_kwp: Potência de pico instalada em kWp.
    :param coordinate: Ponto geográfico central da usina (WGS84).
    :param module_manufacturer: Fabricante dos módulos solares (ex: 'Canadian Solar').
    :param module_model: Modelo dos módulos (ex: 'CS3W-450MS').
    :param inspections: Histórico de inspeções realizadas nesta usina.
    :param created_at: Data de cadastro da usina.
    """
    name: str
    client_name: str
    location_name: str
    capacity_kwp: float
    client_id: Optional[str] = None
    coordinate: Optional[GeoCoordinate] = None
    module_manufacturer: Optional[str] = None
    module_model: Optional[str] = None
    inspections: list[Inspection] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_inspection(self, inspection: Inspection) -> None:
        """Adiciona uma nova inspeção ao histórico da usina."""
        self.inspections.append(inspection)

    @property
    def total_inspections(self) -> int:
        """Quantidade de campanhas de inspeção registradas."""
        return len(self.inspections)

    @property
    def latest_inspection(self) -> Optional[Inspection]:
        """Retorna a inspeção mais recente realizada."""
        if not self.inspections:
            return None
        return max(self.inspections, key=lambda i: i.date)
