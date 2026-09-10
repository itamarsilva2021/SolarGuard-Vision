"""
Entidade de Domínio representando um Cliente / Proprietário de Usinas Fotovoltaicas.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Client:
    """
    Representa o cliente corporativo ou pessoa física proprietária dos ativos solares inspecionados.
    
    :param id: Identificador único universal (UUID).
    :param name: Razão social ou nome completo do cliente.
    :param document: CNPJ ou CPF do cliente.
    :param email: E-mail de contato para envio de relatórios e alertas.
    :param phone: Telefone para contato comercial/técnico.
    :param address: Endereço ou sede da empresa.
    :param created_at: Data de cadastro no sistema.
    """
    name: str
    document: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
