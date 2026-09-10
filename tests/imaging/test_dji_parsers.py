"""
Suíte de testes de integração e unitários para parsers, analisadores RTK e validadores
especializados do drone DJI Matrice 4T (Etapa 12B).
"""

import pytest
import numpy as np
from pathlib import Path
from PIL import Image

from src.infrastructure.imaging.dji_xmp_parser import DjiXmpParser
from src.infrastructure.imaging.dji_rtk_parser import DjiRtkParser
from src.infrastructure.imaging.dji_flight_parser import DjiFlightParser
from src.infrastructure.imaging.dji_rjpeg_parser import DjiRjpegParser
from src.infrastructure.imaging.dji_validators import DjiImageValidator
from src.infrastructure.imaging.dji_metadata_parser import DjiMetadataParser
from src.application.dtos.dji_metadata_dto import (
    RtkStatus,
    ThermalGainMode,
    DjiParsedMetadataDTO,
)
from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.domain.value_objects.thermal_matrix_meta import ThermalMatrixMeta


# Bloco XMP simulado no padrão do DJI Matrice 4T (mistura de atributos e nós XML)
MOCK_DJI_XMP_XML = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:drone-dji="http://www.dji.com/drone-dji/1.0/"
      drone-dji:GimbalPitchDegree="-89.5"
      drone-dji:GimbalRollDegree="0.2"
      drone-dji:GimbalYawDegree="134.8"
      drone-dji:FlightPitchDegree="2.1"
      drone-dji:FlightRollDegree="-1.3"
      drone-dji:FlightYawDegree="135.0"
      drone-dji:RelativeAltitude="24.8"
      drone-dji:AbsoluteAltitude="745.2"
      drone-dji:RtkAltitude="745.25"
      drone-dji:RtkFlag="50"
      drone-dji:RtkStdLat="0.015"
      drone-dji:RtkStdLon="0.018"
      drone-dji:RtkStdHgt="0.024"
      drone-dji:RtkDiffAge="1.2"
      drone-dji:ThermalGainMode="HighGain"
      drone-dji:Emissivity="0.92"
      drone-dji:ReflectedTemperature="18.5"
      drone-dji:Distance="24.5"
      drone-dji:RelativeHumidity="55.0"
      drone-dji:Model="Matrice 4T"
      drone-dji:DroneSerialNumber="1581F4DT001234"
      drone-dji:CameraSerialNumber="4C8AH005678"
      drone-dji:CameraType="Thermal">
      <drone-dji:CalibratedFocalLength>1145.6</drone-dji:CalibratedFocalLength>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


class TestDjiXmpParser:
    """Testes para o parser avançado de XMP."""

    def test_parse_xmp_string_attributes_and_elements(self):
        parsed = DjiXmpParser.parse_xmp_string(MOCK_DJI_XMP_XML)

        # Gimbal
        assert parsed.get("GimbalPitchDegree") == pytest.approx(-89.5)
        assert parsed.get("GimbalYawDegree") == pytest.approx(134.8)

        # Drone
        assert parsed.get("FlightPitchDegree") == pytest.approx(2.1)
        assert parsed.get("FlightYawDegree") == pytest.approx(135.0)

        # Altitudes
        assert parsed.get("RelativeAltitude") == pytest.approx(24.8)
        assert parsed.get("AbsoluteAltitude") == pytest.approx(745.2)
        assert parsed.get("RtkAltitude") == pytest.approx(745.25)

        # RTK
        assert parsed.get("RtkFlag") == 50
        assert parsed.get("RtkStdLat") == pytest.approx(0.015)
        assert parsed.get("RtkStdLon") == pytest.approx(0.018)

        # Radiometria
        assert parsed.get("ThermalGainMode") == "HighGain"
        assert parsed.get("Emissivity") == pytest.approx(0.92)
        assert parsed.get("ReflectedTemperature") == pytest.approx(18.5)
        assert parsed.get("RelativeHumidity") == pytest.approx(55.0)

        # Hardware & Óptica (extraído via nó XML)
        assert parsed.get("Model") == "Matrice 4T"
        assert parsed.get("CameraType") == "Thermal"
        assert parsed.get("CalibratedFocalLength") == pytest.approx(1145.6)

    def test_parse_malformed_or_empty_xmp(self):
        result = DjiXmpParser.parse_xmp_string("not an xml text")
        assert isinstance(result, dict)
        assert len(result) == 0


