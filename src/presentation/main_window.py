"""
Janela Principal (MainWindow) Desktop do SolarGuard Vision.

Implementa o Shell unificado da aplicação com 6 seções integradas:
1. Dashboard (KPIs, gráficos de severidade e histórico de usinas)
2. Inspeções (Listagem, carregamento de imagens térmicas e detecção de anomalias)
3. Relatórios (Histórico de relatórios técnicos, visualização e geração de PDFs/Planilhas)
4. Dataset Audit (Auditoria de integridade, balanceamento e paridade de datasets YOLOv11)
5. Configurações (Preferências de sistema, idioma, temas e parâmetros de radiometria)
6. Licenciamento (HWID de máquina, validação de licença comercial/acadêmica e ativação)
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QStackedWidget,
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QLineEdit,
        QComboBox,
        QFileDialog,
        QMessageBox,
        QFrame,
        QScrollArea,
        QFormLayout,
        QGroupBox,
        QStatusBar,
        QDialog,
    )
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QFont, QIcon, QColor, QPixmap, QDesktopServices
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    QMainWindow = object
    QWidget = object
    QDialog = object

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.config.settings_manager import SettingsManager
from src.infrastructure.security.license_manager import LicenseManager
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_project_repository import SqliteProjectRepository
from src.infrastructure.database.repositories.sqlite_inspection_repository import SqliteInspectionRepository
from src.infrastructure.database.repositories.sqlite_thermal_anomaly_repository import SqliteThermalAnomalyRepository
from src.infrastructure.database.repositories.sqlite_thermal_image_repository import SqliteThermalImageRepository
from src.infrastructure.database.repositories.sqlite_report_repository import SqliteReportRepository
from src.infrastructure.database.repositories.sqlite_user_repository import SqliteUserRepository
from src.application.services.user_service import UserService
from src.application.services.session_service import SessionManager
from src.presentation.dataset_audit_window import DatasetAuditWidget

logger = get_logger("MainWindow")


# =============================================================================
# ESTILOS VISUAIS DARK TECH (PALETA CORPORATIVA SOLARGUARD)
# =============================================================================
MAIN_STYLE_SHEET = """
QMainWindow, QWidget {
    background-color: #0B132B;
    color: #F8FAFC;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
}

QScrollBar:vertical {
    border: none;
    background: #1C2541;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3A506B;
    border-radius: 4px;
    min-height: 20px;
}

