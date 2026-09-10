"""
Contratos e Interfaces abstratas para a Camada de Repositórios (Repository Pattern).
Princípio da Inversão de Dependência (DIP - SOLID).
"""

from abc import ABC, abstractmethod
from typing import Optional
from src.domain.entities.client import Client
from src.domain.entities.project import Project
from src.domain.entities.inspection import Inspection
from src.domain.entities.thermal_image import ThermalImage
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.entities.report import Report
from src.domain.entities.user import User



class IClientRepository(ABC):
    """Interface abstrata de persistência para Clientes."""

    @abstractmethod
    def save(self, client: Client) -> Client:
        """Cria ou atualiza um cliente no banco de dados."""
        pass

    @abstractmethod
    def get_by_id(self, client_id: str) -> Optional[Client]:
        """Recupera um cliente pelo seu identificador único."""
        pass

    @abstractmethod
    def list_all(self) -> list[Client]:
        """Lista todos os clientes cadastrados no sistema."""
        pass

    @abstractmethod
    def delete(self, client_id: str) -> bool:
        """Remove um cliente pelo ID. Retorna True se removido com sucesso."""
        pass


class IProjectRepository(ABC):
    """Interface abstrata de persistência para Usinas / Projetos."""

    @abstractmethod
    def save(self, project: Project) -> Project:
        """Cria ou atualiza uma usina no banco de dados."""
        pass

    @abstractmethod
    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Recupera uma usina pelo seu identificador único."""
        pass

    @abstractmethod
    def list_all(self) -> list[Project]:
        """Lista todas as usinas cadastradas no sistema."""
        pass

    @abstractmethod
    def list_by_client(self, client_id: str) -> list[Project]:
        """Lista todas as usinas pertencentes a um determinado cliente."""
        pass

    @abstractmethod
    def delete(self, project_id: str) -> bool:
        """Remove uma usina pelo ID. Retorna True se removida com sucesso."""
        pass


class IInspectionRepository(ABC):
    """Interface abstrata de persistência para Missões de Inspeção."""

    @abstractmethod
    def save(self, inspection: Inspection) -> Inspection:
        """Cria ou atualiza uma inspeção."""
        pass

    @abstractmethod
    def get_by_id(self, inspection_id: str) -> Optional[Inspection]:
        """Recupera uma inspeção pelo ID com suas imagens e anomalias agregadas."""
        pass

    @abstractmethod
    def list_all(self) -> list[Inspection]:
        """Lista todas as inspeções cadastradas."""
        pass

    @abstractmethod
    def list_by_project(self, project_id: str) -> list[Inspection]:
        """Lista todas as inspeções realizadas em um determinado projeto."""
        pass

    @abstractmethod
    def delete(self, inspection_id: str) -> bool:
        """Remove uma inspeção pelo ID."""
        pass


class IThermalImageRepository(ABC):
    """Interface abstrata de persistência para Imagens Térmicas."""

    @abstractmethod
    def save(self, image: ThermalImage) -> ThermalImage:
        """Salva ou atualiza uma imagem térmica."""
        pass

    @abstractmethod
    def get_by_id(self, image_id: str) -> Optional[ThermalImage]:
        """Busca uma imagem pelo ID."""
        pass

    @abstractmethod
    def list_by_inspection(self, inspection_id: str) -> list[ThermalImage]:
        """Retorna todas as imagens térmicas de uma inspeção."""
        pass

    @abstractmethod
    def delete(self, image_id: str) -> bool:
        """Remove uma imagem térmica pelo ID."""
        pass


class IThermalAnomalyRepository(ABC):
    """Interface abstrata de persistência para Falhas / Anomalias Térmicas."""

    @abstractmethod
    def save(self, anomaly: ThermalAnomaly, image_id: str) -> ThermalAnomaly:
        """Salva ou atualiza uma anomalia associada a uma imagem térmica."""
        pass

    @abstractmethod
    def get_by_id(self, anomaly_id: str) -> Optional[ThermalAnomaly]:
        """Busca uma falha pelo ID."""
        pass

    @abstractmethod
    def list_by_image(self, image_id: str) -> list[ThermalAnomaly]:
        """Lista todas as falhas detectadas em uma imagem específica."""
        pass

    @abstractmethod
    def list_by_inspection(self, inspection_id: str) -> list[ThermalAnomaly]:
        """Lista todas as falhas encontradas em uma inspeção completa."""
        pass

    @abstractmethod
    def delete(self, anomaly_id: str) -> bool:
        """Remove uma anomalia pelo ID."""
        pass


class IReportRepository(ABC):
    """Interface abstrata de persistência para Relatórios Gerados."""

    @abstractmethod
    def save(self, report: Report) -> Report:
        """Salva ou atualiza os metadados de um relatório gerado."""
        pass

    @abstractmethod
    def get_by_id(self, report_id: str) -> Optional[Report]:
        """Busca um relatório pelo ID."""
        pass

    @abstractmethod
    def list_by_inspection(self, inspection_id: str) -> list[Report]:
        """Lista todos os relatórios emitidos para uma inspeção."""
        pass

    @abstractmethod
    def list_all(self) -> list[Report]:
        """Lista todos os relatórios gerados no sistema."""
        pass

    @abstractmethod
    def delete(self, report_id: str) -> bool:
        """Remove o registro de um relatório."""
        pass


class IUserRepository(ABC):
    """Interface abstrata de persistência para Usuários e Autenticação."""

    @abstractmethod
    def save(self, user: User) -> User:
        """Cria ou atualiza um usuário."""
        pass

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Busca usuário pelo ID."""
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """Busca usuário pelo login único."""
        pass

    @abstractmethod
    def list_all(self) -> list[User]:
        """Lista todos os usuários cadastrados."""
        pass

    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """Remove um usuário do sistema."""
        pass

