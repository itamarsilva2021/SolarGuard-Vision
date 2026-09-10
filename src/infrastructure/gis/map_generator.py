"""
Gerador de Mapas Interativos com Folium para Visualização Georreferenciada de Falhas em Usinas Solares.
Suporta imagens de satélite de alta resolução (Esri), OpenStreetMap, mapas de calor (HeatMap),
agrupamento inteligente de defeitos (MarkerCluster) e popups analíticos ricos.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union, TYPE_CHECKING
import html

import folium
from folium import plugins

if TYPE_CHECKING:
    from src.application.dtos.gis_dtos import GeoReferencedAnomaly
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("MapGenerator")


class MapGenerator:
    """
    Gerador de mapas interativos Web/HTML para inspeções fotovoltaicas georreferenciadas.
    """

    DEFAULT_LATITUDE = -9.3891   # Vale do São Francisco / Polo Solar de Petrolina - PE
    DEFAULT_LONGITUDE = -40.5027
    DEFAULT_ZOOM = 18

    def __init__(self, output_dir: Optional[Union[Path, str]] = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else settings.reports_dir / "maps"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_map(
        self,
        anomalies: List[GeoReferencedAnomaly],
        output_filename: str = "mapa_inspecao_termica.html",
        map_title: str = "SolarGuard Vision - Mapa Georreferenciado de Falhas Fotovoltaicas",
        center_coord: Optional[GeoCoordinate] = None,
        include_heatmap: bool = True,
        include_clusters: bool = True,
    ) -> Path:
        """
        Cria um mapa interativo completo com Folium e salva como arquivo HTML.
        
        :param anomalies: Lista de anomalias com coordenadas GPS.
        :param output_filename: Nome do arquivo HTML de saída.
        :param map_title: Título exibido no cabeçalho do mapa.
        :param center_coord: Coordenada central forçada (opcional).
        :param include_heatmap: Se True, adiciona camada com mapa de calor térmico.
        :param include_clusters: Se True, agrupa marcadores em clusters por proximidade.
        :return: Path do arquivo HTML gerado.
        """
        out_path = self.output_dir / output_filename

        # Calcular centro do mapa
        if center_coord:
            center_lat = center_coord.latitude
            center_lon = center_coord.longitude
        elif anomalies:
            center_lat = sum(a.coordinate.latitude for a in anomalies) / len(anomalies)
            center_lon = sum(a.coordinate.longitude for a in anomalies) / len(anomalies)
        else:
            center_lat = self.DEFAULT_LATITUDE
            center_lon = self.DEFAULT_LONGITUDE

        # Inicializar mapa Folium
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=self.DEFAULT_ZOOM,
            control_scale=True,
            tiles=None,  # Configurado manualmente abaixo para multi-camadas
        )

        # -------------------------------------------------------------
        # 1. Camadas Base (Tilesets)
        # -------------------------------------------------------------
        # Camada 1: Satélite de Alta Resolução Esri (Ideal para usinas fotovoltaicas)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="🛰️ Imagem de Satélite (Esri)",
            max_zoom=20,
            show=True,
        ).add_to(m)

        # Camada 2: OpenStreetMap (Vetorial Padrão)
        folium.TileLayer(
            tiles="OpenStreetMap",
            name="🗺️ Mapa de Ruas (OpenStreetMap)",
            max_zoom=19,
            show=False,
        ).add_to(m)

        # Camada 3: Relevo e Topografia (OpenTopoMap)
        folium.TileLayer(
            tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            attr="OpenTopoMap",
            name="🏔️ Topografia e Relevo (OpenTopoMap)",
            max_zoom=17,
            show=False,
        ).add_to(m)


        # -------------------------------------------------------------
        # 2. Camada de Marcadores de Falhas
        # -------------------------------------------------------------
        if include_clusters:
            marker_group = plugins.MarkerCluster(
                name="📍 Agrupamento de Falhas (Cluster)",
                overlay=True,
                control=True,
                show=True,
                options={"maxClusterRadius": 35, "disableClusteringAtZoom": 19},
            ).add_to(m)
        else:
            marker_group = folium.FeatureGroup(name="📍 Falhas Térmicas", overlay=True, control=True).add_to(m)

        # Inserir cada defeito no mapa
        for anom in anomalies:
            lat = anom.coordinate.latitude
            lon = anom.coordinate.longitude

            popup_html = self._create_popup_html(anom)
            tooltip_text = (
                f"{anom.anomaly_type_name} | "
                f"Tmax: {anom.max_temp_celsius:.1f}°C | "
                f"ΔT: {anom.delta_t_celsius or 0.0:.1f}°C | "
                f"{anom.severity_display_name}"
            )

            # Escolher cor e ícone baseados na severidade normativa IEC
            icon_color, icon_name = self._get_marker_icon_props(anom.severity)

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=380),
                tooltip=tooltip_text,
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
            ).add_to(marker_group)

            # Adicionar também círculo pulsante de destaque térmico
            folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color=anom.severity_hex_color,
                fill=True,
                fill_color=anom.severity_hex_color,
                fill_opacity=0.6,
                weight=2,
            ).add_to(marker_group)

        # -------------------------------------------------------------
        # 3. Camada de Mapa de Calor (HeatMap) Opcional
        # -------------------------------------------------------------
        if include_heatmap and anomalies:
            # Pondera o calor com base na temperatura máxima medida
            heat_data = [
                [a.coordinate.latitude, a.coordinate.longitude, max(a.max_temp_celsius - 25.0, 1.0)]
                for a in anomalies
            ]
            heatmap_layer = plugins.HeatMap(
                heat_data,
                name="🔥 Mapa de Calor de Temperatura (HeatMap)",
                min_opacity=0.35,
                radius=22,
                blur=15,
                max_zoom=18,
                show=False,  # Opcional, ativável no seletor de camadas
            )
            heatmap_layer.add_to(m)

        # -------------------------------------------------------------
        # 4. Plugins Adicionais de Navegação e Medição
        # -------------------------------------------------------------
        # Ferramenta de medição métrica no mapa (distâncias entre módulos e inversores)
        plugins.MeasureControl(
            position="topleft",
            primary_length_unit="meters",
            secondary_length_unit="kilometers",
            primary_area_unit="sqmeters",
        ).add_to(m)

        # Botão de tela cheia
        plugins.Fullscreen(position="topleft").add_to(m)

        # MiniMap para orientação rápida no canto inferior
        plugins.MiniMap(toggle_display=True, position="bottomright").add_to(m)

        # Seletor de camadas
        folium.LayerControl(position="topright", collapsed=False).add_to(m)

        # Título flutuante elegante
        self._add_title_box(m, map_title, len(anomalies))

        # Salvar arquivo HTML
        m.save(str(out_path))
        logger.info(f"Mapa interativo Folium salvo com sucesso em: {out_path} ({len(anomalies)} falhas plotadas)")
        return out_path

    def _get_marker_icon_props(self, severity: SeverityLevel) -> tuple[str, str]:
        """Retorna a cor do marcador Folium e o nome do ícone FontAwesome."""
        if severity == SeverityLevel.CRITICAL:
            return "red", "exclamation-triangle"
        elif severity == SeverityLevel.MEDIUM:
            return "orange", "fire"
        elif severity == SeverityLevel.LOW:
            return "beige", "info-circle"
        else:
            return "green", "check-circle"

    def _create_popup_html(self, anom: GeoReferencedAnomaly) -> str:
        """Gera conteúdo HTML estilizado para o popup da falha térmica."""
        sev_color = anom.severity_hex_color
        delta_t_str = f"+{anom.delta_t_celsius:.1f}°C" if anom.delta_t_celsius is not None else "N/A"
        date_str = anom.captured_at.strftime("%d/%m/%Y %H:%M:%S") if anom.captured_at else "Data não registrada"

        html_content = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; min-width: 260px; color: #1E293B; line-height: 1.4;">
            <div style="background-color: {sev_color}; color: white; padding: 6px 12px; border-radius: 6px 6px 0 0; font-weight: bold; font-size: 13px; display: flex; justify-content: space-between; align-items: center;">
                <span>{html.escape(anom.anomaly_type_name)}</span>
                <span style="font-size: 11px; background: rgba(0,0,0,0.25); padding: 2px 6px; border-radius: 4px;">{html.escape(anom.severity_display_name)}</span>
            </div>
            <div style="padding: 10px; border: 1px solid #E2E8F0; border-top: none; border-radius: 0 0 6px 6px; background: #F8FAFC;">
                <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 3px 0; color: #64748B;">Temperatura Máxima:</td>
                        <td style="padding: 3px 0; font-weight: bold; color: #DC2626; text-align: right;">{anom.max_temp_celsius:.1f}°C</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748B;">Gradiente (ΔT IEC):</td>
                        <td style="padding: 3px 0; font-weight: bold; color: {sev_color}; text-align: right;">{delta_t_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748B;">Confiança IA:</td>
                        <td style="padding: 3px 0; font-weight: bold; text-align: right;">{anom.confidence * 100:.1f}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748B;">Latitude:</td>
                        <td style="padding: 3px 0; font-family: monospace; text-align: right;">{anom.coordinate.latitude:.6f}°</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748B;">Longitude:</td>
                        <td style="padding: 3px 0; font-family: monospace; text-align: right;">{anom.coordinate.longitude:.6f}°</td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0; color: #64748B;">Data do Voo:</td>
                        <td style="padding: 3px 0; font-size: 11px; text-align: right;">{date_str}</td>
                    </tr>
                </table>
        """
        if anom.notes:
            html_content += f"""
                <div style="margin-top: 8px; padding-top: 6px; border-top: 1px dashed #CBD5E1; font-size: 11px; color: #475569;">
                    <b>Obs:</b> {html.escape(anom.notes)}
                </div>
            """

        html_content += """
            </div>
        </div>
        """
        return html_content

    def _add_title_box(self, folium_map: folium.Map, title: str, fault_count: int) -> None:
        """Insere caixa estilizada com o título do sistema no topo do mapa."""
        title_html = f"""
        <div style="position: fixed; 
                    top: 12px; left: 60px; width: auto; max-width: 480px; height: auto;
                    background-color: rgba(26, 29, 36, 0.90);
                    color: #FFFFFF;
                    padding: 8px 16px;
                    border: 1px solid #3A4153;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.35);
                    font-family: 'Segoe UI', Arial, sans-serif;
                    z-index: 9999;">
            <div style="font-size: 13px; font-weight: bold; color: #F1C40F; letter-spacing: 0.5px;">☀️ SOLARGUARD VISION</div>
            <div style="font-size: 12px; font-weight: 600; color: #E0E6ED; margin-top: 2px;">{html.escape(title)}</div>
            <div style="font-size: 11px; color: #94A3B8; margin-top: 2px;">
                Total de Falhas Detectadas: <b style="color: #E74C3C;">{fault_count}</b>
            </div>
        </div>
        """
        folium_map.get_root().html.add_child(folium.Element(title_html))
