"""
Diálogo Modal de Ativação e Desbloqueio de Licença Ed25519 (PySide6).
Exibido obrigatoriamente quando o SolarGuard Vision não possui licença válida ou quando esta expira.
"""

from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
    QWidget,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.infrastructure.security.license_manager import LicenseManager


ACTIVATION_STYLE_SHEET = """
QDialog {
    background-color: #0B132B;
    color: #F8FAFC;
    font-family: 'Segoe UI', sans-serif;
}
QFrame#card {
    background-color: #111D3B;
    border: 1px solid #1C2541;
    border-radius: 12px;
}
QLineEdit {
    background-color: #1C2541;
    border: 1px solid #3A506B;
    border-radius: 6px;
    padding: 10px 14px;
    color: #F8FAFC;
    font-size: 13px;
}
QLineEdit:focus {
    border: 1px solid #00A896;
}
QPushButton#activateBtn {
    background-color: #00A896;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 10px;
    border-radius: 6px;
    border: none;
}
QPushButton#activateBtn:hover {
    background-color: #028090;
}
QPushButton#cancelBtn {
    background-color: transparent;
    color: #94A3B8;
    font-size: 12px;
    padding: 8px;
    border-radius: 6px;
    border: 1px solid #24344D;
}
QPushButton#cancelBtn:hover {
    background-color: #1C2541;
    color: #F8FAFC;
}
"""


class LicenseActivationDialog(QDialog):
    """
    Diálogo modal de ativação de licença obrigatório para desbloqueio da aplicação.
    """

    def __init__(self, lic_mgr: Optional[LicenseManager] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.lic_mgr = lic_mgr or LicenseManager()
        self.setWindowTitle("SolarGuard Vision - Ativação de Licença Obrigatória")
        self.setFixedSize(520, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(ACTIVATION_STYLE_SHEET)

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 28, 28, 28)
        main_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(24, 24, 24, 24)
        card_l.setSpacing(12)

        # Cabeçalho
        title = QLabel("Bloqueio de Uso - Ativação Necessária")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #EF4444;")
        title.setAlignment(Qt.AlignCenter)

        sub = QLabel(
            "Esta instalação do SolarGuard Vision requer uma licença válida assinada digitalmente "
            "com criptografia Ed25519 pela autoridade emissora."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        sub.setAlignment(Qt.AlignCenter)

        card_l.addWidget(title)
        card_l.addWidget(sub)
        card_l.addSpacing(6)

        # HWID Card
        hwid_lbl = QLabel("Hardware Fingerprint (HWID) desta máquina:")
        hwid_lbl.setStyleSheet("color: #CBD5E1; font-weight: bold; font-size: 12px;")
        card_l.addWidget(hwid_lbl)

        hwid_box = QHBoxLayout()
        self.hwid_input = QLineEdit(self.lic_mgr.get_current_machine_fingerprint())
        self.hwid_input.setReadOnly(True)
        self.hwid_input.setStyleSheet("font-family: Consolas, monospace; font-size: 13px; color: #38BDF8;")
        
        copy_btn = QPushButton("Copiar HWID")
        copy_btn.setFixedWidth(100)
        copy_btn.setStyleSheet("background-color: #3A506B; color: white; padding: 8px; border-radius: 6px; font-weight: bold;")
        copy_btn.clicked.connect(self._copy_hwid)
        hwid_box.addWidget(self.hwid_input)
        hwid_box.addWidget(copy_btn)
        card_l.addLayout(hwid_box)

        card_l.addSpacing(4)

        # Campo Chave de Ativação
        key_lbl = QLabel("Chave de Licença (.key ou token Ed25519):")
        key_lbl.setStyleSheet("color: #CBD5E1; font-weight: bold; font-size: 12px;")
        card_l.addWidget(key_lbl)

        key_box = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Cole o token <payload>.<assinatura>...")
        browse_btn = QPushButton("Arquivo...")
        browse_btn.setFixedWidth(80)
        browse_btn.setStyleSheet("background-color: #3A506B; color: white; padding: 8px; border-radius: 6px;")
        browse_btn.clicked.connect(self._browse_file)
        key_box.addWidget(self.key_input)
        key_box.addWidget(browse_btn)
        card_l.addLayout(key_box)

        # Label de Status/Erro
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")
        self.status_lbl.setVisible(False)
        card_l.addWidget(self.status_lbl)

        card_l.addSpacing(6)

        # Botões
        self.activate_btn = QPushButton("Ativar & Desbloquear Sistema")
        self.activate_btn.setObjectName("activateBtn")
        self.activate_btn.setFixedHeight(40)
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.clicked.connect(self._attempt_activation)

        self.exit_btn = QPushButton("Sair do Sistema")
        self.exit_btn.setObjectName("cancelBtn")
        self.exit_btn.setFixedHeight(34)
        self.exit_btn.setCursor(Qt.PointingHandCursor)
        self.exit_btn.clicked.connect(self.reject)

        card_l.addWidget(self.activate_btn)
        card_l.addWidget(self.exit_btn)

        main_layout.addWidget(card)

    def _copy_hwid(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self.hwid_input.text())
        QMessageBox.information(self, "Copiado", "HWID copiado para a área de transferência.")

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Chave de Licença", "", "Licenças (*.key *.lic *.txt)")
        if path:
            text = Path(path).read_text(encoding="utf-8").strip()
            self.key_input.setText(text)

    def _attempt_activation(self) -> None:
        key = self.key_input.text().strip()
        if not key:
            self._show_error("Insira a chave criptográfica de ativação.")
            return

        info = self.lic_mgr.save_license(key)
        if info.is_valid:
            QMessageBox.information(
                self,
                "Licença Ativada",
                f"Licença verificada com sucesso via Ed25519!\n\n"
                f"Cliente: {info.client_name}\n"
                f"Tipo: {info.license_type.display_name}\n"
                f"Status: {info.status_message}",
            )
            self.accept()
        else:
            self._show_error(info.status_message)

    def _show_error(self, msg: str) -> None:
        self.status_lbl.setText(f"❌ {msg}")
        self.status_lbl.setVisible(True)
