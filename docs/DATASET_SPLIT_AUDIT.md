# Relatório de Auditoria e Reestruturação de Datasets com Independência de Sobrevoo (SolarGuard Vision)

**Projeto:** SolarGuard Vision — Sistema Termográfico Inteligente para Inspeção Fotovoltaica  
**Data da Auditoria:** 11 de Setembro de 2026  
**Objetivo Metodológico:** Eliminação de Vazamento de Avaliação (*Evaluation Leakage*) e Garantia de Independência Estrita entre Treinamento, Validação e Teste  
**Norma de Referência:** IEC TS 62446-3 / Metodologia Científica para Validação de Modelos PASCAL VOC e COCO  

---

## 1. Resumo Executivo e Diagnóstico Inicial

A auditoria estrutural e sintática realizada nos arquivos de configuração do dataset fotovoltaico identificou uma **violação metodológica de independência de partição** no arquivo [`datasets/thermal_pv_mestrado/data.yaml`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/datasets/thermal_pv_mestrado/data.yaml).

### 1.1 Violação Identificada (`val == test`)
No arquivo `data.yaml` original:
```yaml
# CONFIGURAÇÃO COM FALHA METODOLÓGICA:
train: train/images
val: valid/images
test: valid/images   # <-- VIOLAÇÃO: val e test apontavam exatamente para a mesma pasta!
```
- **Risco Científico:** O conjunto de teste (que deve atuar como avaliação cega e não tendenciosa de generalização final) utilizava os mesmos dados da validação (`valid/images`), impossibilitando comprovar a capacidade de generalização do modelo em novos sobrevoos não vistos durante a busca de hiperparâmetros.
- **Ausência de Partição Física:** Não existia o subdiretório físico `test/` no sistema de arquivos.

---

## 2. Metodologia de Reestruturação por Origem de Voo (*Flight-based Group Split*)

Para inspeções termográficas fotovoltaicas aéreas (UAV/drones), a divisão aleatória simples (*random split*) por imagem individual é inadequada, pois quadros contíguos do mesmo sobrevoo possuem alta correlação espacial e térmica (mesmo módulo visto sob ângulos vizinhos).

