"""
Testes unitários para o padrão Result do SolarGuard Vision.
"""

import pytest
from src.core.result import Success, Failure


class TestResultPattern:
    def test_success_flow(self):
        result = Success("Dado processado com sucesso")
        assert result.is_success is True
        assert result.is_failure is False
        assert result.value == "Dado processado com sucesso"
        assert result.unwrap() == "Dado processado com sucesso"

    def test_failure_flow(self):
        result = Failure("Erro ao ler matriz térmica")
        assert result.is_success is False
        assert result.is_failure is True
        assert result.error == "Erro ao ler matriz térmica"

        with pytest.raises(ValueError):
            result.unwrap()
