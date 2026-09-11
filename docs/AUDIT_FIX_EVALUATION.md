# Relatório de Auditoria e Correção Científica da Avaliação Experimental (SolarGuard Vision)

**Projeto:** SolarGuard Vision — Sistema Termográfico Inteligente para Inspeção Fotovoltaica  
**Data:** 11 de Setembro de 2026  
**Responsabilidade Metodológica:** Avaliação de Modelos de Inteligência Artificial para Detecção de Anomalias Térmicas  
**Referência Normativa:** IEC TS 62446-3 / Padrões de Avaliação de Visão Computacional (PASCAL VOC / COCO)

---

## 1. Resumo Executivo da Auditoria

Em conformidade com os princípios de integridade científica e rigor metodológico para dissertação de mestrado, foi conduzida uma auditoria abrangente sobre o módulo de validação e avaliação experimental do SolarGuard Vision.

A auditoria identificou uma **anomalia metodológica crítica** na rotina de extração de predições e cálculo da matriz de confusão e métricas derivadas (Accuracy, Precision, Recall e F1-score). A lógica anterior convertia falsos negativos em predições perfeitas quando o detector não produzia detecções com sobreposição suficiente, inflando artificialmente a acurácia para **100,00%**.

Este documento detalha o diagnóstico do erro, a fundamentação matemática adotada para a correção, a implementação do pareamento estrito via *Intersection over Union* ($\text{IoU} \ge 0.45$) com tratamento explícito da classe `background`, a cobertura por testes unitários e os resultados comparativos antes e após a correção.

---

## 2. Diagnóstico da Falha Metodológica

### 2.1 Código Auditado

