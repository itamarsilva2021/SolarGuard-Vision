"""
Testes unitários para os componentes GIS do SolarGuard Vision (Etapa 8).
Valida a engine de projeção fotogramétrica DJI, o gerador de mapas Folium e o exportador GeoJSON.
"""

import json
from pathlib import Path
from datetime import datetime
import pytest

from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.application.dtos.gis_dtos import GeoReferencedAnomaly
from src.infrastructure.gis.thermal_georeferencer import ThermalGeoReferencer
from src.infrastructure.gis.geojson_exporter import GeoJsonExporter
from src.infrastructure.gis.map_generator import MapGenerator


class TestThermalGeoReferencer:
    """Testes para o calculador de projeção e coordenadas no solo."""

    @pytest.fixture
    def georeferencer(self) -> ThermalGeoReferencer:
        return ThermalGeoReferencer(hfov_deg=44.0, vfov_deg=35.0)

    def test_calculate_gsd(self, georeferencer: ThermalGeoReferencer):
        # A 25 metros de altitude, HFOV=44°, VFOV=35°, sensor 640x512
        gsd_x, gsd_y = georeferencer.calculate_gsd(flight_altitude_m=25.0, image_width_px=640, image_height_px=512)

        assert gsd_x > 0.0
        assert gsd_y > 0.0
        # GSD típico para essas especificações fica em torno de 0.03 a 0.04 metros/pixel (3 a 4 cm/pixel)
        assert 0.02 <= gsd_x <= 0.06
        assert 0.02 <= gsd_y <= 0.06

    def test_project_anomaly_center_matches_drone_horizontal_location(self, georeferencer: ThermalGeoReferencer):
        drone_coord = GeoCoordinate(latitude=-9.3891, longitude=-40.5027, altitude_meters=395.0)
        # Bbox centralizada exatamente no meio da imagem normalizada (0.45 a 0.55) -> centro = (0.5, 0.5)
        center_bbox = BoundingBox(x_min=0.45, y_min=0.45, x_max=0.55, y_max=0.55, is_normalized=True)

        anomaly_coord = georeferencer.project_anomaly_coordinate(
            drone_coordinate=drone_coord,
            bbox=center_bbox,
            image_width_px=640,
            image_height_px=512,
            flight_altitude_m=25.0,
            yaw_deg=0.0,
        )

        # O centro óptico não deve sofrer desvio horizontal em relação ao nadir do drone
        assert pytest.approx(anomaly_coord.latitude, abs=1e-6) == drone_coord.latitude
        assert pytest.approx(anomaly_coord.longitude, abs=1e-6) == drone_coord.longitude
        assert anomaly_coord.altitude == 370.0  # 395m - 25m

    def test_project_anomaly_offset_with_heading(self, georeferencer: ThermalGeoReferencer):
        drone_coord = GeoCoordinate(latitude=-9.3891, longitude=-40.5027, altitude_meters=100.0)
        # Bbox deslocada para o canto superior direito (x > 0.5, y < 0.5 -> acima do centro óptico)
        offset_bbox = BoundingBox(x_min=0.7, y_min=0.1, x_max=0.9, y_max=0.3, is_normalized=True)

        # Com Yaw=0° (apontando para o Norte):
        # Deslocamento para cima na imagem = para frente = Norte (+lat)
        # Deslocamento para a direita na imagem = Leste (+lon)
        coord_north = georeferencer.project_anomaly_coordinate(
            drone_coordinate=drone_coord,
            bbox=offset_bbox,
            flight_altitude_m=30.0,
            yaw_deg=0.0,
        )

        assert coord_north.latitude > drone_coord.latitude
        assert coord_north.longitude > drone_coord.longitude


