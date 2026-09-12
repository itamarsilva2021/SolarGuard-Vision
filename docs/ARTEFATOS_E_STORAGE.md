# Governança de Artefatos Pesados e Storage (Git LFS)

Este documento estabelece as diretrizes de armazenamento, versionamento e distribuição dos artefatos de grande porte do ecossistema **SolarGuard Vision**, incluindo pesos de redes neurais profundas, datasets termográficos e saídas de laudos periciais.

---

## 1. Visão Geral da Arquitetura de Armazenamento

Para manter o repositório Git ágil, rápido para clonagem e em conformidade com as melhores práticas de Engenharia de Software e MLOps:

- **Git Standard (Core do Código):** Código-fonte Python, testes unitários, documentação Markdown, configurações estruturais e schemas JSON/YAML.
- **Git LFS (Large File Storage):** Pesos binários de modelos de Deep Learning (`*.pt`, `*.onnx`, `*.engine`) e imagens de alta resolução dos datasets de teste e validação.
- **Armazenamento Efêmero Local / `.gitignore`:** Caches de compilação (`.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `build/`, `dist/`), diretórios de runs de experimentos (`runs/`) e relatórios/mapas gerados dinamicamente em tempo de execução (`reports/*.pdf`, `reports/charts/*`, `reports/maps/*`).

---

## 2. Regras de Rastreamento do Git LFS (`.gitattributes`)

O arquivo [`.gitattributes`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/.gitattributes) delega automaticamente os seguintes padrões ao Git LFS:

```gitattributes
*.pt filter=lfs diff=lfs merge=lfs -text
*.onnx filter=lfs diff=lfs merge=lfs -text
*.engine filter=lfs diff=lfs merge=lfs -text
datasets/**/*.jpg filter=lfs diff=lfs merge=lfs -text
datasets/**/*.png filter=lfs diff=lfs merge=lfs -text
datasets/**/*.rjpeg filter=lfs diff=lfs merge=lfs -text
```

### O que isso significa?
No repositório Git ordinário, esses arquivos são armazenados apenas como ponteiros criptográficos de texto leve (contendo SHA-256 e tamanho em bytes). O conteúdo binário real é transferido de forma transparente via HTTPS para o servidor LFS do GitHub apenas quando solicitado.

---

## 3. Guia Operacional: Como Trabalhar com o Git LFS

### 3.1. Clonando o Repositório com Pesos
Ao clonar pela primeira vez em uma nova estação de trabalho:

```powershell
# 1. Instalar o cliente Git LFS no sistema (uma única vez por máquina)
git lfs install

# 2. Clonar normalmente o repositório
git clone https://github.com/itamarsilva2021/SolarGuard-Vision.git
cd SolarGuard-Vision

# 3. Baixar os pesos binários dos modelos (se não baixados automaticamente)
git lfs pull
```

### 3.2. Adicionando Novos Modelos Treinados
Ao exportar uma nova versão de pesos:
```powershell
# Salvar o modelo em models/ ou experiments/
cp runs/detect/train/weights/best.pt models/best_v2.pt

# O Git detecta automaticamente a regra *.pt e usa LFS
git add models/best_v2.pt
git commit -m "feat(model): atualizar pesos YOLOv11 com nova rodada de treino"
git push origin main
```

---

## 4. Política de Saneamento de Caches e Relatórios

Para evitar inflação acidental do histórico Git:
1. **Caches de Testes e Tipagem:** Diretórios como `.mypy_cache`, `.ruff_cache` e `.pytest_cache` são gerados sob demanda e **nunca** devem ser comitados.
2. **Relatórios Gerados Dinamicamente:** A pasta `reports/` é preservada através de marcadores `.gitkeep`, mas os PDFs, mapas interativos e gráficos PNG produzidos durante inspeções são estritamente mantidos em ambiente local.
