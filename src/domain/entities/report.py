"""
Entidade de Domínio representando um Relatório Técnico ou Executivo gerado pelo sistema.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid


class ReportType(str, Enum):
    """Tipos de relatórios suportados pelo SolarGuard Vision."""
    PDF_EXECUTIVE = "pdf_executive"      # Sumário para gestores e investidores
    PDF_TECHNICAL = "pdf_technical"      # Dossiê técnico aprofundado com imagens e IEC
    EXCEL_ANALYTICAL = "excel_analytical" # Planilha bruta com coordenadas GPS e medições

    @property
    def display_name(self) -> str:
        names = {
            ReportType.PDF_EXECUTIVE: "Relatório Executivo (PDF)",
            ReportType.PDF_TECHNICAL: "Relatório Técnico Completo (PDF)",
            ReportType.EXCEL_ANALYTICAL: "Planilha Analítica de Falhas (Excel)",
        }
        return names.get(self, self.value)


@dataclass
class Report:
    """
    Representa um arquivo de relatório gerado a partir de uma inspeção.
    
    :param id: Identificador único universal.
    :param inspection_id: Identificador da inspeção inspecionada.
    :param title: Título descritivo do relatório.
    :param report_type: Tipo de documento (PDF Executivo, PDF Técnico, Excel).
    :param file_path: Caminho completo onde o arquivo gerado foi salvo no disco.
    :param file_size_bytes: Tamanho do arquivo gerado em bytes.
    :param generated_by: Nome do usuário/técnico responsável pela geração.
    :param generated_at: Data e hora em que o relatório foi gerado.
    """
    inspection_id: str
    title: str
    report_type: ReportType
    file_path: str
    file_size_bytes: int = 0
    generated_by: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