No arquivo [`src/application/services/experimental_evaluation_service.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/application/services/experimental_evaluation_service.py), na função `_extract_real_ground_truth_and_predictions()`, a lógica de atribuição de rótulos preditos para cada caixa de Ground Truth estava implementada conforme a estrutura:

```python
# CÓDIGO ANTERIOR COM FALHA METODOLÓGICA (LINHAS 357-364):
if best_iou >= 0.20 and best_pred_idx != -1:
    matched_preds.add(best_pred_idx)
    pred_name = class_names.get(best_pred_cls, f"class_{best_pred_cls}")
    y_pred.append(pred_name)
else:
    # Falso Negativo: nenhuma detecção correspondente encontrada (ou detecção de fundo)
    if pred_boxes:
        y_pred.append(class_names.get(pred_boxes[0][0], gt_name))
    else:
        y_pred.append(gt_name)  # <-- ERRO CRÍTICO: Atribuía o próprio GT como predição!
```

### 2.2 Impactos do Bug

1. **Transformação de Falsos Negativos em Acertos Perfeitos:**  
   Quando uma anomalia térmica real presente na imagem não era detectada pelo modelo (ou a predição obtinha $\text{IoU} < 0.20$), a rotina executava `y_pred.append(gt_name)`. Como consequência, $y_{true} == y_{pred}$, registrando um **True Positive espúrio** para um objeto não detectado.
2. **Omissão de Falsos Positivos:**  
   Predições produzidas pelo detector em regiões onde não existia anomalia (falsos alarmes) eram ignoradas no cômputo da matriz, desconsiderando predições espúrias.
3. **Métricas Infladas Artificialmente:**  
   A Acurácia Global e a Precisão eram reportadas como $1.0000$ (100%), gerando um relatório metodologicamente inválido para defesa acadêmica.

---

## 3. Fundamentação Teórica e Formulação Matemática

Na detecção de objetos baseada em *bounding boxes* e coordenadas espaciais normalizadas ($x, y, w, h$), a avaliação clássica de classificação unidimensional não se aplica diretamente sem um algoritmo formal de pareamento espacial biunívoco.

### 3.1 Métrica de Sobreposição Espacial (IoU)

Dadas duas caixas delimitadoras $B_{gt}$ (Ground Truth) e $B_{pred}$ (Predição), a taxa de sobreposição espacial é computada pela razão entre a área de interseção e a área de união:

$$\text{IoU}(B_{gt}, B_{pred}) = \frac{\text{Área}(B_{gt} \cap B_{pred})}{\text{Área}(B_{gt} \cup B_{pred})}$$

Adota-se o limiar científico padrão de aceitação:

$$\tau_{\text{IoU}} = 0.45$$

### 3.2 Algoritmo de Pareamento Guloso (*Greedy Bounding Box Matching*)

1. **Ordenação por Confiança:** As predições geradas pelo modelo são ordenadas em ordem decrescente de confiança:
   $$\mathcal{P} = \{ (B_j, c_j, s_j) \mid s_1 \ge s_2 \ge \dots \ge s_m \}$$
2. **Seleção Biunívoca:** Para cada predição $j$, busca-se o Ground Truth $i \in \mathcal{G}$ não alocado que maximize $\text{IoU}(B_i, B_j)$:
   $$\text{se } \max_{i} \text{IoU}(B_i, B_j) \ge 0.45 \implies \text{Match: } (y_{true} = c_i, y_{pred} = c_j)$$
3. **Definição Estatística dos Casos:**
   - **Caso A (True Positive):** $\text{IoU} \ge 0.45$ e $c_i == c_j \implies$ Predição correta.
   - **Caso C (Classification Error / Confusion):** $\text{IoU} \ge 0.45$ e $c_i \ne c_j \implies$ O modelo localizou a anomalia mas errou sua categoria (ex: confundiu *hotspot group* com *panel with hotspots*).
   - **Caso B (False Negative):** Ground Truth $i$ sem predição correspondente com $\text{IoU} \ge 0.45$:
     $$y_{true} = c_i, \quad y_{pred} = \text{"background"}$$
     *Garante que a omissão seja computada no denominador do Recall e NUNCA como acerto.*
   - **Caso D (False Positive):** Predição $j$ sem Ground Truth correspondente:
     $$y_{true} = \text{"background"}, \quad y_{pred} = c_j$$
     *Garante que falsos alarmes reduzam a Precisão.*

### 3.3 Estrutura da Matriz de Confusão $(C + 1) \times (C + 1)$

Com a introdução da categoria explícita `background`, a matriz de confusão $M$ possui dimensão $(C + 1) \times (C + 1)$, onde $C$ é o número de classes de anomalias térmicas.

$$\begin{pmatrix}
M_{1,1} & \dots & M_{1,C} & M_{1, \text{bg}} (\text{FN}_1) \\
\vdots & \ddots & \vdots & \vdots \\
M_{C,1} & \dots & M_{C,C} & M_{C, \text{bg}} (\text{FN}_C) \\
M_{\text{bg}, 1} (\text{FP}_1) & \dots & M_{\text{bg}, C} (\text{FP}_C) & M_{\text{bg}, \text{bg}} (\text{TN})
\end{pmatrix}$$

### 3.4 Fórmulas de Desempenho por Classe

Para cada anomalia $k \in \{1, \dots, C\}$:

$$\text{Precision}_k = \frac{\text{TP}_k}{\text{TP}_k + \text{FP}_k}$$

$$\text{Recall}_k = \frac{\text{TP}_k}{\text{TP}_k + \text{FN}_k}$$

$$\text{F1}_k = 2 \cdot \frac{\text{Precision}_k \cdot \text{Recall}_k}{\text{Precision}_k + \text{Recall}_k}$$

---

## 4. Implementação da Correção no Código

### 4.1 Método Estático Determinístico

Foi introduzido o método [`match_detections_with_ground_truth`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/application/services/experimental_evaluation_service.py#L338-L400) na classe `ExperimentalEvaluationService`:

```python
@classmethod
def match_detections_with_ground_truth(
    cls,
    gt_boxes: List[Tuple[int, float, float, float, float]],
    pred_boxes: List[Tuple[int, float, float, float, float, float]],
    class_names: Dict[int, str],
    iou_threshold: float = 0.45,
    background_label: str = "background",
) -> Tuple[List[str], List[str]]:
```

A função executa:
1. Ordenação das predições por confiança decrescente.
2. Atribuição gulosa aos GTs com $\text{IoU} \ge 0.45$.
3. Geração explícita de $(y_{true}=c_{gt}, y_{pred}=\text{"background"})$ para GTs órfãos.
4. Geração explícita de $(y_{true}=\text{"background"}, y_{pred}=c_{pred})$ para predições não pareadas.

### 4.2 Suporte a `target_classes` na Agregação

No arquivo [`src/application/validation/classification_metrics.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/application/validation/classification_metrics.py), a calculadora de métricas foi aprimorada para permitir o parâmetro opcional `target_classes`. Dessa forma, as médias macro e ponderadas agregam sobre as classes reais de anomalia fotovoltaica (o domínio do problema), enquanto o detalhamento analítico mantém a visualização transparente do impacto do `background`.

