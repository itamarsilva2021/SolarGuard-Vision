"""
Exportador de Anomalias e Inspeções Térmicas para o Formato Padronizado GeoJSON (RFC 7946).
Permite integração direta com softwares GIS profissionais (QGIS, ArcGIS, Google Earth).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.dtos.gis_dtos import GeoReferencedAnomaly
from src.core.logger import get_logger

logger = get_logger("GeoJsonExporter")


class GeoJsonExporter:
    """
    Exportador de anomalias térmicas fotovoltaicas para GeoJSON padrão RFC 7946.
    """

    @classmethod
    def export_to_dict(
        cls,
        anomalies: List[GeoReferencedAnomaly],
        collection_name: str = "SolarGuard Vision - Inspeção Termográfica Fotovoltaica",
    ) -> Dict[str, Any]:
        """
        Converte uma lista de anomalias georreferenciadas em um dicionário FeatureCollection GeoJSON.
        
        :param anomalies: Lista de anomalias georreferenciadas.
        :param collection_name: Nome do conjunto de dados ou projeto.
        :return: Dicionário formatado em conformidade com RFC 7946.
        """
        features = []
        severity_counts = {"critical": 0, "medium": 0, "low": 0, "informational": 0}

        for anom in anomalies:
            # Padrão GeoJSON: [longitude, latitude] ou [longitude, latitude, altitude]
            coord = anom.coordinate
            coordinates = [coord.longitude, coord.latitude]
            if coord.altitude is not None:
                coordinates.append(round(coord.altitude, 2))

            sev_code = anom.severity.value
            if sev_code in severity_counts:
                severity_counts[sev_code] += 1

            feature = {
                "type": "Feature",
                "id": anom.anomaly_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": coordinates,
                },
                "properties": {
                    "anomaly_id": anom.anomaly_id,
                    "image_id": anom.image_id,
                    "anomaly_type": anom.anomaly_type_name,
                    "anomaly_type_code": anom.anomaly_type.value,
                    "severity": anom.severity_display_name,
                    "severity_code": anom.severity.value,
                    "severity_color_hex": anom.severity_hex_color,
                    "max_temp_celsius": round(anom.max_temp_celsius, 2),
                    "delta_t_celsius": round(anom.delta_t_celsius, 2) if anom.delta_t_celsius is not None else None,
                    "min_temp_celsius": round(anom.min_temp_celsius, 2) if anom.min_temp_celsius is not None else None,
                    "avg_temp_celsius": round(anom.avg_temp_celsius, 2) if anom.avg_temp_celsius is not None else None,
                    "confidence": round(anom.confidence, 4),
                    "project_id": anom.project_id,
                    "project_name": anom.project_name,
                    "inspection_id": anom.inspection_id,
                    "inspection_title": anom.inspection_title,
                    "captured_at": anom.captured_at.isoformat() if anom.captured_at else None,
                    "crop_path": anom.crop_path,
                    "notes": anom.notes,
                },
            }
            features.append(feature)

        geojson_doc = {
            "type": "FeatureCollection",
            "name": collection_name,
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:OGC:1.3:CRS84",
                },
            },
            "metadata": {
                "generator": "SolarGuard Vision - Solar Thermal Vision & AI",
                "spec": "RFC 7946",
                "generated_at": datetime.now().isoformat(),
                "total_features": len(features),
                "severity_summary": severity_counts,
            },
            "features": features,
        }

        return geojson_doc

    @classmethod
    def export_to_json_str(
        cls,
        anomalies: List[GeoReferencedAnomaly],
        collection_name: str = "SolarGuard Vision - Inspeção Termográfica",
        indent: int = 2,
    ) -> str:
        """Serializa anomalias georreferenciadas em string formatada JSON."""
        data = cls.export_to_dict(anomalies, collection_name=collection_name)
        return json.dumps(data, indent=indent, ensure_ascii=False)

    @classmethod
    def export_to_file(
        cls,
        anomalies: List[GeoReferencedAnomaly],
        output_path: Union[str, Path],
        collection_name: str = "SolarGuard Vision - Inspeção Termográfica",
    ) -> Path:
        """
        Salva as anomalias georreferenciadas em um arquivo `.geojson`.
        
        :param anomalies: Lista de anomalias com coordenadas GPS.
        :param output_path: Caminho de destino do arquivo.
        :param collection_name: Nome do conjunto de dados.
        :return: Path do arquivo gerado.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        json_str = cls.export_to_json_str(anomalies, collection_name=collection_name)
        path.write_text(json_str, encoding="utf-8")

        logger.info(f"Arquivo GeoJSON gerado com sucesso: {path} ({len(anomalies)} falhas)")
        return path
