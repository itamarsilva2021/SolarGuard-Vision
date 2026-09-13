"""
Diálogo Modal Obrigatório de Alteração de Senha (PySide6).
Exibido obrigatoriamente quando o usuário possui must_change_password=True.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.application.services.user_service import UserService
from src.domain.entities.user import User


CHANGE_PASSWORD_STYLE_SHEET = """
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
QLabel {
    color: #F8FAFC;
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
QPushButton#submitBtn {
    background-color: #00A896;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 10px;
    border-radius: 6px;
    border: none;
}
QPushButton#submitBtn:hover {
    background-color: #028090;
}
QPushButton#submitBtn:pressed {
    background-color: #026C7A;
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


class ForcePasswordChangeDialog(QDialog):
    """
    Diálogo modal de alteração obrigatória de senha.
    Exige a digitação da senha atual/temporária e a definição de uma nova senha forte (mínimo 12 caracteres).
    """

    def __init__(
        self,
        user: User,
        user_service: UserService,
        parent: Optional[QWidget] = None,
        preset_current_password: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.user = user
        self.user_service = user_service
        self.preset_current_password = preset_current_password

        self.setWindowTitle("SolarGuard Vision - Troca de Senha Obrigatória")
        self.setFixedSize(440, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(CHANGE_PASSWORD_STYLE_SHEET)

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 28, 28, 28)
        main_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Troca Obrigatória de Senha")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #F59E0B;")
        title.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            f"Olá, {self.user.full_name} ({self.user.username}).\n"
            "Por políticas de segurança no primeiro acesso ou reset, "
            "você deve cadastrar uma nova senha antes de prosseguir."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94A3B8; font-size: 11px; margin-top: 4px;")
        desc.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(6)

        # Campos
        old_pwd_lbl = QLabel("Senha Atual / Temporária:")
        old_pwd_lbl.setStyleSheet("color: #CBD5E1; font-weight: 500; font-size: 12px;")
        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.Password)
        self.old_password_input.setPlaceholderText("••••••••")
        if self.preset_current_password:
            self.old_password_input.setText(self.preset_current_password)

        new_pwd_lbl = QLabel("Nova Senha (Mínimo 12 caracteres):")
        new_pwd_lbl.setStyleSheet("color: #CBD5E1; font-weight: 500; font-size: 12px;")
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input.setPlaceholderText("••••••••••••")

        confirm_pwd_lbl = QLabel("Confirmar Nova Senha:")
        confirm_pwd_lbl.setStyleSheet("color: #CBD5E1; font-weight: 500; font-size: 12px;")
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setPlaceholderText("••••••••••••")
        self.confirm_password_input.returnPressed.connect(self._attempt_change_password)

        card_layout.addWidget(old_pwd_lbl)
        card_layout.addWidget(self.old_password_input)
        card_layout.addWidget(new_pwd_lbl)
        card_layout.addWidget(self.new_password_input)
        card_layout.addWidget(confirm_pwd_lbl)
        card_layout.addWidget(self.confirm_password_input)

        # Erro
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        card_layout.addWidget(self.error_label)

        # Botões
        self.submit_btn = QPushButton("Confirmar Nova Senha")
        self.submit_btn.setObjectName("submitBtn")
        self.submit_btn.setFixedHeight(40)
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.clicked.connect(self._attempt_change_password)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)

        card_layout.addWidget(self.submit_btn)
        card_layout.addWidget(self.cancel_btn)

        main_layout.addWidget(card)

    def _attempt_change_password(self) -> None:
        old_pwd = self.old_password_input.text()
        new_pwd = self.new_password_input.text()
        confirm_pwd = self.confirm_password_input.text()

        if not old_pwd or not new_pwd or not confirm_pwd:
            self._show_error("Todos os campos devem ser preenchidos.")
            return

        if len(new_pwd) < 12:
            self._show_error("A nova senha deve possuir pelo menos 12 caracteres.")
            return

        if new_pwd != confirm_pwd:
            self._show_error("A nova senha e a confirmação não coincidem.")
            return

        if new_pwd == old_pwd:
            self._show_error("A nova senha não pode ser idêntica à senha atual.")
            return

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Atualizando...")

        res = self.user_service.change_password(self.user.id, old_pwd, new_pwd)
        if res.is_success:
            self.user.must_change_password = False
            self.error_label.setVisible(False)
            self.accept()
        else:
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Confirmar Nova Senha")
            self._show_error(res.error)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(f"⚠️  {message}")
        self.error_label.setVisible(True)
