"""
Interface Gráfica PySide6 para Auditoria e Diagnóstico de Datasets YOLOv11.
Permite inspeção de paridade imagem-rótulo, cálculo de distribuição e exportação de PDF.
"""

from pathlib import Path
from typing import Optional
import sys

try:
    from PySide6.QtWidgets import (
        QWidget,
        QMainWindow,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QFileDialog,
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QTextEdit,
        QFrame,
        QProgressBar,
        QMessageBox,
    )
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QFont, QColor
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    QWidget = object
    QMainWindow = object
    class QThread:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
    def Signal(*args): return lambda: None

from src.application.dataset.dataset_audit import DatasetAuditor, DatasetAuditResult
from src.application.dataset.dataset_report import DatasetPdfReportGenerator
from src.core.logger import get_logger

logger = get_logger("DatasetAuditWindow")


class AuditWorkerThread(QThread):
    """Thread em segundo plano para não congelar a interface durante a auditoria."""
    finished_signal = Signal(object)
    error_signal = Signal(str)

    def __init__(self, dataset_path: str) -> None:
        super().__init__()
        self.dataset_path = dataset_path

    def run(self) -> None:
        try:
            auditor = DatasetAuditor()
            result = auditor.audit(self.dataset_path)
            self.finished_signal.emit(result)
        except Exception as ex:
            logger.error(f"Erro na thread de auditoria: {ex}")
            self.error_signal.emit(str(ex))


