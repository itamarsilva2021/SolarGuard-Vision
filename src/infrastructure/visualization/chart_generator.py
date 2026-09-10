from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import matplotlib
matplotlib.use("Agg")  # Backend não-interativo seguro para ambiente desktop e threads
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
import numpy as np
from datetime import datetime

if TYPE_CHECKING:
    from src.application.dtos.dashboard_dtos import DashboardData

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("ChartGenerator")



class ChartGenerator:
    """
    Gerador de gráficos analíticos e painéis visuais para o Dashboard e Relatórios Técnicos.
    Utiliza paletas e tipografia de alto padrão visual com estilo Dark/Tech.
    """

    # Cores corporativas para falhas
    FAULT_COLORS = {
        "Hotspot": "#E74C3C",
        "Módulo Desconectado": "#E67E22",
        "Degradação PID": "#9B59B6",
        "Sujidade / Poeira": "#F39C12",
        "Sombreamento Parcial": "#3498DB",
        "Módulo Saudável (Sem Falha)": "#2ECC71",
        "Outros": "#95A5A6",
    }

    # Cores normativas IEC TS 62446-3
    SEVERITY_COLORS = {
        "Crítico (Classe 3 - IEC)": "#E74C3C",
        "Médio (Classe 2 - IEC)": "#E67E22",
        "Baixo (Classe 1 - IEC)": "#F1C40F",
        "Informativo / Normal": "#2ECC71",
    }

    def __init__(self, output_dir: Optional[Path | str] = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else settings.reports_dir / "charts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Configuração visual padrão do matplotlib
        self._apply_style()

    def _apply_style(self) -> None:
        """Aplica tema visual moderno, escuro e técnico para os gráficos."""
        plt.style.use("dark_background")
        plt.rcParams.update({
            "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
            "font.family": "sans-serif",
            "figure.facecolor": "#1A1D24",
            "axes.facecolor": "#222631",
            "axes.edgecolor": "#3A4153",
            "axes.labelcolor": "#E0E6ED",
            "text.color": "#E0E6ED",
            "xtick.color": "#A0AEC0",
            "ytick.color": "#A0AEC0",
            "grid.color": "#2D3446",
            "grid.linestyle": "--",
            "grid.alpha": 0.5,
        })

    def generate_fault_distribution_pie(
        self,
        faults_by_type: Dict[str, int],
        output_filename: str = "chart_faults_distribution.png",
    ) -> Path:
        """
        Gera gráfico Donut (rosca) com a distribuição percentual de tipos de falhas.
        """
        out_path = self.output_dir / output_filename

        # Filtrar valores maiores que zero
        valid_items = {k: v for k, v in faults_by_type.items() if v > 0}
        if not valid_items:
            valid_items = {"Sem falhas detectadas": 1}

        labels = list(valid_items.keys())
        sizes = list(valid_items.values())
        colors = [self.FAULT_COLORS.get(lbl, "#34495E") for lbl in labels]

        fig, ax = plt.subplots(figsize=(6, 5), dpi=150)
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            pctdistance=0.75,
            textprops={"fontsize": 9, "color": "#E0E6ED"},
            wedgeprops={"width": 0.45, "edgecolor": "#1A1D24", "linewidth": 2},
        )

        for autotext in autotexts:
            autotext.set_fontsize(8)
            autotext.set_weight("bold")
            autotext.set_color("#FFFFFF")

        ax.set_title("Distribuição de Falhas por Categoria", fontsize=12, pad=15, weight="bold")
        fig.tight_layout()
        fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        logger.info(f"Gráfico de distribuição gerado em: {out_path}")
        return out_path

    def generate_severity_bar_chart(
        self,
        faults_by_severity: Dict[str, int],
        output_filename: str = "chart_severity_ranking.png",
    ) -> Path:
        """
        Gera gráfico de barras com classificação das falhas por severidade IEC TS 62446-3.
        """
        out_path = self.output_dir / output_filename

        labels = list(faults_by_severity.keys())
        counts = list(faults_by_severity.values())
        colors = [self.SEVERITY_COLORS.get(lbl, "#E67E22") for lbl in labels]

        fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
        bars = ax.barh(labels, counts, color=colors, height=0.55, edgecolor="#1A1D24")

        # Anotar contagem numérica em cada barra
        for bar in bars:
            w = bar.get_width()
            ax.text(
                w + max(counts or [1]) * 0.02,
                bar.get_y() + bar.get_height() / 2.0,
                f"{int(w)}",
                ha="left",
                va="center",
                fontsize=9,
                weight="bold",
                color="#E0E6ED",
            )

        ax.set_title("Classificação de Severidade (IEC TS 62446-3)", fontsize=12, pad=12, weight="bold")
        ax.set_xlabel("Quantidade de Ocorrências", fontsize=10)
        ax.grid(axis="x", linestyle="--", alpha=0.5)
        ax.invert_yaxis()  # Ordem do mais crítico no topo

        fig.tight_layout()
        fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        logger.info(f"Gráfico de severidades gerado em: {out_path}")
        return out_path

    def generate_historical_trend_chart(
        self,
        history_timeline: List[Dict[str, Any]],
        output_filename: str = "chart_historical_trend.png",
    ) -> Path:
        """
        Gera gráfico temporal (Time Series) mostrando evolução de inspeções e defeitos detectados.
        """
        out_path = self.output_dir / output_filename

        fig, ax1 = plt.subplots(figsize=(8, 4.5), dpi=150)

        if not history_timeline:
            # Fallback caso não haja inspeções registradas ainda
            dates = [datetime.now()]
            faults = [0]
            inspections = [0]
        else:
            dates = [item["date"] for item in history_timeline]
            faults = [item.get("faults", 0) for item in history_timeline]
            inspections = [item.get("inspections", 1) for item in history_timeline]

        # Linha e área para defeitos encontrados
        line1 = ax1.plot(dates, faults, color="#E74C3C", marker="o", linewidth=2.5, label="Falhas Detectadas")
        ax1.fill_between(dates, faults, color="#E74C3C", alpha=0.20)
        ax1.set_ylabel("Quantidade de Falhas", color="#E74C3C", fontsize=10, weight="bold")
        ax1.tick_params(axis="y", labelcolor="#E74C3C")

        # Segundo eixo para quantidade de inspeções
        ax2 = ax1.twinx()
        line2 = ax2.bar(dates, inspections, width=2.0, color="#3498DB", alpha=0.45, label="Inspeções Realizadas")
        ax2.set_ylabel("Inspeções de Voo", color="#3498DB", fontsize=10, weight="bold")
        ax2.tick_params(axis="y", labelcolor="#3498DB")

        ax1.set_title("Evolução Histórica de Inspeções e Falhas", fontsize=12, pad=15, weight="bold")
        ax1.grid(True, linestyle="--", alpha=0.5)

        # Formatação de datas no eixo X
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%y"))
        fig.autofmt_xdate()

        fig.tight_layout()
        fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        logger.info(f"Gráfico histórico gerado em: {out_path}")
        return out_path

    def generate_consolidated_dashboard_figure(
        self,
        dashboard_data: DashboardData,
        output_filename: str = "dashboard_overview.png",
    ) -> Path:
        """
        Gera um painel completo consolidado 2x2 com KPIs, Donut, Barras e Linha temporal.
        Ideal para exibição central na interface gráfica desktop e anexação em relatórios executivos.
        """
        out_path = self.output_dir / output_filename
        fig = plt.figure(figsize=(14, 9), dpi=150)
        gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.28)

        # -------------------------------------------------------------
        # Painel 1: Cards com KPIs Numéricos
        # -------------------------------------------------------------
        ax_kpi = fig.add_subplot(gs[0, 0])
        ax_kpi.axis("off")
        ax_kpi.set_title("Indicadores Principais (KPIs)", fontsize=13, weight="bold", pad=10)

        kpis = dashboard_data.kpis
        cards = [
            ("Inspeções Realizadas", f"{kpis.total_inspections}", "#3498DB"),
            ("Falhas Identificadas", f"{kpis.total_faults}", "#E67E22"),
            ("Falhas Críticas (Classe 3)", f"{kpis.critical_faults}", "#E74C3C"),
            ("Conformidade IEC TS 62446", f"{kpis.iec_compliance_rate_pct:.1f}%", "#2ECC71"),
            ("Gradiente Térmico Máximo", f"ΔT {kpis.max_delta_t_celsius:.1f}°C", "#F1C40F"),
            ("Temperatura Mais Alta", f"{kpis.highest_temp_celsius:.1f}°C", "#E74C3C"),
        ]

        # Desenhar cards em grid 3x2 dentro do subplot
        for i, (title, val, color) in enumerate(cards):
            row = i // 2
            col = i % 2
            x = 0.05 + col * 0.48
            y = 0.68 - row * 0.32

            rect = FancyBboxPatch(
                (x, y), 0.44, 0.26,
                boxstyle="round,pad=0.01",
                transform=ax_kpi.transAxes,
                facecolor="#222631",
                edgecolor="#3A4153",
                linewidth=1.5,
            )
            ax_kpi.add_patch(rect)

            ax_kpi.text(x + 0.03, y + 0.17, title, transform=ax_kpi.transAxes,
                        fontsize=8.5, color="#A0AEC0", weight="bold")
            ax_kpi.text(x + 0.03, y + 0.05, val, transform=ax_kpi.transAxes,
                        fontsize=14, color=color, weight="bold")

        # -------------------------------------------------------------
        # Painel 2: Donut Chart de Falhas por Categoria
        # -------------------------------------------------------------
        ax_pie = fig.add_subplot(gs[0, 1])
        type_items = {k: v for k, v in dashboard_data.distribution.by_type.items() if v > 0}
        if not type_items:
            type_items = {"Sem Falhas": 1}

        labels_pie = list(type_items.keys())
        sizes_pie = list(type_items.values())
        colors_pie = [self.FAULT_COLORS.get(lbl, "#34495E") for lbl in labels_pie]

        ax_pie.pie(
            sizes_pie,
            labels=labels_pie,
            autopct="%1.0f%%",
            startangle=140,
            colors=colors_pie,
            pctdistance=0.75,
            textprops={"fontsize": 8, "color": "#E0E6ED"},
            wedgeprops={"width": 0.42, "edgecolor": "#1A1D24", "linewidth": 1.5},
        )
        ax_pie.set_title("Distribuição por Tipo de Falha", fontsize=13, weight="bold", pad=10)

        # -------------------------------------------------------------
        # Painel 3: Barras de Severidade IEC
        # -------------------------------------------------------------
        ax_bar = fig.add_subplot(gs[1, 0])
        sev_items = dashboard_data.distribution.by_severity
        labels_sev = list(sev_items.keys())
        counts_sev = list(sev_items.values())
        colors_sev = [self.SEVERITY_COLORS.get(lbl, "#E67E22") for lbl in labels_sev]

        bars = ax_bar.barh(labels_sev, counts_sev, color=colors_sev, height=0.50)
        for bar in bars:
            w = bar.get_width()
            ax_bar.text(w + max(counts_sev or [1]) * 0.02, bar.get_y() + bar.get_height() / 2.0,
                        f"{int(w)}", va="center", fontsize=8.5, weight="bold", color="#E0E6ED")

        ax_bar.set_title("Severidade Normativa (IEC TS 62446-3)", fontsize=13, weight="bold", pad=10)
        ax_bar.set_xlabel("Ocorrências", fontsize=9)
        ax_bar.grid(axis="x", linestyle="--", alpha=0.4)
        ax_bar.invert_yaxis()

        # -------------------------------------------------------------
        # Painel 4: Histórico Temporal
        # -------------------------------------------------------------
        ax_hist = fig.add_subplot(gs[1, 1])
        timeline = dashboard_data.distribution.timeline_series
        if not timeline:
            dates = [datetime.now()]
            fault_vals = [0]
        else:
            dates = [t["date"] for t in timeline]
            fault_vals = [t.get("faults", 0) for t in timeline]

        ax_hist.plot(dates, fault_vals, color="#E74C3C", marker="o", linewidth=2)
        ax_hist.fill_between(dates, fault_vals, color="#E74C3C", alpha=0.25)
        ax_hist.set_title("Histórico de Falhas ao Longo do Tempo", fontsize=13, weight="bold", pad=10)
        ax_hist.set_ylabel("Falhas", fontsize=9)
        ax_hist.grid(True, linestyle="--", alpha=0.4)
        ax_hist.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        fig.autofmt_xdate()

        fig.suptitle("SolarGuard Vision - Painel Geral de Monitoramento Fotovoltaico",
                     fontsize=15, weight="bold", color="#FFFFFF", y=0.98)

        fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        logger.info(f"Painel consolidado gerado com sucesso em: {out_path}")
        return out_path
