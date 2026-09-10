"""
Testes de conformidade com a norma IEC TS 62446-3 para classificação de severidade e tipos de falha.
"""

import pytest
from src.domain.enums import AnomalyType, SeverityLevel
from src.domain.value_objects import DeltaT


class TestIECSeverityClassification:
    @pytest.mark.parametrize(
        "delta_t,expected_severity",
        [
            (0.0, SeverityLevel.INFORMATIVE),
            (2.5, SeverityLevel.INFORMATIVE),
            (2.99, SeverityLevel.INFORMATIVE),
            (3.0, SeverityLevel.LOW),
            (5.5, SeverityLevel.LOW),
            (9.9, SeverityLevel.LOW),
            (10.0, SeverityLevel.MEDIUM),
            (18.5, SeverityLevel.MEDIUM),
            (29.99, SeverityLevel.MEDIUM),
            (30.0, SeverityLevel.CRITICAL),
            (45.0, SeverityLevel.CRITICAL),
            (60.0, SeverityLevel.CRITICAL),
        ],
    )
    def test_iec_62446_3_delta_t_thresholds(self, delta_t, expected_severity):
        classified = SeverityLevel.from_delta_t(delta_t)
        assert classified == expected_severity

    def test_delta_t_object_classification_method(self):
        dt_critical = DeltaT(t_max_celsius=75.0, t_ref_celsius=40.0)  # delta = 35.0
        assert dt_critical.classify_iec_62446_3() == SeverityLevel.CRITICAL

        dt_medium = DeltaT(t_max_celsius=52.0, t_ref_celsius=40.0)  # delta = 12.0
        assert dt_medium.classify_iec_62446_3() == SeverityLevel.MEDIUM

        dt_low = DeltaT(t_max_celsius=46.0, t_ref_celsius=40.0)  # delta = 6.0
        assert dt_low.classify_iec_62446_3() == SeverityLevel.LOW

        dt_info = DeltaT(t_max_celsius=41.5, t_ref_celsius=40.0)  # delta = 1.5
        assert dt_info.classify_iec_62446_3() == SeverityLevel.INFORMATIVE


class TestAnomalyTypes:
    def test_fault_distinction(self):
        # Módulos saudáveis não devem ser contabilizados como falha técnica
        assert AnomalyType.HEALTHY_MODULE.is_fault is False

        # Todas as outras classes representam falha/defeito
        assert AnomalyType.HOTSPOT.is_fault is True
        assert AnomalyType.DISCONNECTED_MODULE.is_fault is True
        assert AnomalyType.PID.is_fault is True
        assert AnomalyType.SOILING.is_fault is True
        assert AnomalyType.SHADING.is_fault is True

    def test_display_names_portuguese(self):
        assert "Hotspot" in AnomalyType.HOTSPOT.display_name
        assert "Módulo Desconectado" == AnomalyType.DISCONNECTED_MODULE.display_name
        assert "Degradação PID" == AnomalyType.PID.display_name
        assert "Sujidade" in AnomalyType.SOILING.display_name
        assert "Sombreamento" in AnomalyType.SHADING.display_name
        assert "Saudável" in AnomalyType.HEALTHY_MODULE.display_name