class TestDjiRtkParser:
    """Testes para classificação e cálculo de acurácia RTK."""

    def test_parse_rtk_fixed_precision(self):
        xmp_data = {
            "RtkFlag": 50,
            "RtkStdLat": 0.012,
            "RtkStdLon": 0.016,
            "RtkStdHgt": 0.025,
            "RtkDiffAge": 1.0,
        }
        rtk_dto = DjiRtkParser.parse_rtk_data(xmp_data)

        assert rtk_dto.status == RtkStatus.FIXED
        assert rtk_dto.is_precise is True
        assert rtk_dto.flag == 50

        # H_acc = sqrt(0.012^2 + 0.016^2) = sqrt(0.000144 + 0.000256) = sqrt(0.000400) = 0.020 m (2 cm)
        assert rtk_dto.horizontal_accuracy_meters == pytest.approx(0.020, abs=1e-3)
        assert rtk_dto.vertical_accuracy_meters == pytest.approx(0.025)

        suitable, reason = DjiRtkParser.is_suitable_for_photogrammetry(rtk_dto)
        assert suitable is True
        assert "centimétrica" in reason.lower() or "rtk fixed" in reason.lower()

    def test_parse_rtk_float(self):
        xmp_data = {"RtkFlag": 16, "RtkStdLat": 0.45, "RtkStdLon": 0.55}
        rtk_dto = DjiRtkParser.parse_rtk_data(xmp_data)

        assert rtk_dto.status == RtkStatus.FLOAT
        assert rtk_dto.is_precise is False
        suitable, _ = DjiRtkParser.is_suitable_for_photogrammetry(rtk_dto)
        assert suitable is False

    def test_parse_no_rtk(self):
        xmp_data = {"RtkFlag": 0}
        rtk_dto = DjiRtkParser.parse_rtk_data(xmp_data)

        assert rtk_dto.status == RtkStatus.NONE
        assert rtk_dto.is_precise is False
        assert rtk_dto.horizontal_accuracy_meters is None
        suitable, _ = DjiRtkParser.is_suitable_for_photogrammetry(rtk_dto)
        assert suitable is False


class TestDjiFlightParser:
    """Testes para orientação espacial do voo e altitudes."""

    def test_parse_orientation_and_nadir(self):
        xmp_data = {
            "GimbalPitchDegree": -88.0,
            "GimbalRollDegree": 0.0,
            "GimbalYawDegree": 180.0,
            "FlightPitchDegree": 2.5,
            "FlightRollDegree": -1.0,
            "FlightYawDegree": 182.0,
        }
        orientation = DjiFlightParser.parse_orientation(xmp_data)

        assert orientation.gimbal_pitch == pytest.approx(-88.0)
        assert orientation.gimbal_yaw == pytest.approx(180.0)
        assert orientation.flight_pitch == pytest.approx(2.5)

        # -88° está a 2° do nadir (-90°), dentro da tolerância de 15°
        assert DjiFlightParser.is_nadir_angle(orientation) is True

    def test_oblique_angle_detection(self):
        xmp_data = {"GimbalPitchDegree": -45.0}  # Ângulo oblíquo
        orientation = DjiFlightParser.parse_orientation(xmp_data)
        assert DjiFlightParser.is_nadir_angle(orientation) is False

    def test_parse_altitudes_hierarchy(self):
        # 1. Com RtkAltitude prioritário
        xmp_data = {"RelativeAltitude": 25.0, "AbsoluteAltitude": 700.0, "RtkAltitude": 700.2}
        rel, abs_alt = DjiFlightParser.parse_altitudes(xmp_data, exif_gps_alt=699.0)
        assert rel == pytest.approx(25.0)
        assert abs_alt == pytest.approx(700.2)

        # 2. Sem RtkAltitude, com AbsoluteAltitude
        xmp_data2 = {"RelativeAltitude": 30.0, "AbsoluteAltitude": 550.0}
        rel2, abs_alt2 = DjiFlightParser.parse_altitudes(xmp_data2, exif_gps_alt=548.0)
        assert rel2 == pytest.approx(30.0)
        assert abs_alt2 == pytest.approx(550.0)

        # 3. Apenas EXIF como fallback
        rel3, abs_alt3 = DjiFlightParser.parse_altitudes({}, exif_gps_alt=120.0)
        assert rel3 is None
        assert abs_alt3 == pytest.approx(120.0)


