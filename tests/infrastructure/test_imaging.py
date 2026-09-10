"""
Testes unitários para o módulo de processamento de imagens, metadados e radiometria térmica.
Valida o parser radiométrico, extração de metadados e geração de miniaturas.
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

from src.domain.enums.palette_type import PaletteType
from src.infrastructure.imaging.dji_thermal_parser import DjiThermalParser
from src.infrastructure.imaging.preview_generator import PreviewGenerator
from src.infrastructure.imaging.metadata_extractor import MetadataExtractor


@pytest.fixture
def temp_image_dir(tmp_path) -> Path:
    """Cria diretório temporário para arquivos de teste de imagem."""
    img_dir = tmp_path / "test_images"
    img_dir.mkdir(parents=True, exist_ok=True)
    return img_dir


@pytest.fixture
def synthetic_radiometric_tiff(temp_image_dir) -> Path:
    """
    Gera um arquivo TIFF de 16 bits simulando matriz térmica radiométrica em centi-Kelvin.
    30.000 cK = 300 K = 26.85 °C (fundo normal)
    34.000 cK = 340 K = 66.85 °C (hotspot simulado)
    """
    tiff_path = temp_image_dir / "sample_radiometric_16bit.tiff"
    data = np.full((100, 100), 30000, dtype=np.uint16)
    # Cria uma região quente (hotspot) no centro
    data[40:60, 40:60] = 34000
    cv2.imwrite(str(tiff_path), data)
    return tiff_path


@pytest.fixture
def synthetic_optical_jpg(temp_image_dir) -> Path:
    """Gera um arquivo JPG colorido sintético (RGB/BGR)."""
    jpg_path = temp_image_dir / "sample_drone_optical.jpg"
    img = np.zeros((200, 300, 3), dtype=np.uint8)
    img[:] = (100, 150, 200)  # Cor de fundo
    cv2.circle(img, (150, 100), 30, (0, 0, 255), -1)  # Círculo vermelho
    cv2.imwrite(str(jpg_path), img)
    return jpg_path


@pytest.fixture
def synthetic_optical_png(temp_image_dir) -> Path:
    """Gera um arquivo PNG sintético."""
    png_path = temp_image_dir / "sample_panel.png"
    img = np.zeros((150, 150, 3), dtype=np.uint8)
    img[:] = (50, 100, 150)
    cv2.imwrite(str(png_path), img)
    return png_path


class TestDjiThermalParser:
    def test_extract_from_radiometric_tiff_16bit(self, synthetic_radiometric_tiff):
        parser = DjiThermalParser()
        matrix = parser.extract_temperature_matrix(synthetic_radiometric_tiff)

        assert isinstance(matrix, np.ndarray)
        assert matrix.shape == (100, 100)
        assert matrix.dtype == np.float32

        # Verifica temperatura de fundo (~26.85 °C)
        assert pytest.approx(matrix[10, 10], abs=0.5) == 26.85
        # Verifica temperatura do hotspot (~66.85 °C)
        assert pytest.approx(matrix[50, 50], abs=0.5) == 66.85

    def test_extract_metadata(self, synthetic_radiometric_tiff):
        parser = DjiThermalParser()
        meta = parser.extract_metadata(synthetic_radiometric_tiff)

        assert meta.sensor_width == 100
        assert meta.sensor_height == 100
        assert pytest.approx(meta.min_temp_celsius, abs=0.5) == 26.85
        assert pytest.approx(meta.max_temp_celsius, abs=0.5) == 66.85
        assert meta.dynamic_range > 35.0

    def test_extract_from_standard_jpg(self, synthetic_optical_jpg):
        parser = DjiThermalParser()
        matrix = parser.extract_temperature_matrix(synthetic_optical_jpg)
        assert matrix.shape == (200, 300)
        assert np.min(matrix) >= 20.0
        assert np.max(matrix) <= 80.0


class TestPreviewGenerator:
    def test_preview_generation_for_jpg(self, tmp_path, synthetic_optical_jpg):
        generator = PreviewGenerator(cache_dir=tmp_path / "cache")
        prev_path = generator.generate_preview(synthetic_optical_jpg, max_dimension=150)

        assert prev_path.exists()
        assert prev_path.suffix.lower() == ".jpg"

        # Carrega miniatura gerada para validar dimensões
        thumb = cv2.imread(str(prev_path))
        h, w = thumb.shape[:2]
        assert max(h, w) == 150
        assert w == 150  # Proporção 300x200 vira 150x100
        assert h == 100

    def test_preview_generation_with_thermal_palettes_for_16bit_tiff(
        self, tmp_path, synthetic_radiometric_tiff
    ):
        generator = PreviewGenerator(cache_dir=tmp_path / "cache")

        # Testa Ironbow
        prev_ironbow = generator.generate_preview(
            synthetic_radiometric_tiff,
            max_dimension=100,
            palette=PaletteType.IRONBOW,
        )
        assert prev_ironbow.exists()

        # Testa Rainbow
        prev_rainbow = generator.generate_preview(
            synthetic_radiometric_tiff,
            max_dimension=100,
            palette=PaletteType.RAINBOW,
        )
        assert prev_rainbow.exists()

        # Testa White Hot
        prev_white_hot = generator.generate_preview(
            synthetic_radiometric_tiff,
            max_dimension=100,
            palette=PaletteType.WHITE_HOT,
        )
        assert prev_white_hot.exists()


class TestMetadataExtractor:
    def test_gps_conversion(self):
        # 12° 58' 17.04" S -> -12.9714
        coord_tuple = (12, 58, 17.04)
        dec = MetadataExtractor._convert_gps_coordinate(coord_tuple, "S")
        assert pytest.approx(dec, abs=0.001) == -12.9714

        # 38° 30' 5.04" W -> -38.5014
        coord_tuple_lon = (38, 30, 5.04)
        dec_lon = MetadataExtractor._convert_gps_coordinate(coord_tuple_lon, "W")
        assert pytest.approx(dec_lon, abs=0.001) == -38.5014
