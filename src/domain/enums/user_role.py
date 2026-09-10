"""
Enumeração de papéis de usuários (Role-Based Access Control - RBAC) no SolarGuard Vision.
"""

from enum import Enum


class UserRole(str, Enum):
    """Papéis de controle de acesso no sistema."""
    ADMIN = "admin"           # Acesso irrestrito (configurações, licença, backups, usuários)
    INSPECTOR = "inspector"   # Operação técnica (importação, inspeções, IA, relatórios, mapas)
    VIEWER = "viewer"         # Somente leitura (dashboard, histórico de relatórios)

    @property
    def display_name(self) -> str:
        names = {
            UserRole.ADMIN: "Administrador do Sistema",
            UserRole.INSPECTOR: "Engenheiro Inspetor",
            UserRole.VIEWER: "Visualizador / Cliente",
        }
        return names.get(self, self.value)