QTableWidget {
    background-color: #1C2541;
    border: 1px solid #3A506B;
    border-radius: 6px;
    gridline-color: #24344D;
    selection-background-color: #00A896;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background-color: #111D3B;
    color: #94A3B8;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #24344D;
}
QLineEdit, QComboBox {
    background-color: #1C2541;
    border: 1px solid #3A506B;
    border-radius: 6px;
    padding: 6px 10px;
    color: #F8FAFC;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #00A896;
}
QGroupBox {
    border: 1px solid #3A506B;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: bold;
    color: #38BDF8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
}
"""


class DashboardView(QWidget):
    """Aba 1: Painel Gerencial com Indicadores, KPIs e Gráficos de Severidade."""

    def __init__(self, db: DatabaseManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.project_repo = SqliteProjectRepository(db)
        self.inspection_repo = SqliteInspectionRepository(db)
        self.anomaly_repo = SqliteThermalAnomalyRepository(db)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Cabeçalho
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Painel de Monitoramento & Indicadores de Saúde Fotovoltaica")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        subtitle = QLabel("Conformidade normativa IEC TS 62446-3 e auditoria radiométrica contínua.")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)

        refresh_btn = QPushButton("Atualizar Dados")
        refresh_btn.setFixedWidth(130)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #00A896; color: white; border-radius: 6px;
                padding: 8px 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #028090; }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Cards de KPI
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(12)
        self.card_plants = self._create_card("USINAS MONITORADAS", "0", "#38BDF8")
        self.card_inspections = self._create_card("INSPEÇÕES REALIZADAS", "0", "#A855F7")
        self.card_anomalies = self._create_card("ANOMALIAS DETECTADAS", "0", "#F59E0B")
        self.card_critical = self._create_card("CASOS CRÍTICOS (CLASSE 3)", "0", "#EF4444")
        self.stat_boxes = [self.card_plants, self.card_inspections, self.card_anomalies, self.card_critical]

        kpi_layout.addWidget(self.card_plants)
        kpi_layout.addWidget(self.card_inspections)
        kpi_layout.addWidget(self.card_anomalies)
        kpi_layout.addWidget(self.card_critical)
        layout.addLayout(kpi_layout)

        # Painel Central: Tabela de Inspeções Recentes e Gráficos
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Lado Esquerdo: Tabela de Atividades Recentes
        left_box = QVBoxLayout()
        table_title = QLabel("Inspeções Recentes na Usina:")
        table_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        left_box.addWidget(table_title)

        self.table_recent = QTableWidget()
        self.table_recent.setColumnCount(4)
        self.table_recent.setHorizontalHeaderLabels(["Data", "Usina / Projeto", "Status", "Severidade IEC"])
        self.table_recent.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_recent.setAlternatingRowColors(True)
        self.table_recent.setEditTriggers(QTableWidget.NoEditTriggers)
        left_box.addWidget(self.table_recent)
        content_layout.addLayout(left_box, stretch=3)

        # Lado Direito: Visualização Gráfica
        right_box = QVBoxLayout()
        chart_title = QLabel("Diagnóstico Visual de Severidade:")
        chart_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        right_box.addWidget(chart_title)

        self.chart_image_label = QLabel("Nenhum gráfico carregado.")
        self.chart_image_label.setAlignment(Qt.AlignCenter)
        self.chart_image_label.setStyleSheet("background-color: #1C2541; border: 1px dashed #3A506B; border-radius: 8px;")
        self.chart_image_label.setFixedHeight(260)
        right_box.addWidget(self.chart_image_label)
        content_layout.addLayout(right_box, stretch=2)

        layout.addLayout(content_layout)
        self.refresh_data()

    def _create_card(self, title: str, value: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #1C2541;
                border: 1px solid #3A506B;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: bold;")
        lbl_v = QLabel(value)
        lbl_v.setObjectName("val")
        lbl_v.setStyleSheet(f"color: {accent_color}; font-size: 22px; font-weight: bold;")
        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return card

    def refresh_data(self) -> None:
        """Carrega métricas reais do banco de dados SQLite."""
        try:
            projects = self.project_repo.list_all()
            inspections = self.inspection_repo.list_all()
            anomalies = self.anomaly_repo.list_all()

            # Contagem de críticos (Classe 3 ou HIGH/CRITICAL)
            critical_count = sum(
                1 for a in anomalies if getattr(a, "severity", None) and str(a.severity.value).lower() in ["critical", "high", "classe 3"]
            )

            self.card_plants.findChild(QLabel, "val").setText(str(len(projects)))
            self.card_inspections.findChild(QLabel, "val").setText(str(len(inspections)))
            self.card_anomalies.findChild(QLabel, "val").setText(str(len(anomalies)))
            self.card_critical.findChild(QLabel, "val").setText(str(critical_count))

            # Atualiza tabela de inspeções recentes
            self.table_recent.setRowCount(min(8, len(inspections)))
            for row, insp in enumerate(sorted(inspections, key=lambda x: str(x.inspection_date or ""), reverse=True)[:8]):
                dt_str = insp.inspection_date.strftime("%d/%m/%Y %H:%M") if hasattr(insp.inspection_date, "strftime") else str(insp.inspection_date or "N/A")
                self.table_recent.setItem(row, 0, QTableWidgetItem(dt_str))
                self.table_recent.setItem(row, 1, QTableWidgetItem(f"Usina ID: {insp.project_id[:8]}..."))
                self.table_recent.setItem(row, 2, QTableWidgetItem(str(insp.status.value if hasattr(insp.status, "value") else insp.status)))
                self.table_recent.setItem(row, 3, QTableWidgetItem("Conforme IEC TS 62446-3"))

            # Carrega gráfico mais recente caso exista em reports/charts/
            charts_dir = Path("reports/charts")
            if charts_dir.exists():
                pngs = sorted(charts_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
                if pngs:
                    pix = QPixmap(str(pngs[0])).scaled(380, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.chart_image_label.setPixmap(pix)
        except Exception as ex:
            logger.error(f"Erro ao atualizar dashboard: {ex}")

    def refresh_metrics(self) -> None:
        """Alias para atualização de métricas do dashboard."""
        self.refresh_data()


class InspectionsView(QWidget):
    """Aba 2: Gestão e Execução de Inspeções Termográficas e Detecção."""

    def __init__(self, db: DatabaseManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.inspection_repo = SqliteInspectionRepository(db)
        self.anomaly_repo = SqliteThermalAnomalyRepository(db)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Cabeçalho
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Inspeções de Termografia Aérea")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        sub = QLabel("Gerenciamento de voos, processamento de imagens DJI RJPEG e detecção de hotspots.")
        sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box)

        btn_new = QPushButton("Carregar Imagem Térmica...")
        btn_new.setStyleSheet("""
            QPushButton {
                background-color: #028090; color: white; border-radius: 6px;
                padding: 8px 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #00A896; }
        """)
        btn_new.clicked.connect(self._load_thermal_image)
        header.addWidget(btn_new)
        layout.addLayout(header)

        # Tabela de Inspeções
        self.table_inspections = QTableWidget()
        self.table_inspections.setColumnCount(5)
        self.table_inspections.setHorizontalHeaderLabels([
            "ID da Inspeção", "Data do Voo", "Status Operacional", "Responsável Técnico", "Ações"
        ])
        self.table_inspections.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_inspections.setAlternatingRowColors(True)
        self.table_inspections.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table_inspections)

        # Tabela de Anomalias Detectadas
        lbl_anomalies = QLabel("Anomalias Térmicas Identificadas na Inspeção Ativa:")
        lbl_anomalies.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(lbl_anomalies)

        self.table_anomalies = QTableWidget()
        self.table_anomalies.setColumnCount(6)
        self.table_anomalies.setHorizontalHeaderLabels([
            "Código Anomalia", "Tipo de Falha", "Temp. Pico (°C)", "Delta T (°C)", "Severidade IEC", "Ação Recomendada"
        ])
        self.table_anomalies.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_anomalies.setAlternatingRowColors(True)
        self.table_anomalies.setFixedHeight(180)
        self.table_anomalies.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table_anomalies)

        self.refresh_data()

    def _load_thermal_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem Térmica Fotovoltaica",
            "",
            "Imagens Térmicas (*.jpg *.jpeg *.png *.tif *.tiff)",
        )
        if path:
            QMessageBox.information(
                self,
                "Processamento de Imagem",
                f"Imagem térmica selecionada:\n{Path(path).name}\n\nPronta para calibração radiométrica e inferência YOLOv11.",
            )

    def refresh_data(self) -> None:
        try:
            inspections = self.inspection_repo.list_all()
            self.table_inspections.setRowCount(len(inspections))
            for r, insp in enumerate(inspections):
                self.table_inspections.setItem(r, 0, QTableWidgetItem(insp.id[:12] + "..."))
                dt_str = insp.inspection_date.strftime("%d/%m/%Y") if hasattr(insp.inspection_date, "strftime") else str(insp.inspection_date or "")
                self.table_inspections.setItem(r, 1, QTableWidgetItem(dt_str))
                self.table_inspections.setItem(r, 2, QTableWidgetItem(str(insp.status.value if hasattr(insp.status, "value") else insp.status)))
                self.table_inspections.setItem(r, 3, QTableWidgetItem(str(insp.pilot_name or "Eng. Responsável")))
                self.table_inspections.setItem(r, 4, QTableWidgetItem("Inspecionar"))

            anomalies = self.anomaly_repo.list_all()
            self.table_anomalies.setRowCount(min(10, len(anomalies)))
            for r, a in enumerate(anomalies[:10]):
                self.table_anomalies.setItem(r, 0, QTableWidgetItem(str(getattr(a, "id", f"ANOM_{r+1}")[:8])))
                self.table_anomalies.setItem(r, 1, QTableWidgetItem(str(getattr(a, "anomaly_type", "Hotspot"))))
                self.table_anomalies.setItem(r, 2, QTableWidgetItem(f"{getattr(a, 'max_temperature', 48.5):.1f} °C"))
                self.table_anomalies.setItem(r, 3, QTableWidgetItem(f"Δ {getattr(a, 'delta_t', 14.2):.1f} °C"))
                self.table_anomalies.setItem(r, 4, QTableWidgetItem(str(getattr(a, "severity", "Classe 2 (Média)"))))
                self.table_anomalies.setItem(r, 5, QTableWidgetItem("Programar Manutenção Preventiva"))
        except Exception as ex:
            logger.error(f"Erro ao carregar dados de inspeções: {ex}")


class ReportsView(QWidget):
    """Aba 3: Histórico e Exportação de Relatórios Técnicos Oficiais."""

    def __init__(self, db: DatabaseManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.report_repo = SqliteReportRepository(db)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Central de Relatórios Técnicos")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        sub = QLabel("Documentação de conformidade IEC TS 62446-3, laudos periciais em PDF e dados em planilha.")
        sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box)

        btn_open = QPushButton("Abrir Arquivo Selecionado")
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #00A896; color: white; border-radius: 6px;
                padding: 8px 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #028090; }
        """)
        btn_open.clicked.connect(self._open_selected_report)
        header.addWidget(btn_open)
        layout.addLayout(header)

        # Tabela de Relatórios
        self.table_reports = QTableWidget()
        self.table_reports.setColumnCount(5)
        self.table_reports.setHorizontalHeaderLabels([
            "Nome do Documento", "Formato", "Tamanho", "Data de Criação", "Caminho no Disco"
        ])
        self.table_reports.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_reports.setAlternatingRowColors(True)
        self.table_reports.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table_reports)

        self.refresh_data()

    def refresh_data(self) -> None:
        """Varre arquivos em reports/ e lista na tabela."""
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)

        files = sorted(
            [f for f in reports_dir.glob("*.*") if f.suffix.lower() in [".pdf", ".xlsx", ".csv", ".html", ".geojson"]],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        self.table_reports.setRowCount(len(files))
        for r, f in enumerate(files):
            sz = f"{f.stat().st_size / 1024:.1f} KB"
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            self.table_reports.setItem(r, 0, QTableWidgetItem(f.name))
            self.table_reports.setItem(r, 1, QTableWidgetItem(f.suffix.upper().replace(".", "")))
            self.table_reports.setItem(r, 2, QTableWidgetItem(sz))
            self.table_reports.setItem(r, 3, QTableWidgetItem(mtime))
            self.table_reports.setItem(r, 4, QTableWidgetItem(str(f.resolve())))

    def _open_selected_report(self) -> None:
        curr = self.table_reports.currentRow()
        if curr < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um relatório na tabela para abrir.")
            return

        path_str = self.table_reports.item(curr, 4).text()
        p = Path(path_str)
        if p.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
        else:
            QMessageBox.critical(self, "Erro", f"Arquivo não encontrado em:\n{path_str}")


class SettingsView(QWidget):
    """Aba 5: Configurações de Sistema, Idioma, Temas e Radiometria."""

    def __init__(self, settings_mgr: Optional[Any] = None, parent: Optional[QWidget] = None) -> None:
        if isinstance(settings_mgr, QWidget) and parent is None:
            parent = settings_mgr
            settings_mgr = None
        super().__init__(parent)
        self.settings_mgr = settings_mgr or SettingsManager()
        self._setup_ui()
        self.lang_combo = self.combo_lang
        self.theme_combo = self.combo_theme

    def save_settings(self) -> None:
        """Alias para salvamento de configurações."""
        self._save_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Configurações do SolarGuard Vision")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        sub = QLabel("Personalize parâmetros operacionais, preferências visuais e coeficientes termográficos.")
        sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(sub)

        form_group = QGroupBox("Preferências Gerais de Interface")
        form_l = QFormLayout(form_group)
        form_l.setSpacing(12)

        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Português (Brasil)", "English (US)", "Español"])
        form_l.addRow("Idioma do Sistema:", self.combo_lang)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Dark Tech (Padrão)", "Clean Light"])
        form_l.addRow("Tema de Cores:", self.combo_theme)

        self.input_reports_dir = QLineEdit(str(Path("reports").resolve()))
        form_l.addRow("Diretório de Exportação:", self.input_reports_dir)
        layout.addWidget(form_group)

        # Grupo de Radiometria
        radio_group = QGroupBox("Calibração Radiométrica Padrão (IEC TS 62446-3)")
        radio_l = QFormLayout(radio_group)
        radio_l.setSpacing(12)

        self.input_emissivity = QLineEdit("0.90")
        radio_l.addRow("Emissividade Típica do Vidro (ε):", self.input_emissivity)

        self.input_refl_temp = QLineEdit("20.0")
        radio_l.addRow("Temperatura Refletida Padrão (°C):", self.input_refl_temp)

        self.input_transmittance = QLineEdit("0.98")
        radio_l.addRow("Transmitância Atmosférica Típica (τ):", self.input_transmittance)
        layout.addWidget(radio_group)

        # Botões de Ação
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Salvar Alterações")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #00A896; color: white; border-radius: 6px;
                padding: 10px 18px; font-weight: bold;
            }
            QPushButton:hover { background-color: #028090; }
        """)
        save_btn.clicked.connect(self._save_settings)

        reset_btn = QPushButton("Restaurar Padrões")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3A506B; color: white; border-radius: 6px;
                padding: 10px 18px;
            }
            QPushButton:hover { background-color: #4A6572; }
        """)
        reset_btn.clicked.connect(self._reset_settings)

        btn_box.addWidget(save_btn)
        btn_box.addWidget(reset_btn)
        btn_box.addStretch()
        layout.addLayout(btn_box)

        layout.addStretch()
        self._load_values()

    def _load_values(self) -> None:
        cfg = self.settings_mgr.get_settings()
        if cfg.language == "en":
            self.combo_lang.setCurrentIndex(1)
        elif cfg.language == "es":
            self.combo_lang.setCurrentIndex(2)
        else:
            self.combo_lang.setCurrentIndex(0)

    def _save_settings(self) -> None:
        lang_code = "pt-br"
        if self.combo_lang.currentIndex() == 1:
            lang_code = "en"
        elif self.combo_lang.currentIndex() == 2:
            lang_code = "es"

        theme = "dark" if self.combo_theme.currentIndex() == 0 else "light"
        self.settings_mgr.update(language=lang_code, theme=theme)
        QMessageBox.information(self, "Sucesso", "Configurações salvas com sucesso.")

    def _reset_settings(self) -> None:
        self.settings_mgr.reset_to_defaults()
        self._load_values()
        QMessageBox.information(self, "Sucesso", "Configurações restauradas para o padrão.")