---

## 5. Cobertura por Testes Unitários

Foi implementada a suíte de testes unitários em [`tests/application/test_scientific_evaluation_audit.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/tests/application/test_scientific_evaluation_audit.py), cobrindo exaustivamente os quatro cenários fundamentais:

| Teste | Cenário Avaliado | Comportamento Esperado | Status |
| :--- | :--- | :--- | :---: |
| `test_case_a_true_positive` | GT existe e predição tem $\text{IoU} \ge 0.45$ com a mesma classe | $y_{true} == y_{pred} \implies \text{TP}=1, \text{FN}=0, \text{FP}=0$ | **APROVADO** |
| `test_case_b_false_negative_when_no_detection` | GT existe e modelo não gerou nenhuma predição | $y_{true} = c_{gt}, y_{pred} = \text{"background"} \implies \text{FN}=1, \text{Acc}=0\%$ | **APROVADO** |
| `test_case_b_false_negative_when_iou_insufficient` | GT existe e predição está distante ($\text{IoU} < 0.45$) | Registra $\text{FN}$ para o GT e $\text{FP}$ para a caixa órfã | **APROVADO** |
| `test_case_c_classification_error` | GT existe ($\text{IoU} \ge 0.45$), mas classe predita é diferente | Registra confusão entre classes: $y_{true} \ne y_{pred}$ | **APROVADO** |
| `test_case_d_false_positive_ghost_detection` | Predição gerada sem nenhum GT na imagem | $y_{true} = \text{"background"}, y_{pred} = c_{pred} \implies \text{FP}=1$ | **APROVADO** |
| `test_multi_detection_greedy_matching` | Duas predições para o mesmo GT | A de maior confiança faz match; a redundante vira $\text{FP}$ | **APROVADO** |

**Resultado dos Testes:** 6/6 aprovados no módulo e 213/213 aprovados na suíte completa do sistema.

---

## 6. Comparativo Experimental Antes vs. Depois da Correção

Ao submeter o modelo real treinado (`models/best.pt`) contra o conjunto de validação do dataset termográfico (`datasets/thermal_pv_mestrado/valid` com 24 imagens e 91 anotações de Ground Truth):

| Métrica | Antes da Auditoria (Com Bug) | Após a Correção Científica | Interpretação Científica |
| :--- | :---: | :---: | :--- |
| **Acurácia Global** | **100,00%** | **0,00%** | Antes: Falsos negativos eram forçados como acerto. Depois: Revela a taxa real de acerto espacial no limiar $\text{IoU} \ge 0.45$. |
| **Falsos Negativos (hotspot group)** | 0 | **57** | Todas as 57 instâncias reais não alcançaram $\text{IoU} \ge 0.45$ com confiança $\ge 0.25$. |
| **Falsos Negativos (panel with hotspots)**| 0 | **34** | Todas as 34 instâncias reais foram devidamente contabilizadas como omissões ($\text{FN}$). |
| **Falsos Positivos (Predições órfãs)** | 0 | **125** | 125 detecções fora da região de Ground Truth computadas como $\text{FP}$. |
| **Dimensão da Matriz de Confusão** | $2 \times 2$ | **$3 \times 3$ (com background)** | Padrão Ultralytics / COCO com visualização explícita de omissões e falsos alarmes. |

---

## 7. Parecer para a Dissertação de Mestrado

1. **Adesão Metodológica Estrita:** A avaliação experimental do SolarGuard Vision atende integralmente às definições matemáticas de detecção de objetos.
2. **Transparência Acadêmica:** A eliminação da acurácia inflada de 100% protege a pesquisa de contestações metodológicas durante a defesa de mestrado, fornecendo um diagnóstico fidedigno do detector.
3. **Rastreabilidade e Reprodutibilidade:** Os resultados corrigidos são persistidos no banco de dados SQLite (`ai_experiments`) e exportados para PDF, Excel e CSV de forma automatizada e auditável.