class TestGeoJsonExporter:
    """Testes para o gerador de arquivos e estruturas RFC 7946 GeoJSON."""

    @pytest.fixture
    def sample_anomalies(self) -> list[GeoReferencedAnomaly]:
        return [
            GeoReferencedAnomaly(
                anomaly_id="anom-001",
                image_id="img-001",
                anomaly_type=AnomalyType.HOTSPOT,
                severity=SeverityLevel.CRITICAL,
                coordinate=GeoCoordinate(latitude=-9.38912, longitude=-40.50271, altitude_meters=372.5),
                max_temp_celsius=74.2,
                confidence=0.95,
                delta_t_celsius=38.5,
                project_name="UFV Petrolina 1",
                inspection_title="Inspeção Semestral",
                captured_at=datetime(2026, 6, 15, 11, 30),
            ),
            GeoReferencedAnomaly(
                anomaly_id="anom-002",
                image_id="img-001",
                anomaly_type=AnomalyType.SOILING,
                severity=SeverityLevel.LOW,
                coordinate=GeoCoordinate(latitude=-9.38915, longitude=-40.50279, altitude_meters=372.4),
                max_temp_celsius=48.0,
                confidence=0.88,
                delta_t_celsius=5.2,
                project_name="UFV Petrolina 1",
                inspection_title="Inspeção Semestral",
                captured_at=datetime(2026, 6, 15, 11, 30),
            ),
        ]


    def test_export_to_dict_rfc_7946_spec(self, sample_anomalies):
        data = GeoJsonExporter.export_to_dict(sample_anomalies, "UFV Petrolina - Teste")

        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        assert data["metadata"]["total_features"] == 2
        assert data["metadata"]["severity_summary"]["critical"] == 1
        assert data["metadata"]["severity_summary"]["low"] == 1

        feat1 = data["features"][0]
        assert feat1["type"] == "Feature"
        assert feat1["id"] == "anom-001"
        assert feat1["geometry"]["type"] == "Point"
        # Coordenadas no GeoJSON são [longitude, latitude, altitude]
        assert feat1["geometry"]["coordinates"][0] == -40.50271
        assert feat1["geometry"]["coordinates"][1] == -9.38912
        assert feat1["geometry"]["coordinates"][2] == 372.50

        props = feat1["properties"]
        assert props["anomaly_type"] == "Hotspot"
        assert props["severity"] == "Crítico (Classe 3 - IEC)"
        assert props["max_temp_celsius"] == 74.2
        assert props["delta_t_celsius"] == 38.5

    def test_export_to_file(self, sample_anomalies, tmp_path):
        out_file = tmp_path / "test_export.geojson"
        res_path = GeoJsonExporter.export_to_file(sample_anomalies, out_file)

        assert res_path.exists()
        parsed = json.loads(res_path.read_text(encoding="utf-8"))
        assert parsed["type"] == "FeatureCollection"
        assert len(parsed["features"]) == 2


class TestMapGenerator:
    """Testes para o gerador de mapas interativos Folium."""

    def test_generate_map_empty_anomalies(self, tmp_path):
        generator = MapGenerator(output_dir=tmp_path)
        map_path = generator.generate_map(
            anomalies=[],
            output_filename="empty_map.html",
        )

        assert map_path.exists()
        content = map_path.read_text(encoding="utf-8")
        assert "folium" in content.lower()
        assert "SOLARGUARD VISION" in content

    def test_generate_map_with_anomalies_and_layers(self, tmp_path):
        generator = MapGenerator(output_dir=tmp_path)
        anomalies = [
            GeoReferencedAnomaly(
                anomaly_id="anom-01",
                image_id="img-01",
                anomaly_type=AnomalyType.HOTSPOT,
                severity=SeverityLevel.CRITICAL,
                coordinate=GeoCoordinate(latitude=-9.3891, longitude=-40.5027),
                max_temp_celsius=72.0,
                confidence=0.96,
                delta_t_celsius=35.0,
            ),
            GeoReferencedAnomaly(
                anomaly_id="anom-02",
                image_id="img-01",
                anomaly_type=AnomalyType.DISCONNECTED_MODULE,
                severity=SeverityLevel.MEDIUM,
                coordinate=GeoCoordinate(latitude=-9.3892, longitude=-40.5028),
                max_temp_celsius=58.0,
                confidence=0.91,
                delta_t_celsius=14.0,
            ),
        ]

        map_path = generator.generate_map(
            anomalies=anomalies,
            output_filename="solar_faults_map.html",
            map_title="UFV Sol do Sertão",
            include_heatmap=True,
            include_clusters=True,
        )

        assert map_path.exists()
        html_code = map_path.read_text(encoding="utf-8")

        # Verifica inclusão de componentes essenciais
        assert "Esri World Imagery" in html_code
        assert "UFV Sol do Sertão" in html_code
        assert "72.0" in html_code or "72" in html_code
        assert "Hotspot" in html_code
