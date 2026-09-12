# SolarGuard Vision (Research Edition v1.0)

[![CI/CD Pipeline](https://github.com/itamarsilva2021/SolarGuard-Vision/actions/workflows/ci.yml/badge.svg)](https://github.com/itamarsilva2021/SolarGuard-Vision/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-240%20passed-brightgreen?logo=pytest)](https://github.com/itamarsilva2021/SolarGuard-Vision)
[![Coverage](https://img.shields.io/badge/Coverage-87%25-brightgreen?logo=codecov)](https://github.com/itamarsilva2021/SolarGuard-Vision)
[![Git LFS](https://img.shields.io/badge/Git%20LFS-Models%20%26%20Datasets-blueviolet?logo=git-lfs)](docs/ARTEFATOS_E_STORAGE.md)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Licensing](https://img.shields.io/badge/Licensing-Ed25519%20RFC%208032-informational)](docs/LICENSING_ARCHITECTURE.md)
[![Norma](https://img.shields.io/badge/Norma-IEC%20TS%2062446--3-orange.svg)](https://webstore.iec.ch/publication/28628)

> **Plataforma Científica e Industrial Autônoma de Diagnóstico Termográfico Aéreo para Usinas Solares Fotovoltaicas.**

---

## ☀️ Visão Geral

O **SolarGuard Vision** é um sistema completo desenvolvido para o diagnóstico de anomalias térmicas em módulos fotovoltaicos a partir de imagens aéreas capturadas por drones (RPAs), com suporte especializado para **DJI Matrice 4T**. O sistema unifica:
- **Calibração Radiométrica de Nível Físico:** Equações de Planck, decaimento angular de emissividade e compensação atmosférica;
- **Detecção de Falhas com Visão Computacional Profunda:** Redes neurais de última geração **YOLOv11**;
- **Classificação Normativa de Severidade:** Diagnóstico automatizado conforme a **IEC TS 62446-3:2017**;
- **Mapeamento Topológico de Precisão:** Vínculo geométrico entre cada falha e o módulo físico (*String*, Linha e Coluna da usina);
- **Geração de Laudos Periciais Automatizados:** Exportação em PDF pericial, planilhas Excel (.xlsx) e mapas geoespaciais interativos (Folium);
- **Segurança Criptográfica Assimétrica:** Licenciamento baseado em curvas elípticas **Ed25519** com vinculação física por Hardware ID (HWID).

---

## 🏛️ Arquitetura do Sistema

O software foi construído seguindo rigorosamente a **Clean Architecture** (Arquitetura Limpa) e os princípios **SOLID**:

```
SolarGuard Vision/
├── src/
│   ├── core/                  # Configurações Pydantic, Logging e Result Pattern
│   ├── domain/                # Entidades, Enums e Contratos (Python puro)
│   ├── application/           # Casos de Uso, Orquestração e Validação Científica
│   ├── infrastructure/        # Motores de Radiometria, YOLOv11, SQLite WAL, DJI e GIS
│   └── presentation/          # Interface Gráfica Reativa em PySide6 (Qt)
├── docs/                      # Compêndio Documental Completo para Dissertação
├── tests/                     # 274 Testes Automatizados (100% de Aprovação)
├── .github/workflows/         # Pipeline de CI/CD (Ruff, MyPy, Pytest, Coverage)
├── uv.lock                    # Ambiente determinístico e reproduzível
└── packaging/                 # Scripts de Empacotamento para Windows
```

---

## 🚀 Instalação Rápida e Reproduzível (`uv`)

O projeto utiliza o gerenciador de alta performance **`uv`** com **`uv.lock`**, garantindo 100% de reprodutibilidade e separação estrita entre ambientes.

### Instalação com `uv` (Recomendado):
```powershell
# 1. Clonar o repositório e baixar os modelos pesados com Git LFS
git clone https://github.com/itamarsilva2021/SolarGuard-Vision.git
cd SolarGuard-Vision
git lfs pull

# 2. Instalação Enxuta de Produção (Apenas Runtime):
uv sync --no-dev

# Ou para Ambiente Completo de Desenvolvimento (Testes + Linter):
uv sync --all-groups

# 3. Executar o sistema:
uv run python main.py

# 4. Executar a suíte de testes (240 testes):
uv run pytest -v
```

### Instalação Tradicional (`pip`):
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python main.py
```

---

## 📊 Resultados Experimentais Reais (Mestrado)

O modelo YOLOv11n foi treinado e avaliado com **100% de dados reais de campo** (sem dados simulados), sob avaliação científica com pareamento guloso por IoU ($\ge 0.45$) e contabilização estrita da classe `background` (conforme detalhado em [`docs/AUDIT_FIX_EVALUATION.md`](docs/AUDIT_FIX_EVALUATION.md)):

- **Imagens Reais de Usinas:** 52 imagens
- **Anotações de Falhas Íntegras:** 511 instâncias reais auditadas
- **mAP Global (@50):** **35.73%** (com classe `panel with hotspots` atingindo **68.40%**)
- **mAP Global (@50-95):** **27.48%**
- **Revocação (Recall):** **68.40%**
- **Acurácia Pareada Estrita ($\text{IoU} \ge 0.45$):** **0.00%** (avaliação realista com penalização por falsos negativos/omissões espaciais de `background`, eliminando o bug metodológico anterior que inflava artificialmente a acurácia para 100%)
- **Tempo de Inferência:** $82.8\text{ ms}$ por imagem em CPU ($> 65\text{ FPS}$ em GPU)

---

## 📚 Documentação Completa

Todos os manuais e relatórios técnicos estão disponíveis na pasta [`docs/`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/):
- [`documentacao_tecnica.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/documentacao_tecnica.md)
- [`documentacao_algoritmo.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/documentacao_algoritmo.md)
- [`documentacao_arquitetura.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/documentacao_arquitetura.md)
- [`manual_do_usuario.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/manual_do_usuario.md)
- [`manual_de_instalacao.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/manual_de_instalacao.md)
- [`resultados_experimentais.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/resultados_experimentais.md)
- [`relatorio_conformidade_arquitetural.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/relatorio_conformidade_arquitetural.md)
- [`dissertacao_validacao_experimental.md`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/docs/dissertacao_validacao_experimental.md)

---

## ⚖️ Licença

Este projeto é desenvolvido para fins de pesquisa científica e acadêmica no âmbito do Programa de Pós-Graduação em Engenharia. Todos os direitos reservados.
