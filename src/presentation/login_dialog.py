"""
Tela de Autenticação e Login de Operadores do SolarGuard Vision (PySide6).
Interface moderna Dark Tech com validação segura de credenciais via SessionManager.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from src.application.services.session_service import SessionManager


LOGIN_STYLE_SHEET = """
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
QPushButton#loginBtn {
    background-color: #00A896;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 10px;
    border-radius: 6px;
    border: none;
}
QPushButton#loginBtn:hover {
    background-color: #028090;
}
QPushButton#loginBtn:pressed {
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


class LoginDialog(QDialog):
    """
    Diálogo modal de autenticação de operadores e administradores.
    Bloqueia o acesso à aplicação até a confirmação de credenciais válidas.
    """

    def __init__(self, session_manager: SessionManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session_manager = session_manager
        self.setWindowTitle("SolarGuard Vision - Autenticação de Operador")
        self.setFixedSize(420, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(LOGIN_STYLE_SHEET)

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 28, 28, 28)
        main_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        # Brand / Cabeçalho
        brand_title = QLabel("SolarGuard Vision")
        brand_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        brand_title.setStyleSheet("color: #00A896;")
        brand_title.setAlignment(Qt.AlignCenter)

        brand_subtitle = QLabel("Painel de Diagnóstico & Termografia IA")
        brand_subtitle.setFont(QFont("Segoe UI", 9, QFont.Bold))
        brand_subtitle.setStyleSheet("color: #64748B;")
        brand_subtitle.setAlignment(Qt.AlignCenter)

        info_lbl = QLabel("Insira suas credenciais corporativas para acessar o sistema:")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; margin-top: 4px;")
        info_lbl.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(brand_title)
        card_layout.addWidget(brand_subtitle)
        card_layout.addWidget(info_lbl)
        card_layout.addSpacing(6)

        # Formulário de Entrada
        user_lbl = QLabel("Usuário / Login:")
        user_lbl.setStyleSheet("color: #CBD5E1; font-weight: 500; font-size: 12px;")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Ex: admin ou operador")
        self.username_input.returnPressed.connect(self._focus_password_or_login)

        pwd_lbl = QLabel("Senha de Acesso:")
        pwd_lbl.setStyleSheet("color: #CBD5E1; font-weight: 500; font-size: 12px;")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.returnPressed.connect(self._attempt_login)

        card_layout.addWidget(user_lbl)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(pwd_lbl)
        card_layout.addWidget(self.password_input)

        # Mensagem de Erro
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        card_layout.addWidget(self.error_label)

        card_layout.addSpacing(6)

        # Botões de Ação
        self.login_btn = QPushButton("Acessar Sistema")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setFixedHeight(40)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._attempt_login)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)

        card_layout.addWidget(self.login_btn)
        card_layout.addWidget(self.cancel_btn)

        main_layout.addWidget(card)

    def _focus_password_or_login(self) -> None:
        if not self.password_input.text():
            self.password_input.setFocus()
        else:
            self._attempt_login()

    def _attempt_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error("Por favor, preencha o usuário e a senha.")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Autenticando...")

        res = self.session_manager.login(username, password)
        if res.is_success:
            user = res.value
            if user.must_change_password:
                # Força a exibição do diálogo de troca de senha
                from src.presentation.force_password_change_dialog import ForcePasswordChangeDialog
                change_dlg = ForcePasswordChangeDialog(
                    user=user,
                    user_service=self.session_manager.user_service,
                    parent=self,
                    preset_current_password=password,
                )
                if change_dlg.exec() != QDialog.Accepted:
                    # Se o usuário cancelou a troca obrigatória de senha, desloga e rejeita
                    self.session_manager.logout()
                    self.login_btn.setEnabled(True)
                    self.login_btn.setText("Acessar Sistema")
                    self._show_error("A troca de senha é obrigatória para prosseguir.")
                    return

            self.error_label.setVisible(False)
            self.accept()
        else:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Acessar Sistema")
            self._show_error(res.error)
            self.password_input.clear()
            self.password_input.setFocus()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(f"⚠️  {message}")
        self.error_label.setVisible(True)