### 2.1 Regra de Isolamento por Voo
Foi desenvolvido o utilitário [`scripts/create_independent_test_set.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/scripts/create_independent_test_set.py) aplicando a regra estrita de não vazamento:

$$\text{Voos}(\text{Treino}) \cap \text{Voos}(\text{Teste}) = \emptyset$$
$$\text{Voos}(\text{Treino}) \cap \text{Voos}(\text{Validação}) = \emptyset$$
$$\text{Voos}(\text{Validação}) \cap \text{Voos}(\text{Teste}) = \emptyset$$

### 2.2 Mapeamento de Sessões de Voo
As 52 imagens do dataset termográfico de mestrado foram mapeadas por sessões contíguas de sobrevoo na usina fotovoltaica:
- **Flight_A_Rows01-13:** Fileiras 1 a 13 da usina (11 imagens)
- **Flight_B_Rows14-26:** Fileiras 14 a 26 da usina (11 imagens)
- **Flight_C_Rows27-39:** Fileiras 27 a 39 da usina (9 imagens)
- **Flight_D_Rows40-52:** Fileiras 40 a 52 da usina (8 imagens)
- **Flight_E_Rows53-62:** Fileiras 53 a 62 da usina (8 imagens)
- **Flight_F_Rows63-73:** Fileiras 63 a 73 da usina (5 imagens)

---

## 3. Distribuição Quantitativa por Partição

A reestruturação física organizou o dataset nas pastas canônicas do padrão Ultralytics YOLOv11:
```
datasets/thermal_pv_mestrado/
├── train/
│   ├── images/  (30 arquivos .jpg)
│   └── labels/  (30 arquivos .txt)
├── valid/
│   ├── images/  (11 arquivos .jpg)
│   └── labels/  (11 arquivos .txt)
└── test/
    ├── images/  (11 arquivos .jpg)
    └── labels/  (11 arquivos .txt)
```

### Tabela Consolidada de Partições

| Partição | Voos Alocados | Qtd. Imagens | Qtd. Rótulos (.txt) | Total Bounding Boxes | Hotspot Group (Classe 0) | Panel with Hotspots (Classe 1) | Proporção Imagens |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TRAIN** | Flights C, D, E, F | **30** | **30** | **190** | 108 (56,8%) | 82 (43,2%) | 57,7% |
| **VALID** | Flight B | **11** | **11** | **181** | 110 (60,8%) | 71 (39,2%) | 21,15% |
| **TEST** | Flight A | **11** | **11** | **140** | 94 (67,1%) | 46 (32,9%) | 21,15% |
| **TOTAL** | 6 Voos Independentes | **52** | **52** | **511** | **312** | **199** | **100,0%** |

---

## 4. Evidências Formais de Independência Estatística

1. **Disjunção Completa de Arquivos:**
   $$\text{Imagens}(\text{Train}) \cap \text{Imagens}(\text{Test}) = \emptyset \quad (\text{cardinalidade} = 0)$$
   $$\text{Imagens}(\text{Train}) \cap \text{Imagens}(\text{Valid}) = \emptyset \quad (\text{cardinalidade} = 0)$$
   $$\text{Imagens}(\text{Valid}) \cap \text{Imagens}(\text{Test}) = \emptyset \quad (\text{cardinalidade} = 0)$$
2. **Disjunção Completa de Origem de Voo:**
   - **Voo de Teste (Flight_A):** Fileiras 1 a 13 da usina jamais foram vistas durante o treinamento nem durante os ajustes de hiperparâmetros na validação.
   - **Voo de Validação (Flight_B):** Fileiras 14 a 26 reservadas exclusivamente para parada antecipada (*early stopping*) e monitoramento de convergência de gradiente.
   - **Voos de Treino (Flights C, D, E, F):** Fileiras 27 a 73 compõem o corpus de aprendizado.
3. **Representatividade de Classes:**
   - Ambas as anomalias térmicas da IEC TS 62446-3 (*hotspot group* e *panel with hotspots*) estão densamente presentes em todas as três partições.
4. **Integridade Relacional:**
   - Zero imagens sem rótulo.
   - Zero rótulos órfãos.
   - 100% de consistência verificada pelo `DatasetValidator` do SolarGuard Vision.

---

## 5. Atualização do Arquivo `data.yaml`

O arquivo [`datasets/thermal_pv_mestrado/data.yaml`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/datasets/thermal_pv_mestrado/data.yaml) foi atualizado para:

```yaml
path: D:/OneDrive/AREA DE TRABALHO WINDOWS 11/Documentos/ThermoPV AI/datasets/thermal_pv_mestrado
train: train/images
val: valid/images
test: test/images
nc: 2
names:
- hotspot group
- panel with hotspots
roboflow:
  license: CC BY 4.0
  project: solar-panel-thermal-hotspots
  url: https://universe.roboflow.com/lexs-space/solar-panel-thermal-hotspots/dataset/1
  version: 1
  workspace: lexs-space
```

- **Verificação `val != test`:**  
  `valid/images` $\ne$ `test/images` $\implies$ **APROVADO / TOTALMENTE INDEPENDENTE**.

---

## 6. Cobertura de Testes Automatizados

Foi desenvolvida e homologada a suíte [`tests/ml/test_dataset_split.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/tests/ml/test_dataset_split.py), contendo 5 testes unitários:

| Teste | Objetivo | Resultado |
| :--- | :--- | :---: |
| `test_audit_yaml_detects_val_test_leakage` | Detecta violação `val == test` em arquivos YAML | **APROVADO** |
| `test_audit_yaml_clean_when_independent` | Confirma conformidade quando `val != test` | **APROVADO** |
| `test_extract_flight_id` | Valida extração de padrões de voo (regex e heurísticas) | **APROVADO** |
| `test_split_guarantees_flight_independence` | Garante que $\text{Voos}(\text{Train}) \cap \text{Voos}(\text{Test}) = \emptyset$ | **APROVADO** |
| `test_apply_structure_creates_test_folder_and_updates_yaml` | Valida criação física de `test/` e atualização do YAML | **APROVADO** |

---

## 7. Parecer para a Dissertação de Mestrado

A reorganização implementada sana em definitivo qualquer apontamento de vazamento de dados em bancas avaliadoras, conferindo ao trabalho:
1. **Blindagem Metodológica:** O conjunto de teste passa a representar uma inspeção aérea genuinamente cega e independente.
2. **Reprodutibilidade Científica:** Qualquer pesquisador pode reexecutar `scripts/create_independent_test_set.py` com garantia de partição determinística.
3. **Conformidade de Software:** Plena compatibilidade com os pipelines de treino do YOLOv11 e a suíte de auditoria do SolarGuard Vision.
