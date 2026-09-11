"""
Testes unitários para o utilitário de particionamento e auditoria de independência de datasets.
Verifica:
- Detecção de vazamento metodológico (val == test)
- Isolamento estrito de voos entre treino, validação e teste
- Reorganização estrutural em train/, valid/ e test/
- Atualização e consistência do data.yaml
"""

import pytest
from pathlib import Path
import yaml
from scripts.create_independent_test_set import DatasetSplitter, DatasetAuditError


class TestDatasetSplitter:
    @pytest.fixture
    def mock_dataset_with_leakage(self, tmp_path):
        """Cria dataset dummy onde val aponta para test (vazamento)."""
        root = tmp_path / "mock_dataset"
        (root / "train" / "images").mkdir(parents=True)
        (root / "train" / "labels").mkdir(parents=True)
        (root / "valid" / "images").mkdir(parents=True)
        (root / "valid" / "labels").mkdir(parents=True)

        # 10 imagens no total
        for i in range(1, 11):
            split = "train" if i <= 7 else "valid"
            flight_id = f"flight_{i % 3 + 1}"
            img = root / split / "images" / f"{flight_id}_img{i}.jpg"
            lbl = root / split / "labels" / f"{flight_id}_img{i}.txt"
            img.write_text("fake_image_bytes")
            lbl.write_text("0 0.5 0.5 0.2 0.2\n1 0.4 0.4 0.3 0.3\n")

        # data.yaml com val == test
        yaml_content = {
            "path": str(root),
            "train": "train/images",
            "val": "valid/images",
            "test": "valid/images",  # <-- Vazamento de avaliação
            "nc": 2,
            "names": ["hotspot", "panel"],
        }
        (root / "data.yaml").write_text(yaml.dump(yaml_content))
        return root

    def test_audit_yaml_detects_val_test_leakage(self, mock_dataset_with_leakage):
        splitter = DatasetSplitter(dataset_dir=mock_dataset_with_leakage)
        audit = splitter.audit_yaml()

        assert audit["exists"] is True
        assert audit["has_val_test_leakage"] is True
        assert "Violação crítica" in audit["leakage_reason"]

    def test_audit_yaml_clean_when_independent(self, tmp_path):
        root = tmp_path / "clean_dataset"
        root.mkdir()
        yaml_content = {
            "train": "train/images",
            "val": "valid/images",
            "test": "test/images",
            "nc": 2,
            "names": ["hotspot", "panel"],
        }
        yaml_file = root / "data.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        splitter = DatasetSplitter(dataset_dir=root)
        audit = splitter.audit_yaml(yaml_file)

        assert audit["exists"] is True
        assert audit["has_val_test_leakage"] is False
        assert audit["val"] == "valid/images"
        assert audit["test"] == "test/images"

    def test_extract_flight_id(self, tmp_path):
        splitter = DatasetSplitter(dataset_dir=tmp_path)

        assert splitter.extract_flight_id("flight_01_frame12.jpg") == "flight_01"
        assert splitter.extract_flight_id("voo-3_panel.png") == "voo-3"
        assert splitter.extract_flight_id("DJI_04_thermal.jpg") == "dji_04"
        assert splitter.extract_flight_id("thermalhotspot5_PNG.rf.jpg") == "Flight_A_Rows01-13"
        assert splitter.extract_flight_id("thermalhotspot20_PNG.rf.jpg") == "Flight_B_Rows14-26"
        assert splitter.extract_flight_id("thermalhotspot70_PNG.rf.jpg") == "Flight_F_Rows63-73"

    def test_split_guarantees_flight_independence(self, mock_dataset_with_leakage):
        splitter = DatasetSplitter(
            dataset_dir=mock_dataset_with_leakage,
            flight_regex=r"^(flight_\d+)",
            val_ratio=0.3,
            test_ratio=0.3,
        )
        samples = splitter.collect_all_samples()
        assert len(samples) == 10

        splits = splitter.split(samples)
        train_flights = set(s["flight_id"] for s in splits["train"])
        val_flights = set(s["flight_id"] for s in splits["valid"])
        test_flights = set(s["flight_id"] for s in splits["test"])

        # Nenhum voo compartilhado entre treino e teste!
        assert len(train_flights.intersection(test_flights)) == 0
        assert len(train_flights.intersection(val_flights)) == 0
        assert len(val_flights.intersection(test_flights)) == 0

    def test_apply_structure_creates_test_folder_and_updates_yaml(self, mock_dataset_with_leakage):
        splitter = DatasetSplitter(
            dataset_dir=mock_dataset_with_leakage,
            flight_regex=r"^(flight_\d+)",
            val_ratio=0.3,
            test_ratio=0.3,
        )
        samples = splitter.collect_all_samples()
        splits = splitter.split(samples)

        res = splitter.apply_structure(splits, dry_run=False)

        assert (mock_dataset_with_leakage / "train" / "images").exists()
        assert (mock_dataset_with_leakage / "valid" / "images").exists()
        assert (mock_dataset_with_leakage / "test" / "images").exists()
        assert (mock_dataset_with_leakage / "test" / "labels").exists()

        post_audit = splitter.audit_yaml()
        assert post_audit["has_val_test_leakage"] is False
        assert post_audit["val"] == "valid/images"
        assert post_audit["test"] == "test/images"