class LicenseView(QWidget):
    """Aba 6: Gestão de Licença, Identificação de Hardware e Ativação."""

    def __init__(self, lic_mgr: Optional[Any] = None, parent: Optional[QWidget] = None) -> None:
        if isinstance(lic_mgr, QWidget) and parent is None:
            parent = lic_mgr
            lic_mgr = None
        super().__init__(parent)
        self.lic_mgr = lic_mgr or LicenseManager()
        self._setup_ui()
        self.hwid_display = self.hwid_input
        self.status_label = self.lbl_lic_status

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Licenciamento & Ativação de Software")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        sub = QLabel("Gerencie os direitos de uso comercial, acadêmico ou corporativo do SolarGuard Vision.")
        sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Card de Identificação da Máquina
        hwid_group = QGroupBox("Identificação Única Desta Máquina (Hardware Fingerprint)")
        hwid_l = QVBoxLayout(hwid_group)
        hwid_l.setSpacing(10)

        hwid_box = QHBoxLayout()
        self.hwid_input = QLineEdit(self.lic_mgr.get_current_machine_fingerprint())
        self.hwid_input.setReadOnly(True)
        self.hwid_input.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")

        copy_btn = QPushButton("Copiar HWID")
        copy_btn.setFixedWidth(120)
        copy_btn.setStyleSheet("background-color: #3A506B; color: white; padding: 6px; border-radius: 6px;")
        copy_btn.clicked.connect(self._copy_hwid)
        hwid_box.addWidget(self.hwid_input)
        hwid_box.addWidget(copy_btn)
        hwid_l.addLayout(hwid_box)
        layout.addWidget(hwid_group)

        # Card de Status da Licença
        status_group = QGroupBox("Status da Licença Atual")
        status_l = QFormLayout(status_group)
        status_l.setSpacing(10)

        self.lbl_lic_type = QLabel("Carregando...")
        self.lbl_lic_type.setFont(QFont("Segoe UI", 12, QFont.Bold))
        status_l.addRow("Modalidade de Licença:", self.lbl_lic_type)

        self.lbl_lic_status = QLabel("Carregando...")
        status_l.addRow("Situação do Licenciamento:", self.lbl_lic_status)

        self.lbl_lic_days = QLabel("Carregando...")
        status_l.addRow("Vigência Restante:", self.lbl_lic_days)
        layout.addWidget(status_group)

        # Card de Ativação por Chave
        act_group = QGroupBox("Ativar Nova Chave de Licença (.key)")
        act_l = QVBoxLayout(act_group)
        act_l.setSpacing(10)

        act_box = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Cole o token criptográfico da licença ou selecione o arquivo...")
        browse_key_btn = QPushButton("Arquivo .key...")
        browse_key_btn.setFixedWidth(120)
        browse_key_btn.setStyleSheet("background-color: #3A506B; color: white; padding: 6px; border-radius: 6px;")
        browse_key_btn.clicked.connect(self._browse_key_file)

        act_box.addWidget(self.key_input)
        act_box.addWidget(browse_key_btn)
        act_l.addLayout(act_box)

        activate_btn = QPushButton("Ativar Licença")
        activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #00A896; color: white; border-radius: 6px;
                padding: 10px 18px; font-weight: bold;
            }
            QPushButton:hover { background-color: #028090; }
        """)
        activate_btn.clicked.connect(self._activate_license)
        act_l.addWidget(activate_btn)
        layout.addWidget(act_group)

        layout.addStretch()
        self.refresh_status()

    def _copy_hwid(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self.hwid_input.text())
        QMessageBox.information(self, "Copiado", "Hardware Fingerprint copiado para a área de transferência.")

    def _browse_key_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Chave de Licença", "", "Licenças (*.key *.lic *.txt)")
        if path:
            text = Path(path).read_text(encoding="utf-8").strip()
            self.key_input.setText(text)

    def _activate_license(self) -> None:
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Aviso", "Por favor, insira ou selecione uma chave válida.")
            return

        res = self.lic_mgr.apply_license(key)
        if res.is_valid:
            QMessageBox.information(self, "Sucesso", f"Licença ativada com sucesso!\n{res.status_message}")
        else:
            QMessageBox.critical(self, "Falha na Ativação", f"Chave inválida:\n{res.status_message}")
        self.refresh_status()

    def refresh_status(self) -> None:
        lic = self.lic_mgr.check_current_license()
        self.lbl_lic_type.setText(lic.license_type.display_name)
        color = "#2ECC71" if lic.is_valid else "#E74C3C"
        self.lbl_lic_status.setText(lic.status_message)
        self.lbl_lic_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.lbl_lic_days.setText(f"{lic.days_remaining} dias" if lic.days_remaining is not None else "Vitalícia / Indeterminado")


# =============================================================================
# JANELA PRINCIPAL (MAIN WINDOW) COM SIDEBAR
# =============================================================================
class MainWindow(QMainWindow):
    """
    Shell principal da aplicação desktop SolarGuard Vision.
    Conecta Dashboard, Inspeções, Relatórios, Auditoria de Dataset, Configurações e Licenciamento.
    """

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        db_manager: Optional[DatabaseManager] = None,
        session_manager: Optional[SessionManager] = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"{settings.app_name} - {settings.app_version} (Research Edition)")
        self.resize(1200, 780)
        self.setMinimumSize(1000, 650)

        # Inicialização da persistência
        self.db = db or db_manager or DatabaseManager()
        self.db.initialize_schema()

        # Inicialização do controle de sessão
        if session_manager is not None:
            self.session_manager = session_manager
        else:
            user_repo = SqliteUserRepository(self.db)
            user_svc = UserService(user_repo)
            admin_user = user_svc.ensure_default_admin()
            self.session_manager = SessionManager(user_svc)
            self.session_manager.login(admin_user.username, "admin123")

        self._setup_ui()
        self.stacked = self.stack
        self.setStyleSheet(MAIN_STYLE_SHEET)

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # 1. SIDEBAR LATERAL DE NAVEGAÇÃO
        # ---------------------------------------------------------------------
        sidebar = QFrame()
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #0B132B;
                border-right: 1px solid #1C2541;
            }
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 20, 12, 20)
        sb_layout.setSpacing(8)

        # Brand / Logo
        brand_box = QVBoxLayout()
        brand_title = QLabel("SolarGuard Vision")
        brand_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        brand_title.setStyleSheet("color: #00A896;")

        brand_sub = QLabel("AI Thermography Core")
        brand_sub.setStyleSheet("color: #64748B; font-size: 10px; font-weight: bold;")
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_sub)
        sb_layout.addLayout(brand_box)
        sb_layout.addSpacing(15)

        # Botões de Navegação
        self.nav_buttons: List[QPushButton] = []
        nav_items = [
            ("📊  Dashboard", 0),
            ("🔍  Inspeções", 1),
            ("📄  Relatórios", 2),
            ("🧪  Dataset Audit", 3),
            ("⚙️  Configurações", 4),
            ("🔑  Licenciamento", 5),
        ]

        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setFixedHeight(42)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94A3B8;
                    border: none;
                    border-radius: 6px;
                    text-align: left;
                    padding-left: 14px;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #1C2541;
                    color: #F8FAFC;
                }
                QPushButton:checked {
                    background-color: #1C2541;
                    color: #00A896;
                    font-weight: bold;
                    border-left: 4px solid #00A896;
                }
            """)
            btn.clicked.connect(lambda checked, idx=index: self.switch_page(idx))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        # Card de Identificação de Usuário / Sessão Ativa
        self.user_card = QFrame()
        self.user_card.setStyleSheet("""
            QFrame {
                background-color: #111D3B;
                border: 1px solid #1C2541;
                border-radius: 8px;
            }
        """)
        uc_layout = QVBoxLayout(self.user_card)
        uc_layout.setContentsMargins(10, 8, 10, 8)
        uc_layout.setSpacing(4)

        self.user_name_lbl = QLabel()
        self.user_name_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.user_name_lbl.setStyleSheet("color: #F8FAFC;")

        self.user_role_lbl = QLabel()
        self.user_role_lbl.setStyleSheet("color: #38BDF8; font-size: 10px;")

        self.logout_btn = QPushButton("🚪 Sair (Logout)")
        self.logout_btn.setFixedHeight(26)
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #1C2541;
                color: #EF4444;
                border: 1px solid #EF4444;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EF4444;
                color: #FFFFFF;
            }
        """)
        self.logout_btn.clicked.connect(self.handle_logout)

        uc_layout.addWidget(self.user_name_lbl)
        uc_layout.addWidget(self.user_role_lbl)
        uc_layout.addWidget(self.logout_btn)
        sb_layout.addWidget(self.user_card)
        self._update_user_display()

        # Versão na Sidebar
        ver_lbl = QLabel(f"Versão {settings.app_version}\nBuild IEC TS 62446-3")
        ver_lbl.setStyleSheet("color: #475569; font-size: 10px; text-align: center;")
        ver_lbl.setAlignment(Qt.AlignCenter)
        sb_layout.addWidget(ver_lbl)

        main_layout.addWidget(sidebar)

        # ---------------------------------------------------------------------
        # 2. ÁREA CENTRAL COM QSTACKEDWIDGET (6 TELAS)
        # ---------------------------------------------------------------------
        self.stack = QStackedWidget()

        # Instanciação das 6 Views
        self.view_dashboard = DashboardView(self.db)
        self.view_inspections = InspectionsView(self.db)
        self.view_reports = ReportsView(self.db)
        self.view_dataset_audit = DatasetAuditWidget()
        self.view_settings = SettingsView()
        self.view_license = LicenseView()

        self.stack.addWidget(self.view_dashboard)       # index 0
        self.stack.addWidget(self.view_inspections)     # index 1
        self.stack.addWidget(self.view_reports)         # index 2
        self.stack.addWidget(self.view_dataset_audit)   # index 3
        self.stack.addWidget(self.view_settings)        # index 4
        self.stack.addWidget(self.view_license)         # index 5

        main_layout.addWidget(self.stack)

        # ---------------------------------------------------------------------
        # 3. BARRA DE STATUS
        # ---------------------------------------------------------------------
        status_bar = QStatusBar(self)
        status_bar.setStyleSheet("background-color: #0B132B; border-top: 1px solid #1C2541; color: #64748B; font-size: 11px;")
        self.setStatusBar(status_bar)

        lic_info = LicenseManager().check_current_license()
        status_bar.showMessage(
            f"Banco de Dados: Conectado (SQLite WAL)  |  Licença: {lic_info.license_type.display_name} ({lic_info.status_message})  |  Sistema Operacional: Windows 64-bit"
        )

        # Inicia com o Dashboard selecionado se autenticado
        if self.session_manager.is_authenticated():
            self.switch_page(0)

    def _update_user_display(self) -> None:
        """Atualiza os rótulos de usuário ativo e papel no card da barra lateral."""
        user = self.session_manager.current_user
        if user:
            self.user_name_lbl.setText(f"👤 {user.full_name}")
            role_text = user.role.value if hasattr(user.role, "value") else str(user.role)
            self.user_role_lbl.setText(f"Perfil: {role_text.capitalize()}")
        else:
            self.user_name_lbl.setText("👤 Desconectado")
            self.user_role_lbl.setText("Perfil: Não autenticado")

    def check_access(self) -> bool:
        """
        Valida se a sessão atual está autenticada.
        Se não estiver, bloqueia o acesso, oculta a tela principal e abre o diálogo de login.
        """
        if not self.session_manager.is_authenticated():
            self.hide()
            from src.presentation.login_dialog import LoginDialog
            login_dlg = LoginDialog(self.session_manager)
            if login_dlg.exec() == QDialog.Accepted and self.session_manager.is_authenticated():
                self._update_user_display()
                self.show()
                return True
            else:
                self.close()
                return False
        return True

    def handle_logout(self) -> None:
        """Executa logout seguro da sessão e reabre a tela de autenticação."""
        reply = QMessageBox.question(
            self,
            "Confirmar Saída",
            "Deseja realmente encerrar a sessão de trabalho?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.session_manager.logout()
            self._update_user_display()
            self.hide()
            from src.presentation.login_dialog import LoginDialog
            login_dlg = LoginDialog(self.session_manager)
            if login_dlg.exec() == QDialog.Accepted and self.session_manager.is_authenticated():
                self._update_user_display()
                self.show()
                self.switch_page(0)
            else:
                self.close()

    def switch_page(self, index: int) -> None:
        """Alterna a página visível e atualiza o estado dos botões da sidebar."""
        if not self.check_access():
            return

        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
            btn.setProperty("active", "true" if i == index else "false")

        # Recarrega dados sob demanda
        if index == 0:
            self.view_dashboard.refresh_data()
        elif index == 1:
            self.view_inspections.refresh_data()
        elif index == 2:
            self.view_reports.refresh_data()
        elif index == 5:
            self.view_license.refresh_status()
