"""
Testes automatizados da MainWindow e Shell Desktop do SolarGuard Vision.
Valida inicialização, navegação pelas 6 abas, componentes e integração de dados.
"""

import os
import sys
import pytest
from pathlib import Path

# Configurar Qt para rodar em modo offscreen (headless) para testes automatizados
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.config.settings_manager import SettingsManager
from src.infrastructure.security.license_manager import LicenseManager
from src.presentation.main_window import (
    MainWindow,
    DashboardView,
    InspectionsView,
    ReportsView,
    SettingsView,
    LicenseView,
)
from src.presentation.dataset_audit_window import DatasetAuditWidget


@pytest.fixture(scope="session")
def qapp():
    """Garante que exista uma única instância do QApplication durante a sessão de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


@pytest.fixture
def memory_db(tmp_path):
    """Cria um banco de dados de teste isolado e inicializa as tabelas."""
    db_file = str(tmp_path / "test_gui_solarguard.db")
    db = DatabaseManager(db_path=db_file)
    db.initialize_schema()
    return db


def test_main_window_instantiation(qapp, memory_db):
    """Testa a criação da MainWindow e inicialização dos componentes básicos."""
    window = MainWindow(db_manager=memory_db)

    assert "SolarGuard Vision" in window.windowTitle()
    assert window.stacked is not None
    assert window.stacked.count() == 6
    assert len(window.nav_buttons) == 6
    assert window.statusBar() is not None

    # Verificar que as 6 abas são as classes esperadas
    assert isinstance(window.stacked.widget(0), DashboardView)
    assert isinstance(window.stacked.widget(1), InspectionsView)
    assert isinstance(window.stacked.widget(2), ReportsView)
    assert isinstance(window.stacked.widget(3), DatasetAuditWidget)
    assert isinstance(window.stacked.widget(4), SettingsView)
    assert isinstance(window.stacked.widget(5), LicenseView)

    window.close()


def test_main_window_navigation(qapp, memory_db):
    """Testa a troca de abas da barra lateral (Sidebar) e atualização visual."""
    window = MainWindow(db_manager=memory_db)

    # Inicialmente na primeira aba (Dashboard)
    assert window.stacked.currentIndex() == 0

    # Navegar por cada uma das abas
    for i in range(6):
        window.switch_page(i)
        assert window.stacked.currentIndex() == i
        # O botão ativo deve ter a propriedade 'active' como 'true'
        assert window.nav_buttons[i].property("active") == "true"
        # Os demais botões devem ser 'false'
        for j in range(6):
            if j != i:
                assert window.nav_buttons[j].property("active") == "false"

    window.close()


def test_dashboard_view_refresh(qapp, memory_db):
    """Testa a atualização de métricas da DashboardView."""
    view = DashboardView(memory_db)
    # Não deve levantar exceções mesmo com repositório vazio
    view.refresh_metrics()
    assert view.stat_boxes is not None
    assert len(view.stat_boxes) == 4


def test_settings_view_load_and_save(qapp, tmp_path, monkeypatch):
    """Testa carregamento e persistência de parâmetros na SettingsView."""
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    cfg_file = tmp_path / "test_settings.json"
    mgr = SettingsManager(config_file=cfg_file)
    view = SettingsView(mgr)

    assert "Português" in view.lang_combo.currentText() or "English" in view.lang_combo.currentText()
    assert "Dark" in view.theme_combo.currentText() or "Light" in view.theme_combo.currentText()

    # Simular alteração e salvamento
    view.combo_lang.setCurrentIndex(1)  # English
    view.combo_theme.setCurrentIndex(0) # Dark
    view.save_settings()

    updated = mgr.get_settings()
    assert updated.language == "en"
    assert updated.theme == "dark"


def test_license_view_display(qapp):
    """Testa exibição dos dados de licença e HWID na LicenseView."""
    lic_mgr = LicenseManager()
    view = LicenseView(lic_mgr)

    hwid = lic_mgr.get_current_machine_fingerprint()
    assert hwid in view.hwid_display.text()
    assert len(view.status_label.text()) > 0
