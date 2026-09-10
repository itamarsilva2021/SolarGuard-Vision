"""
Testes unitários para os Objetos de Valor (Value Objects) do domínio.
"""

import pytest
from src.domain.value_objects import GeoCoordinate, DeltaT, BoundingBox, ThermalMatrixMeta
from src.domain.enums import SeverityLevel
from src.domain.exceptions import (
    InvalidCoordinateError,
    InvalidTemperatureError,
    InvalidBoundingBoxError,
    ThermalDataCorruptedError,
)


class TestGeoCoordinate:
    def test_valid_coordinate_creation(self):
        coord = GeoCoordinate(latitude=-23.5505, longitude=-46.6333, altitude_meters=760.0)
        assert coord.latitude == -23.5505
        assert coord.longitude == -46.6333
        assert coord.altitude_meters == 760.0
        assert coord.to_tuple() == (-23.5505, -46.6333)

    def test_invalid_latitude_raises_error(self):
        with pytest.raises(InvalidCoordinateError):
            GeoCoordinate(latitude=95.0, longitude=-40.0)

        with pytest.raises(InvalidCoordinateError):
            GeoCoordinate(latitude=-95.0, longitude=-40.0)

    def test_invalid_longitude_raises_error(self):
        with pytest.raises(InvalidCoordinateError):
            GeoCoordinate(latitude=-10.0, longitude=185.0)

        with pytest.raises(InvalidCoordinateError):
            GeoCoordinate(latitude=-10.0, longitude=-185.0)

    def test_distance_to_meters_haversine(self):
        # Ponto 1 e Ponto 2 separados por aproximadamente 111 km (1 grau de latitude)
        p1 = GeoCoordinate(latitude=0.0, longitude=0.0)
        p2 = GeoCoordinate(latitude=1.0, longitude=0.0)
        dist = p1.distance_to_meters(p2)
        assert 110_000 < dist < 112_000


class TestDeltaT:
    def test_delta_t_calculation(self):
        dt = DeltaT(t_max_celsius=65.5, t_ref_celsius=35.0)
        assert dt.value == 30.5
        assert dt.classify_iec_62446_3() == SeverityLevel.CRITICAL

    def test_negative_absolute_zero_raises_error(self):
        with pytest.raises(InvalidTemperatureError):
            DeltaT(t_max_celsius=-280.0, t_ref_celsius=25.0)


class TestBoundingBox:
    def test_bounding_box_properties(self):
        bbox = BoundingBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6, is_normalized=True)
        assert pytest.approx(bbox.width) == 0.4
        assert pytest.approx(bbox.height) == 0.4
        assert pytest.approx(bbox.area) == 0.16
        assert bbox.center == (pytest.approx(0.3), pytest.approx(0.4))

    def test_invalid_bounds_raises_error(self):
        with pytest.raises(InvalidBoundingBoxError):
            BoundingBox(x_min=0.5, y_min=0.2, x_max=0.3, y_max=0.6)  # x_max < x_min

    def test_contains_point(self):
        bbox = BoundingBox(x_min=0.2, y_min=0.2, x_max=0.8, y_max=0.8)
        assert bbox.contains_point(0.5, 0.5) is True
        assert bbox.contains_point(0.1, 0.5) is False

    def test_iou_calculation(self):
        # Duas caixas idênticas: IoU deve ser 1.0
        b1 = BoundingBox(x_min=0.2, y_min=0.2, x_max=0.6, y_max=0.6)
        b2 = BoundingBox(x_min=0.2, y_min=0.2, x_max=0.6, y_max=0.6)
        assert b1.iou(b2) == 1.0

        # Caixas sem sobreposição: IoU deve ser 0.0
        b3 = BoundingBox(x_min=0.7, y_min=0.7, x_max=0.9, y_max=0.9)
        assert b1.iou(b3) == 0.0

    def test_conversion_to_pixels_and_back(self):
        bbox = BoundingBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6, is_normalized=True)
        pixel_bbox = bbox.to_pixels(img_width=640, img_height=512)
        assert pixel_bbox.is_normalized is False
        assert pixel_bbox.x_min == 64.0
        assert pixel_bbox.y_min == 102.4

        norm_bbox = pixel_bbox.to_normalized(img_width=640, img_height=512)
        assert norm_bbox.is_normalized is True
        assert pytest.approx(norm_bbox.x_min, 0.01) == 0.1


class TestThermalMatrixMeta:
    def test_dynamic_range_calculation(self, sample_thermal_meta):
        assert pytest.approx(sample_thermal_meta.dynamic_range) == 43.8

    def test_invalid_emissivity_raises_error(self):
        with pytest.raises(ThermalDataCorruptedError):
            ThermalMatrixMeta(emissivity=1.5)

    def test_min_greater_than_max_raises_error(self):
        with pytest.raises(ThermalDataCorruptedError):
            ThermalMatrixMeta(min_temp_celsius=60.0, max_temp_celsius=40.0)