class TestDjiValidators:
    """Testes para integridade e consistência física."""

    def test_validate_nonexistent_file(self, tmp_path):
        bad_path = tmp_path / "non_existent.jpg"
        valid, errors = DjiImageValidator.validate_file_integrity(bad_path)
        assert valid is False
        assert any("não existe" in err.lower() for err in errors)

    def test_validate_truncated_jpeg(self, tmp_path):
        truncated_file = tmp_path / "corrupt.jpg"
        # Grava apenas o cabeçalho SOI sem terminador EOI e tamanho pequeno
        truncated_file.write_bytes(b"\xff\xd8" + b"\x00" * 2000)

        valid, errors = DjiImageValidator.validate_file_integrity(truncated_file)
        assert valid is False
        assert any("terminador eoi" in err.lower() for err in errors)

    def test_validate_healthy_jpeg(self, tmp_path):
        healthy_file = tmp_path / "healthy.jpg"
        img = Image.new("RGB", (640, 512), color=(100, 100, 100))
        img.save(healthy_file, format="JPEG")

        valid, errors = DjiImageValidator.validate_file_integrity(healthy_file)
        assert valid is True
        assert len(errors) == 0

    def test_validate_camera_channel_rejection(self, tmp_path):
        # Arquivo terminado em _W.JPG (Grande angular / Wide RGB)
        wide_file = tmp_path / "DJI_0001_W.JPG"
        is_thermal, warnings = DjiImageValidator.validate_thermal_channel(wide_file)
        assert is_thermal is False
        assert any("grande angular" in w.lower() for w in warnings)

        # Arquivo terminado em _T.JPG (Térmico)
        thermal_file = tmp_path / "DJI_0001_T.JPG"
        is_thermal, warnings = DjiImageValidator.validate_thermal_channel(thermal_file)
        assert is_thermal is True
        assert len(warnings) == 0

    def test_validate_physical_telemetry(self):
        # Valores válidos
        valid, warnings = DjiImageValidator.validate_physical_telemetry(
            latitude=-23.5505,
            longitude=-46.6333,
            altitude_rel=30.0,
            emissivity=0.95,
        )
        assert valid is True
        assert len(warnings) == 0

        # Valores absurdos
        valid2, warnings2 = DjiImageValidator.validate_physical_telemetry(
            latitude=150.0,  # Latitude impossível (> 90)
            longitude=-46.6,
            altitude_rel=0.1,  # Abaixo do chão
            emissivity=1.5,   # Emissividade impossível (> 1.0)
        )
        assert valid2 is False
        assert len(warnings2) == 3


class TestDjiRjpegParser:
    """Testes para analisador de estrutura R-JPEG."""

    def test_rjpeg_signature_detection(self, tmp_path):
        img_file = tmp_path / "test_rjpeg.jpg"
        # Cria JPEG com o bloco XMP mockado contendo assinatura DJI
        img = Image.new("RGB", (64, 64))
        img.save(img_file, format="JPEG")

        # Injeta bytes com assinatura DJI
        content = img_file.read_bytes()
        modified = content[:-2] + MOCK_DJI_XMP_XML.encode("utf-8") + content[-2:]
        img_file.write_bytes(modified)

        assert DjiRjpegParser.is_rjpeg(img_file) is True

    def test_extract_thermal_stream_not_present_returns_none(self, tmp_path):
        normal_jpg = tmp_path / "normal.jpg"
        img = Image.new("RGB", (640, 512))
        img.save(normal_jpg, format="JPEG")

        stream = DjiRjpegParser.extract_raw_thermal_stream(normal_jpg)
        assert stream is None


