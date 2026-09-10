"""
Contratos abstratos para motores de exportação de relatórios técnicos e analíticos.
"""

from abc import ABC, abstractmethod
from src.domain.entities.inspection import Inspection
from src.domain.entities.project import Project


class IPDFReportExporter(ABC):
    """Interface para o gerador de relatórios técnicos em formato PDF (ReportLab)."""

    @abstractmethod
    def export_inspection_report(
        self,
        project: Project,
        inspection: Inspection,
        output_path: str,
    ) -> str:
        """
        Gera relatório técnico executivo completo em PDF com sumário, severidades,
        gráficos e detalhamento fotográfico das anomalias térmicas.
        
        :return: Caminho do arquivo PDF gerado.
        """
        pass


class IExcelExporter(ABC):
    """Interface para exportação tabular analítica em formato Excel (.xlsx)."""

    @abstractmethod
    def export_anomalies_spreadsheet(
        self,
        project: Project,
        inspection: Inspection,
        output_path: str,
    ) -> str:
        """
        Gera planilha detalhada com tabela de falhas, coordenadas GPS, Delta T e severidades.
        
        :return: Caminho do arquivo XLSX gerado.
        """
        pass
