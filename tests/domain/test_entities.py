"""
Testes unitários para as Entidades do domínio SolarGuard Vision.
"""

import pytest
from src.domain.entities import ThermalAnomaly, PVModule, ThermalImage, Inspection, Project
from src.domain.enums import AnomalyType, SeverityLevel, InspectionStatus
from src.domain.value_objects import BoundingBox, DeltaT, GeoCoordinate
from src.domain.exceptions import DomainError


class TestThermalAnomaly:
    def test_anomaly_creation(self, sample_hotspot_anomaly):
        assert sample_hotspot_anomaly.anomaly_type == AnomalyType.HOTSPOT
        assert sample_hotspot_anomaly.severity == SeverityLevel.CRITICAL
        assert sample_hotspot_anomaly.is_critical is True
        assert sample_hotspot_anomaly.confidence == 0.94

    def test_invalid_confidence_raises_error(self, sample_bounding_box):
        with pytest.raises(DomainError):
            ThermalAnomaly(
                anomaly_type=AnomalyType.HOTSPOT,
                severity=SeverityLevel.LOW,
                confidence=1.5,  # Inválido (> 1.0)
                bbox=sample_bounding_box,
                max_temp_celsius=50.0,
            )

    def test_update_severity_from_delta_t(self, sample_bounding_box):
        anomaly = ThermalAnomaly(
            anomaly_type=AnomalyType.HOTSPOT,
            severity=SeverityLevel.INFORMATIVE,
            confidence=0.88,
            bbox=sample_bounding_box,
            max_temp_celsius=75.0,
            delta_t=DeltaT(t_max_celsius=75.0, t_ref_celsius=40.0),  # Delta = 35 -> Crítico
        )
        anomaly.update_severity_from_delta_t()
        assert anomaly.severity == SeverityLevel.CRITICAL


class TestPVModule:
    def test_module_health_status(self, sample_bounding_box):
        module = PVModule(bbox=sample_bounding_box)
        assert module.is_healthy is True

        # Adiciona módulo saudável
        healthy_det = ThermalAnomaly(
            anomaly_type=AnomalyType.HEALTHY_MODULE,
            severity=SeverityLevel.INFORMATIVE,
            confidence=0.95,
            bbox=sample_bounding_box,
            max_temp_celsius=38.0,
        )
        module.add_anomaly(healthy_det)
        assert module.is_healthy is True

        # Adiciona hotspot
        hotspot = ThermalAnomaly(
            anomaly_type=AnomalyType.HOTSPOT,
            severity=SeverityLevel.CRITICAL,
            confidence=0.91,
            bbox=sample_bounding_box,
            max_temp_celsius=70.0,
        )
        module.add_anomaly(hotspot)
        assert module.is_healthy is False
        assert module.worst_severity == SeverityLevel.CRITICAL


class TestThermalImage:
    def test_thermal_image_aggregation(self, sample_bounding_box, sample_hotspot_anomaly):
        image = ThermalImage(
            inspection_id="insp-123",
            file_path="C:/data/DJI_001_T.JPG",
            filename="DJI_001_T.JPG",
            width=640,
            height=512,
        )
        assert image.has_faults is False
        assert image.critical_count == 0

        image.add_anomaly(sample_hotspot_anomaly)
        assert image.has_faults is True
        assert image.critical_count == 1
        assert image.max_scene_temperature == 72.0


class TestInspection:
    def test_inspection_metrics(self, sample_hotspot_anomaly, sample_bounding_box):
        inspection = Inspection(
            project_id="proj-1",
            title="Inspeção Usina 01",
            inspector_name="Eng. Carlos Silva",
            irradiance_w_m2=850.0,
            wind_speed_m_s=2.5,
        )

        assert inspection.meets_iec_conditions is True

        # Criando imagem 1 com hotspot
        img1 = ThermalImage(
            inspection_id=inspection.id,
            file_path="/img1.jpg",
            filename="img1.jpg",
        )
        img1.add_anomaly(sample_hotspot_anomaly)

        # Criando imagem 2 com sujeira (Classe 1 / Baixo)
        img2 = ThermalImage(
            inspection_id=inspection.id,
            file_path="/img2.jpg",
            filename="img2.jpg",
        )
        soiling_anomaly = ThermalAnomaly(
            anomaly_type=AnomalyType.SOILING,
            severity=SeverityLevel.LOW,
            confidence=0.82,
            bbox=sample_bounding_box,
            max_temp_celsius=45.0,
        )
        img2.add_anomaly(soiling_anomaly)

        inspection.add_image(img1)
        inspection.add_image(img2)

        assert inspection.total_images == 2
        assert inspection.total_anomalies == 2
        assert inspection.total_faults == 2
        assert inspection.max_temperature == 72.0

        type_counts = inspection.count_by_type()
        assert type_counts[AnomalyType.HOTSPOT] == 1
        assert type_counts[AnomalyType.SOILING] == 1
        assert type_counts[AnomalyType.PID] == 0

        sev_counts = inspection.count_by_severity()
        assert sev_counts[SeverityLevel.CRITICAL] == 1
        assert sev_counts[SeverityLevel.LOW] == 1
        assert sev_counts[SeverityLevel.MEDIUM] == 0


class TestProject:
    def test_project_aggregation(self, sample_project):
        assert sample_project.total_inspections == 0
        assert sample_project.latest_inspection is None

        insp = Inspection(
            project_id=sample_project.id,
            title="Inspeção Inaugural",
            inspector_name="Eng. Roberto",
        )
        sample_project.add_inspection(insp)

        assert sample_project.total_inspections == 1
        assert sample_project.latest_inspection == insp