class TestDjiMetadataParserIntegration:
    """Testes de integração para a fachada unificada DjiMetadataParser."""

    @pytest.fixture
    def mock_dji_thermal_image(self, tmp_path) -> Path:
        """Cria uma imagem JPEG com tags DJI Matrice 4T injetadas no container."""
        img_path = tmp_path / "DJI_20260910_0001_T.JPG"
        img = Image.new("RGB", (640, 512), color=(50, 50, 50))
        img.save(img_path, format="JPEG")

        # Injeta o bloco XMP com metadados do Matrice 4T
        content = img_path.read_bytes()
        injected = content[:-2] + MOCK_DJI_XMP_XML.encode("utf-8") + content[-2:]
        img_path.write_bytes(injected)

        return img_path

    def test_complete_metadata_parsing(self, mock_dji_thermal_image):
        dto = DjiMetadataParser.parse(mock_dji_thermal_image)

        assert isinstance(dto, DjiParsedMetadataDTO)
        assert dto.file_name == "DJI_20260910_0001_T.JPG"
        assert dto.width == 640
        assert dto.height == 512
        assert dto.is_valid is True
        assert dto.raw_xmp_found is True

        # RTK
        assert dto.rtk.status == RtkStatus.FIXED
        assert dto.rtk.flag == 50
        assert dto.rtk.is_precise is True
        assert dto.rtk.horizontal_accuracy_meters is not None

        # Orientação
        assert dto.orientation.gimbal_pitch == pytest.approx(-89.5)
        assert dto.orientation.gimbal_yaw == pytest.approx(134.8)

        # Altitudes
        assert dto.relative_altitude_meters == pytest.approx(24.8)
        assert dto.absolute_altitude_meters == pytest.approx(745.25)

        # Radiometria
        assert dto.radiometry.emissivity == pytest.approx(0.92)
        assert dto.radiometry.reflected_temp_celsius == pytest.approx(18.5)
        assert dto.radiometry.relative_humidity == pytest.approx(0.55)  # 55.0% -> 0.55
        assert dto.radiometry.gain_mode == ThermalGainMode.HIGH_GAIN

        # Câmera
        assert dto.camera.drone_model == "Matrice 4T"
        assert dto.camera.camera_type == "Thermal"
        assert dto.camera.is_thermal_lens is True

    def test_dto_adapters_to_domain_objects(self, mock_dji_thermal_image):
        dto = DjiMetadataParser.parse(mock_dji_thermal_image)

        # Adiciona coordenadas fictícias para teste do adapter
        dto.latitude = -23.5505
        dto.longitude = -46.6333

        # Teste de conversão para GeoCoordinate
        geo_coord = DjiMetadataParser.to_geo_coordinate(dto)
        assert isinstance(geo_coord, GeoCoordinate)
        assert geo_coord.latitude == -23.5505
        assert geo_coord.longitude == -46.6333
        assert geo_coord.altitude_meters == pytest.approx(745.25)

        # Teste de conversão para ThermalMatrixMeta
        matrix = np.full((512, 640), 42.5, dtype=np.float32)
        matrix[100, 100] = 78.0
        matrix[200, 200] = 22.0

        meta = DjiMetadataParser.to_thermal_matrix_meta(dto, matrix=matrix)
        assert isinstance(meta, ThermalMatrixMeta)
        assert meta.emissivity == pytest.approx(0.92)
        assert meta.reflected_temp_celsius == pytest.approx(18.5)
        assert meta.min_temp_celsius == pytest.approx(22.0)
        assert meta.max_temp_celsius == pytest.approx(78.0)
        assert meta.sensor_width == 640
        assert meta.sensor_height == 512