class DatasetAuditWidget(QWidget):
    """
    Widget reutilizável para auditoria de integridade e balanceamento de datasets de IA fotovoltaica.
    Pode ser acoplado como aba na MainWindow ou exibido de forma independente.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_result: Optional[DatasetAuditResult] = None
        self.worker_thread: Optional[AuditWorkerThread] = None

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        """Monta os componentes visuais do widget de auditoria."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. Cabeçalho de Título
        title_label = QLabel("Auditoria e Validação de Datasets YOLOv11")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        subtitle_label = QLabel("Verifique consistência de rótulos, imagens órfãs, distribuição de classes e balanceamento.")
        subtitle_label.setStyleSheet("color: #64748B; font-size: 11px;")
        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        # 2. Barra de Seleção de Diretório
        dir_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Selecione o diretório raiz do dataset YOLO (com images/ e labels/)...")
        self.path_input.setReadOnly(True)

        browse_btn = QPushButton("Procurar Pasta...")
        browse_btn.setFixedWidth(130)
        browse_btn.clicked.connect(self._browse_dataset_dir)

        self.audit_btn = QPushButton("Executar Auditoria")
        self.audit_btn.setFixedWidth(150)
        self.audit_btn.setEnabled(False)
        self.audit_btn.clicked.connect(self._run_audit)

        dir_layout.addWidget(self.path_input)
        dir_layout.addWidget(browse_btn)
        dir_layout.addWidget(self.audit_btn)
        main_layout.addLayout(dir_layout)

        # Barra de Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminado
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        main_layout.addWidget(self.progress_bar)

        # 3. Cards de Resumo (KPIs)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        self.card_images = self._create_kpi_card("TOTAL IMAGENS", "0")
        self.card_annotations = self._create_kpi_card("ANOTAÇÕES", "0")
        self.card_orphans = self._create_kpi_card("INCONSISTÊNCIAS", "0")
        self.card_balance = self._create_kpi_card("STATUS", "Não Auditado")

        cards_layout.addWidget(self.card_images)
        cards_layout.addWidget(self.card_annotations)
        cards_layout.addWidget(self.card_orphans)
        cards_layout.addWidget(self.card_balance)
        main_layout.addLayout(cards_layout)

        # 4. Tabela de Distribuição de Classes
        table_label = QLabel("Distribuição Quantitativa por Classe:")
        table_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        main_layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nome da Classe", "Amostras", "Proporção (%)", "Imagens Contendo"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFixedHeight(180)
        main_layout.addWidget(self.table)

        # 5. Painel de Diagnóstico e Recomendações
        log_label = QLabel("Diagnóstico e Recomendações Técnicas:")
        log_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        main_layout.addWidget(log_label)

        self.diagnostic_text = QTextEdit()
        self.diagnostic_text.setReadOnly(True)
        self.diagnostic_text.setPlaceholderText("O diagnóstico e recomendações para o treinamento aparecerão aqui...")
        self.diagnostic_text.setFixedHeight(120)
        main_layout.addWidget(self.diagnostic_text)

        # 6. Rodapé com Ações
        footer_layout = QHBoxLayout()
        self.status_footer_label = QLabel("Pronto para auditar.")
        self.status_footer_label.setStyleSheet("color: #64748B; font-size: 11px;")

        self.pdf_btn = QPushButton("Exportar Relatório PDF...")
        self.pdf_btn.setFixedWidth(190)
        self.pdf_btn.setEnabled(False)
        self.pdf_btn.clicked.connect(self._export_pdf)

        footer_layout.addWidget(self.status_footer_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.pdf_btn)
        main_layout.addLayout(footer_layout)

    def _create_kpi_card(self, title: str, initial_value: str) -> QFrame:
        """Cria um card estilizado para métricas-chave."""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setSpacing(3)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #64748B; font-size: 10px; font-weight: bold;")
        lbl_val = QLabel(initial_value)
        lbl_val.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lbl_val.setStyleSheet("color: #0F172A;")
        lbl_val.setObjectName("value_label")

        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_val)
        return card

    def _set_card_value(self, card: QFrame, value: str, color_hex: Optional[str] = None) -> None:
        """Atualiza o texto e a cor de um card de KPI."""
        val_label = card.findChild(QLabel, "value_label")
        if val_label:
            val_label.setText(value)
            if color_hex:
                val_label.setStyleSheet(f"color: {color_hex}; font-weight: bold;")
            else:
                val_label.setStyleSheet("color: #0F172A; font-weight: bold;")

    def _apply_styles(self) -> None:
        """Aplica folha de estilos CSS refinada."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
            QLineEdit {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #0284C7;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
            QPushButton:disabled {
                background-color: #94A3B8;
                color: #E2E8F0;
            }
            QTableWidget {
                border: 1px solid #E2E8F0;
                gridline-color: #F1F5F9;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #1E293B;
                color: white;
                padding: 6px;
                font-weight: bold;
                border: none;
            }
            QTextEdit {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)

    def _browse_dataset_dir(self) -> None:
        """Abre diálogo para seleção de pasta do dataset."""
        dir_selected = QFileDialog.getExistingDirectory(self, "Selecionar Diretório do Dataset YOLOv11")
        if dir_selected:
            self.path_input.setText(dir_selected)
            self.audit_btn.setEnabled(True)
            self.status_footer_label.setText("Diretório selecionado. Clique em 'Executar Auditoria'.")

    def _run_audit(self) -> None:
        """Inicia o processo de auditoria na thread secundária."""
        target_path = self.path_input.text().strip()
        if not target_path or not Path(target_path).exists():
            QMessageBox.warning(self, "Aviso", "Por favor selecione um diretório válido.")
            return

        self.audit_btn.setEnabled(False)
        self.pdf_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_footer_label.setText("Auditando dataset... Aguarde.")

        self.worker_thread = AuditWorkerThread(target_path)
        self.worker_thread.finished_signal.connect(self._on_audit_finished)
        self.worker_thread.error_signal.connect(self._on_audit_error)
        self.worker_thread.start()

    def _on_audit_finished(self, result: DatasetAuditResult) -> None:
        """Recebe o resultado da auditoria e atualiza a visualização."""
        self.current_result = result
        self.progress_bar.setVisible(False)
        self.audit_btn.setEnabled(True)
        self.pdf_btn.setEnabled(True)

        # Atualiza Cards
        self._set_card_value(self.card_images, str(result.validation.total_images))
        self._set_card_value(self.card_annotations, str(result.statistics.total_annotations))

        inconsistencies_count = (
            len(result.validation.orphan_labels)
            + len(result.validation.invalid_class_errors)
            + len(result.validation.syntax_errors)
        )
        orphan_color = "#DC2626" if inconsistencies_count > 0 else "#16A34A"
        self._set_card_value(self.card_orphans, str(inconsistencies_count), orphan_color)

        status_text = "APROVADO" if result.is_approved_for_training else "REPROVADO"
        status_color = "#16A34A" if result.is_approved_for_training else "#DC2626"
        self._set_card_value(self.card_balance, status_text, status_color)

        # Preenche Tabela de Classes
        self.table.setRowCount(0)
        for row_idx, item in enumerate(result.statistics.class_distribution):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(item.class_id)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(item.class_name))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(item.instance_count)))
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"{item.percentage:.1f}%"))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(item.images_containing_count)))

        # Preenche Painel de Diagnóstico
        diag_lines = [
            f"RESUMO: {result.executive_summary}",
            f"BALANCEAMENTO: {result.balance.severity.display_name} (IR: {result.balance.imbalance_ratio}x, Entropia: {result.balance.normalized_entropy*100:.1f}%)",
            "",
            "RECOMENDAÇÕES DE TREINAMENTO:",
        ]
        for rec in result.balance.recommendations:
            diag_lines.append(f"  • {rec}")

        if result.validation.orphan_labels:
            diag_lines.append(f"\nAVISO: {len(result.validation.orphan_labels)} labels órfãos encontrados!")

        self.diagnostic_text.setText("\n".join(diag_lines))
        self.status_footer_label.setText("Auditoria finalizada com sucesso. Relatório PDF pronto para exportação.")

    def _on_audit_error(self, err_msg: str) -> None:
        """Trata erros ocorridos na auditoria."""
        self.progress_bar.setVisible(False)
        self.audit_btn.setEnabled(True)
        self.status_footer_label.setText("Falha na auditoria.")
        QMessageBox.critical(self, "Erro na Auditoria", f"Ocorreu uma falha ao auditar o dataset:\n{err_msg}")

    def _export_pdf(self) -> None:
        """Gera e salva o relatório técnico em PDF."""
        if not self.current_result:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Relatório de Auditoria PDF",
            "relatorio_auditoria_dataset.pdf",
            "Arquivos PDF (*.pdf)",
        )
        if save_path:
            try:
                pdf_gen = DatasetPdfReportGenerator()
                out = pdf_gen.generate_report(self.current_result, save_path)
                QMessageBox.information(
                    self,
                    "Sucesso",
                    f"Relatório PDF gerado com sucesso em:\n{out}",
                )
            except Exception as ex:
                QMessageBox.critical(self, "Erro", f"Falha ao gerar relatório PDF:\n{ex}")


class DatasetAuditWindow(QMainWindow):
    """
    Janela desktop individual para auditoria de datasets YOLOv11 (wrapper para DatasetAuditWidget).
    Mantém 100% de retrocompatibilidade com a API e testes legados.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SolarGuard Vision - Auditoria de Dataset YOLOv11")
        self.resize(950, 720)
        self.audit_widget = DatasetAuditWidget(self)
        self.setCentralWidget(self.audit_widget)

        # Referências diretas para retrocompatibilidade
        self.path_input = self.audit_widget.path_input
        self.audit_btn = self.audit_widget.audit_btn
        self.table = self.audit_widget.table
        self.pdf_btn = self.audit_widget.pdf_btn
        self.card_images = self.audit_widget.card_images
        self.card_annotations = self.audit_widget.card_annotations
        self.card_orphans = self.audit_widget.card_orphans
        self.card_balance = self.audit_widget.card_balance
        self.progress_bar = self.audit_widget.progress_bar
        self.status_footer_label = self.audit_widget.status_footer_label

    def __getattr__(self, name: str):
        # Fallback para qualquer outro atributo interno
        if "audit_widget" in self.__dict__ and hasattr(self.audit_widget, name):
            return getattr(self.audit_widget, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
