# Relatório de Auditoria de Consistência de Classes do Sistema (SolarGuard Vision)

**Projeto:** SolarGuard Vision — Sistema Termográfico Inteligente para Inspeção Fotovoltaica  
**Data da Auditoria:** 11 de Setembro de 2026  
**Responsabilidade:** Auditoria de Consistência Semântica e Mapeamento de Classes entre Artefatos de IA  
**Status do Modelo:** Pesos Preservados (Nenhuma modificação efetuada nos pesos conforme diretriz)

---

## 1. Resumo Executivo da Auditoria

Foi conduzida uma auditoria rigorosa para verificar o alinhamento de taxonomia e classes entre os cinco componentes que regem a Inteligência Artificial do SolarGuard Vision:
1. Os pesos compilados do modelo YOLOv11 ([`models/best.pt`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/models/best.pt));
2. Os metadados descritivos JSON ([`models/best.json`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/models/best.json));
3. A configuração do dataset de mestrado ([`datasets/thermal_pv_mestrado/data.yaml`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/datasets/thermal_pv_mestrado/data.yaml));
4. O pipeline de inferência em produção ([`src/infrastructure/detection/detector.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/detection/detector.py) e [`defect_classifier.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/detection/defect_classifier.py));
5. O módulo de avaliação científica experimental ([`src/application/services/experimental_evaluation_service.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/application/services/experimental_evaluation_service.py)).

### Conclusão Principal
Identificou-se uma **incompatibilidade semântica estrutural real** entre o modelo compilado em disco (`best.pt`, que é um detector mono-classe de geometria de módulos solares: `pv_panel`), a configuração de anomalias térmicas do dataset de mestrado (`hotspot group` e `panel with hotspots`, 2 classes) e os metadados anteriores (que alegavam 6 classes de defeitos).

Em estrito cumprimento às regras da tarefa, **nenhuma modificação foi realizada nos pesos do modelo**, o arquivo de metadados `models/best.json` foi corrigido para refletir com fidedignidade o conteúdo real do binário e as divergências foram formalmente documentadas para decisão acadêmica.

---

## 2. Inspeção Técnica dos Pesos Reais (`models/best.pt`)

A inspeção direta da estrutura serializada via `ultralytics.YOLO` e `torch.load` revelou os seguintes parâmetros internos do checkpoint:

| Propriedade Inspecionada | Valor Extraído do Binário |
| :--- | :--- |
| **Classe do Objeto** | `<class 'ultralytics.nn.tasks.DetectionModel'>` |
| **Número Real de Classes (`nc`)** | **1** |
| **Dicionário de Classes (`model.names`)** | **`{0: 'pv_panel'}`** |
| **Dataset Original de Treinamento** | `Thermal PV Panel Detection Dataset for UAV Inspection` |
| **Hash Criptográfico SHA-256** | `c97fd107607cc6541c703b0010d390083b8912301ff43f12cac2f17a56e42b09` |
| **Tamanho do Arquivo em Disco** | **5.456.794 bytes** (~5.20 MB) |

O modelo atual em `models/best.pt` é, portanto, um detector treinado para localizar a **silhueta física do painel fotovoltaico** (`pv_panel`), e não um classificador multi-classe de patologias térmicas internas.

---

## 3. Matriz Comparativa de Classes por Componente

| Componente | Qtd. Classes | Lista de Nomes de Classes | Função no Sistema |
| :--- | :---: | :--- | :--- |
| **Modelo Real (`models/best.pt`)** | **1** | `0: pv_panel` | Segmentação / bounding box do módulo fotovoltaico |
| **Metadata JSON Anterior (`models/best.json`)** | **6** | `0: hotspot, 1: disconnected_module, 2: pid, 3: soiling, 4: shading, 5: healthy_module` | Declaração teórica de taxonomia IEC TS 62446-3 (*Incorreto*) |
| **Metadata JSON Corrigido (`models/best.json`)** | **1** | `0: pv_panel` | Declaração auditada e fidedigna ao arquivo `.pt` (*Corrigido*) |
| **Dataset Real (`datasets/.../data.yaml`)** | **2** | `0: hotspot group, 1: panel with hotspots` | Dataset de mestrado termográfico Roboflow anotado |
| **Inferência Produção (`DefectClassifier`)** | **6** | `hotspot, disconnected_module, pid, soiling, shading, healthy_module` | Classificação de defeitos térmicos com fallback para `HOTSPOT` |
| **Avaliação Experimental (`Stage 19`)** | **2 + bg** | `hotspot group, panel with hotspots, background` | Auditoria experimental estatística com IoU $\ge 0.45$ |

---

## 4. Diagnóstico de Impacto e Divergências Detectadas

### 4.1 Divergência A: `best.pt` vs. `best.json` (Metadados Incorretos)
- **Problema:** O arquivo `models/best.json` afirmava que o modelo continha 6 classes (`num_classes: 6`), enquanto os pesos compilados possuem apenas 1 classe (`num_classes: 1`).
- **Ação Tomada:** O arquivo `models/best.json` foi retificado na íntegra, sincronizando `classes: {"0": "pv_panel"}` e `num_classes: 1` com o hash SHA-256 verificado.

### 4.2 Divergência B: `best.pt` vs. `data.yaml` (Incompatibilidade Semântica)
- **Problema:** O dataset termográfico de validação/teste possui anotações para 2 categorias de falhas:
  - `Classe 0`: *hotspot group* (grupo de pontos quentes em células)
  - `Classe 1`: *panel with hotspots* (painel inteiro apresentando anomalias térmicas severas)
  Por sua vez, o modelo prediz a classe `pv_panel` (o corpo inteiro do painel).
- **Consequência na Avaliação:** Quando o modelo prediz um `pv_panel`, seu identificador numérico é `0`. Na avaliação experimental, a classe `0` era mapeada para *hotspot group*. Como a caixa delimitadora do painel inteiro raramente coincide com a caixa pequena de um hotspot isolado ($\text{IoU} < 0.45$), o algoritmo de matching rigoroso corretamente computou as predições como Falsos Positivos e as anomalias não detectadas como Falsos Negativos.

### 4.3 Divergência C: `best.pt` vs. Pipeline de Inferência (`DefectClassifier`)
- **Problema:** No arquivo [`src/infrastructure/detection/detector.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/detection/detector.py), o método `detect()` invoca:
  ```python
  raw_label = model.names.get(cls_id, str(cls_id))  # Retorna 'pv_panel'
  anomaly_type = self.classifier.parse_anomaly_type(raw_label)
  ```
- **Fallback Automático:** No arquivo [`defect_classifier.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/detection/defect_classifier.py), `'pv_panel'` não consta no `CLASS_MAPPING`. O código executa:
  ```python
  logger.warning(f"Rótulo de classe desconhecido '{raw_label}'. Classificando como Hotspot.")
  return AnomalyType.HOTSPOT
  ```
  Assim, qualquer módulo fotovoltaico detectado em produção era categorizado heuristicamente como `HOTSPOT`, mesmo na ausência de defeito.

---

## 5. Medidas de Salvaguarda e Decisão Arquitetural

Conforme prescrito na regra:
> *"Caso exista incompatibilidade real: interromper alteração e documentar. Não modificar pesos do modelo nesta etapa."*

1. **Suspensão de Sobrescrita de Pesos:**  
   Os pesos de `models/best.pt` foram integralmente mantidos intactos.
2. **Retificação Documental:**  
   O arquivo de metadados `models/best.json` foi corrigido para que nenhuma documentação declare falsamente a existência de 6 classes no checkpoint atual.
3. **Recomendações Técnicas para Etapas Posteriores:**
   - **Opção 1 (Treinamento Especializado no Dataset de Mestrado):** Executar fine-tuning / treinamento de um novo checkpoint (`best_thermal_faults.pt`) com saída `nc=2` utilizando o dataset reestruturado [`datasets/thermal_pv_mestrado`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/datasets/thermal_pv_mestrado) com suas partições independentes de treino, validação e teste.
   - **Opção 2 (Arquitetura em Cascata de 2 Estágios - Recomendada para Usinas):**
     - **Estágio 1:** `models/best.pt` detecta e recorta a geometria dos módulos fotovoltaicos (`pv_panel`);
     - **Estágio 2:** O motor radiométrico [`RadiometryEngine`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/thermal/radiometry_engine.py) analisa a matriz térmica recortada do painel calculando $\Delta T$, detectando os hotspots internos e classificando conforme a severidade da IEC TS 62446-3.
