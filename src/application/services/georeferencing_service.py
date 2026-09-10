"""
Serviço de Aplicação para Georreferenciamento de Falhas, Geração de Mapas Folium e Exportação GeoJSON.
Orquestra repositórios, motor de projeção fotogramétrica e geradores cartográficos.
"""

from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from src.core.result import Result, Success, Failure
from src.core.config import settings
from src.core.logger import get_logger
from src.domain.interfaces.repositories import (
    IProjectRepository,
    IInspectionRepository,
    IThermalImageRepository,
    IThermalAnomalyRepository,
)
from src.domain.entities.thermal_image import ThermalImage
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.domain.enums.severity_level import SeverityLevel
from src.application.dtos.gis_dtos import GeoReferencedAnomaly, GeoInspectionResult
from src.infrastructure.gis.thermal_georeferencer import ThermalGeoReferencer
from src.infrastructure.gis.map_generator import MapGenerator
from src.infrastructure.gis.geojson_exporter import GeoJsonExporter

logger = get_logger("GeoReferencingService")


class GeoReferencingService:
    """
    Serviço que consolida a inteligência espacial da usina fotovoltaica:
    extrai GPS DJI, projeta coordenadas das falhas, gera mapas Folium e exporta GeoJSON.
    """

    def __init__(
        self,
        project_repository: IProjectRepository,
        inspection_repository: IInspectionRepository,
        thermal_image_repository: IThermalImageRepository,
        thermal_anomaly_repository: IThermalAnomalyRepository,
        georeferencer: Optional[ThermalGeoReferencer] = None,
        map_generator: Optional[MapGenerator] = None,
        geojson_exporter: Optional[GeoJsonExporter] = None,
    ) -> None:
        self.project_repo = project_repository
        self.inspection_repo = inspection_repository
        self.image_repo = thermal_image_repository
        self.anomaly_repo = thermal_anomaly_repository
        self.georeferencer = georeferencer or ThermalGeoReferencer()
        self.map_generator = map_generator or MapGenerator()
        self.geojson_exporter = geojson_exporter or GeoJsonExporter()

    def process_inspection_gis(
        self,
        inspection_id: str,
        generate_map: bool = True,
        export_geojson: bool = True,
    ) -> Result[GeoInspectionResult, str]:
        """
        Georreferencia todas as falhas de uma inspeção, gerando mapa HTML e arquivo GeoJSON.
        
        :param inspection_id: Identificador único da inspeção.
        :param generate_map: Se True, renderiza mapa Folium interativo.
        :param export_geojson: Se True, exporta arquivo GeoJSON padronizado RFC 7946.
        :return: Result contendo GeoInspectionResult.
        """
        try:
            inspection = self.inspection_repo.get_by_id(inspection_id)
            if not inspection:
                return Failure(f"Inspeção não encontrada: {inspection_id}")

            project = self.project_repo.get_by_id(inspection.project_id) if inspection.project_id else None
            project_name = project.name if project else "Usina Solar Fotovoltaica"

            # Obter todas as imagens da inspeção
            images = self.image_repo.list_by_inspection(inspection_id)
            if not images:
                logger.warning(f"Nenhuma imagem térmica cadastrada para a inspeção: {inspection_id}")

            # Mapear imagens por ID para acesso rápido
            images_by_id: Dict[str, ThermalImage] = {img.id: img for img in images}

            geo_anomalies: List[GeoReferencedAnomaly] = []

            # Percorrer imagens e suas anomalias
            for img in images:
                anomalies = self.anomaly_repo.list_by_image(img.id)
                for anom in anomalies:
                    geo_anom = self._georeference_single_anomaly(
                        anomaly=anom,
                        image=img,
                        project_id=project.id if project else None,
                        project_name=project_name,
                        inspection_id=inspection.id,
                        inspection_title=inspection.title,
                    )
                    if geo_anom:
                        geo_anomalies.append(geo_anom)


            # Contabilizar severidades
            critical_cnt = sum(1 for a in geo_anomalies if a.severity == SeverityLevel.CRITICAL)
            medium_cnt = sum(1 for a in geo_anomalies if a.severity == SeverityLevel.MEDIUM)
            low_cnt = sum(1 for a in geo_anomalies if a.severity == SeverityLevel.LOW)

            # Calcular centro geográfico médio
            center_coord = None
            if geo_anomalies:
                avg_lat = sum(a.coordinate.latitude for a in geo_anomalies) / len(geo_anomalies)
                avg_lon = sum(a.coordinate.longitude for a in geo_anomalies) / len(geo_anomalies)
                center_coord = GeoCoordinate(latitude=avg_lat, longitude=avg_lon)

            # Gerar Mapa Folium
            map_path: Optional[Path] = None
            if generate_map:
                map_filename = f"mapa_inspecao_{inspection_id[:8]}.html"
                map_title = f"{inspection.title} - {project_name}"
                map_path = self.map_generator.generate_map(
                    anomalies=geo_anomalies,
                    output_filename=map_filename,
                    map_title=map_title,
                    center_coord=center_coord,
                )

            # Exportar GeoJSON
            geojson_path: Optional[Path] = None
            if export_geojson:
                geojson_dir = settings.reports_dir / "geojson"
                geojson_filename = f"inspecao_{inspection_id[:8]}.geojson"
                geojson_path = self.geojson_exporter.export_to_file(
                    anomalies=geo_anomalies,
                    output_path=geojson_dir / geojson_filename,
                    collection_name=f"Inspeção: {inspection.title} - {project_name}",
                )

            result_dto = GeoInspectionResult(
                total_anomalies=len(geo_anomalies),
                anomalies=geo_anomalies,
                map_html_path=map_path,
                geojson_path=geojson_path,
                center_coordinate=center_coord,
                critical_count=critical_cnt,
                medium_count=medium_cnt,
                low_count=low_cnt,
            )

            logger.info(
                f"Georreferenciamento concluído para inspeção {inspection_id}: "
                f"{len(geo_anomalies)} falhas plotadas."
            )
            return Success(result_dto)

        except Exception as e:
            logger.error(f"Erro no processamento GIS da inspeção {inspection_id}: {e}", exc_info=True)
            return Failure(f"Falha no processamento GIS: {str(e)}")

    def process_project_gis(
        self,
        project_id: str,
        generate_map: bool = True,
        export_geojson: bool = True,
    ) -> Result[GeoInspectionResult, str]:
        """
        Georreferencia todas as falhas de todas as inspeções de uma usina fotovoltaica.
        """
        try:
            project = self.project_repo.get_by_id(project_id)
            if not project:
                return Failure(f"Projeto/Usina não encontrada: {project_id}")

            inspections = self.inspection_repo.list_by_project(project_id)
            all_geo_anomalies: List[GeoReferencedAnomaly] = []

            for insp in inspections:
                images = self.image_repo.list_by_inspection(insp.id)
                for img in images:
                    anomalies = self.anomaly_repo.list_by_image(img.id)
                    for anom in anomalies:

                        geo_anom = self._georeference_single_anomaly(
                            anomaly=anom,
                            image=img,
                            project_id=project.id,
                            project_name=project.name,
                            inspection_id=insp.id,
                            inspection_title=insp.title,
                        )
                        if geo_anom:
                            all_geo_anomalies.append(geo_anom)

            critical_cnt = sum(1 for a in all_geo_anomalies if a.severity == SeverityLevel.CRITICAL)
            medium_cnt = sum(1 for a in all_geo_anomalies if a.severity == SeverityLevel.MEDIUM)
            low_cnt = sum(1 for a in all_geo_anomalies if a.severity == SeverityLevel.LOW)

            center_coord = None
            if all_geo_anomalies:
                avg_lat = sum(a.coordinate.latitude for a in all_geo_anomalies) / len(all_geo_anomalies)
                avg_lon = sum(a.coordinate.longitude for a in all_geo_anomalies) / len(all_geo_anomalies)
                center_coord = GeoCoordinate(latitude=avg_lat, longitude=avg_lon)

            map_path: Optional[Path] = None
            if generate_map:
                map_filename = f"mapa_usina_{project_id[:8]}.html"
                map_title = f"Usina: {project.name} - Histórico Geral de Falhas"
                map_path = self.map_generator.generate_map(
                    anomalies=all_geo_anomalies,
                    output_filename=map_filename,
                    map_title=map_title,
                    center_coord=center_coord,
                )

            geojson_path: Optional[Path] = None
            if export_geojson:
                geojson_dir = settings.reports_dir / "geojson"
                geojson_filename = f"usina_{project_id[:8]}.geojson"
                geojson_path = self.geojson_exporter.export_to_file(
                    anomalies=all_geo_anomalies,
                    output_path=geojson_dir / geojson_filename,
                    collection_name=f"Usina: {project.name} - Mapa Consolidado",
                )

            return Success(GeoInspectionResult(
                total_anomalies=len(all_geo_anomalies),
                anomalies=all_geo_anomalies,
                map_html_path=map_path,
                geojson_path=geojson_path,
                center_coordinate=center_coord,
                critical_count=critical_cnt,
                medium_count=medium_cnt,
                low_count=low_cnt,
            ))

        except Exception as e:
            logger.error(f"Erro no processamento GIS da usina {project_id}: {e}", exc_info=True)
            return Failure(f"Falha no processamento GIS da usina: {str(e)}")

    def _georeference_single_anomaly(
        self,
        anomaly: ThermalAnomaly,
        image: ThermalImage,
        project_id: Optional[str],
        project_name: Optional[str],
        inspection_id: Optional[str],
        inspection_title: Optional[str],
    ) -> Optional[GeoReferencedAnomaly]:
        """Calcula a coordenada geográfica exata de uma única anomalia térmica."""
        # Se a imagem possui coordenadas de voo registradas pelo drone DJI
        drone_coord = image.coordinate
        if not drone_coord:
            # Se não houver GPS registrado, usamos coordenada padrão de segurança
            drone_coord = GeoCoordinate(
                latitude=MapGenerator.DEFAULT_LATITUDE,
                longitude=MapGenerator.DEFAULT_LONGITUDE,
                altitude_meters=image.flight_altitude_meters or 25.0,
            )

        # Projetar coordenada no solo a partir da bounding box da falha
        anomaly_coord = self.georeferencer.project_anomaly_coordinate(
            drone_coordinate=drone_coord,
            bbox=anomaly.bbox,
            image_width_px=image.width,
            image_height_px=image.height,
            flight_altitude_m=image.flight_altitude_meters,
            yaw_deg=image.gimbal_yaw_degrees or 0.0,
        )

        delta_t_val = anomaly.delta_t.delta_celsius if anomaly.delta_t else None

        return GeoReferencedAnomaly(
            anomaly_id=anomaly.id,
            image_id=image.id,
            anomaly_type=anomaly.anomaly_type,
            severity=anomaly.severity,
            coordinate=anomaly_coord,
            max_temp_celsius=anomaly.max_temp_celsius,
            confidence=anomaly.confidence,
            delta_t_celsius=delta_t_val,
            min_temp_celsius=anomaly.min_temp_celsius,
            avg_temp_celsius=anomaly.avg_temp_celsius,
            project_id=project_id,
            project_name=project_name,
            inspection_id=inspection_id,
            inspection_title=inspection_title,
            captured_at=image.captured_at,
            crop_path=anomaly.crop_path,
            notes=anomaly.notes,
        )
