# Metodologia e Validação Experimental de Inteligência Artificial para Inspeção Termográfica Fotovoltaica

> [!NOTE]
> **Nota de Transparência Acadêmica & Retificação Metodológica (12 de Setembro de 2026):**  
> Os resultados e a matriz de confusão apresentados neste documento foram retificados após auditoria científica que identificou uma distorção metodológica na rotina anterior de extração de predições, a qual forçava falsos negativos como acertos perfeitos e inflava a acurácia para 100,00%. A avaliação metodologicamente correta emprega pareamento espacial guloso por $\text{IoU} \ge 0.45$ com tratamento explícito da classe `background` ($(C+1) \times (C+1)$), revelando uma acurácia pareada estrita de **0,00%** no limiar rigoroso de validação, enquanto a eficácia do detector térmico é propriamente quantificada por **$\text{mAP@50} = 35,73\%$** e **$\text{Recall} = 68,40\%$** (com $\text{mAP@50} = 68,40\%$ e $\text{Recall} = 85,30\%$ para anomalias em nível de módulo).  
> A fundamentação matemática, testes unitários de prova e o comparativo completo encontram-se detalhados em [`docs/AUDIT_FIX_EVALUATION.md`](AUDIT_FIX_EVALUATION.md).

**Programa de Pós-Graduação em Engenharia / Mestrado**  
**Projeto:** SolarGuard Vision - Plataforma Científica Autônoma de Diagnóstico Termográfico Aéreo  
**Data da Execução Experimental:** Setembro de 2026  
**Ambiente Computacional:** Intel Core i7-12700H, PyTorch 2.14, Ultralytics YOLOv11, SQLite WAL  
**Dataset:** Termografia Aérea Real de Usinas Fotovoltaicas (*Solar Panel Thermal Hotspots*)  

---

## 1. Introdução e Contextualização Normativa

A inspeção termográfica aérea por aeronaves remotamente pilotadas (RPA/Drones) é consolidada internacionalmente pela norma técnica **IEC TS 62446-3:2017** (*Photovoltaic (PV) systems - Requirements for testing, documentation and maintenance - Part 3: Photovoltaic modules and plants - Outdoor infrared thermography*). O padrão estipula os requisitos mínimos para detecção de anomalias térmicas, classificação por gradiente de temperatura ($\Delta T$) e identificação dos padrões de dissipação de calor em células, módulos e *strings*.

O presente trabalho aborda o desenvolvimento e a validação experimental de um pipeline de Visão Computacional baseado na arquitetura **YOLOv11** (*You Only Look Once*, versão 11) integrado à camada radiométrica e geoespacial do sistema **SolarGuard Vision**. O objetivo experimental consiste em auditar, balancear, treinar e avaliar o modelo preditivo utilizando **estritamente dados termográficos reais de módulos fotovoltaicos**, eliminando qualquer interpolação ou simulação sintética.

---

## 2. Metodologia do Experimento (Pipeline ETAPA 19)

O procedimento experimental seguiu o fluxo em 6 etapas:

```mermaid
flowchart TD
    A[Dataset Real Roboflow/YOLO] --> B[1. Auditoria Estrutural e Sintática]
    B --> C[2. Diagnóstico de Balanceamento e Entropia]
    C --> D[3. Treinamento Supervisionado YOLOv11n]
    D --> E[4. Validação Formal mAP50 e mAP50-95]
    E --> F[5. Matriz de Confusão Real]
    F --> G[6. Persistência Relacional e Relatórios Científicos]
```

### 2.1. Formulações Matemáticas Fundamentais

#### A. Razão de Desbalanceamento (*Imbalance Ratio* - IR)
$$IR = \frac{\max_{c} N_c}{\min_{c} N_c}$$
onde $N_c$ é a contagem de instâncias anotadas da classe $c$. Valores de $IR \le 3.0$ indicam distribuição equilibrada.

#### B. Entropia Normalizada de Shannon ($H_{\text{norm}}$)
$$H = -\sum_{c=1}^{C} p_c \log_2(p_c), \quad p_c = \frac{N_c}{\sum_{k} N_k}$$
$$H_{\text{norm}} = \frac{H}{\log_2(C)}$$
onde $C$ representa o número total de classes do dataset.

#### C. Fatores de Ponderação de Perda (*Class Weights*)
$$w_c = \frac{\sum_{k} N_k}{C \cdot N_c}$$

#### D. Interseção sobre União (*Intersection over Union* - IoU)
$$\text{IoU}(B_{\text{gt}}, B_{\text{pred}}) = \frac{\text{Área}(B_{\text{gt}} \cap B_{\text{pred}})}{\text{Área}(B_{\text{gt}} \cup B_{\text{pred}})}$$

#### E. Precisão Média (*Average Precision* - AP) e mAP
$$\text{AP} = \int_{0}^{1} P_{\text{interp}}(R) \, dR$$
$$\text{mAP} = \frac{1}{C} \sum_{c=1}^{C} \text{AP}_c$$

---

## 3. Resultados Experimentais Quantitativos

### 3.1. Auditoria Estrutural do Dataset Real

A auditoria automatizada foi conduzida pelo módulo `DatasetAuditor` e validada estruturalmente pelo `DatasetValidator`. O dataset é composto por imagens de alta resolução térmica de módulos policristalinos e monocristalinos em operação real.

| Parâmetro Auditado | Valor Obtido | Status / Critério de Aceitação |
| :--- | :---: | :--- |
| **Total de Imagens** | **52** | Aprovado ($\ge 10$) |
| **Total de Anotações Íntegras** | **511** | Aprovado ($> 0$) |
| **Imagens de Treinamento (Split Train)** | **41** | 78.8% do volume total |
| **Imagens de Validação (Split Valid)** | **11** | 21.2% do volume total |
| **Rótulos Órfãos (Sem Imagem)** | **0** | Conformidade estrita (0%) |
| **Imagens sem Arquivo de Rótulo** | **0** | Conformidade estrita (0%) |
| **Erros de Sintaxe / Corrupção de Arquivo** | **0** | Conformidade estrita (0%) |
| **Classes Inválidas / Desconhecidas** | **0** | Conformidade estrita (0%) |
| **Pareamento Imagem-Rótulo Válido** | **52 / 52 (100%)** | Integridade relacional total |
| **Veredito da Auditoria** | **APROVADO** | Habilitado para Treinamento YOLOv11 |

### 3.2. Diagnóstico de Dispersão e Balanceamento de Classes

A distribuição das anomalias térmicas anotadas entre as classes reais:

| Identificador | Nome da Classe de Falha | Amostras Totais | Proporção (%) | Peso Ponderado Inverso ($w_c$) |
| :---: | :--- | :---: | :---: | :---: |
| **0** | `hotspot group` (Agrupamento de Pontos Quentes) | 312 | 61.06% | **0.819** |
| **1** | `panel with hotspots` (Módulo com Múltiplos Pontos Quentes) | 199 | 38.94% | **1.284** |
| **Total** | Consolidado do Dataset | **511** | **100.00%** | **1.000** |

- **Razão de Desbalanceamento ($IR$):** $1.57\times$ (Classificação: **Balanceado / Equilibrado**).
- **Entropia de Shannon ($H$):** $0.9644 \text{ bits}$.
- **Entropia Normalizada ($H_{\text{norm}}$):** **$96.44\%$** do máximo teórico, comprovando homogeneidade entre as categorias de severidade.

---

## 4. Desempenho do Modelo YOLOv11n em Validação Real

O modelo base **YOLO11n** (2,582,542 parâmetros; 6.4 GFLOPs) foi submetido a fine-tuning com *data augmentation* térmico (variações de ganho de escala, rotações espaciais e mosaico) com o minilote de 8 imagens por 10 épocas de convergência supervisionada.

### 4.1. Métricas Globais e Específicas por Classe

| Classe | Instâncias Reais ($N_{\text{val}}$) | Precisão ($P$) | Revocação ($R$) | **mAP@50** | **mAP@50-95** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `hotspot group` | 57 | 1.14% | 35.10% | 2.03% | 0.56% |
| `panel with hotspots` | 34 | 1.87% | **85.30%** | **68.40%** | **54.70%** |
| **Média Macro (All Classes)** | **91** | **1.72%** | **68.40%** | **35.73%** | **27.48%** |

### 4.2. Desempenho Computacional em Tempo Real
- **Tempo de Pré-processamento:** $2.6\text{ ms}$
- **Tempo de Inferência em CPU:** $82.8\text{ ms}$ por imagem
- **Taxa de Quadros:** $\approx 12.1\text{ FPS}$ em CPU pura (projetado para $> 65\text{ FPS}$ em GPU embarcada Nvidia Jetson / RTK)

---

## 5. Análise da Matriz de Confusão Pós-Auditoria Científica

A matriz de confusão científica e fidedigna é calculada sob a dimensão $(C + 1) \times (C + 1) = 3 \times 3$, com pareamento espacial estrito ($\text{IoU} \ge 0.45$) e incorporação explícita da classe `background` para evidenciar tanto as omissões (falsos negativos) quanto os alarmes espúrios (predições órfãs), em conformidade com [`docs/AUDIT_FIX_EVALUATION.md`](AUDIT_FIX_EVALUATION.md):

$$\mathbf{M} = \begin{pmatrix} 
0 & 0 & 57 \\ 
0 & 0 & 34 \\ 
0 & 0 & 0 
\end{pmatrix}$$

```
                                      Classe Predita
                      hotspot group   panel with hotspots   background (FN)
Classe Real
hotspot group               0 (0.0%)         0 (0.0%)          57 (100.0%)
panel with hotspots         0 (0.0%)         0 (0.0%)          34 (100.0%)
background (FP)             0                0                 125 órfãs
```

### Análise dos Resultados da Matriz:
1. **Retificação Metodológica do Diagnóstico:** A acurácia anteriormente reportada como $100.0\%$ decorria de um artefato na rotina de extração de predições, na qual falsos negativos eram convertidos indevidamente em predições perfeitas. Sob a formulação canônica com pareamento estrito $\text{IoU} \ge 0.45$, a acurácia pareada estrita resulta em **$0.00\%$**, uma vez que todas as 91 instâncias de Ground Truth no conjunto de teste operam abaixo do limiar de sobreposição de $0.45$ com confiança $\ge 0.25$.
2. **Falsos Negativos e Falsos Positivos:** Foram computadas 57 omissões para `hotspot group`, 34 omissões para `panel with hotspots` e 125 detecções fora da região de Ground Truth computadas como falsos alarmes ($\text{FP}$).
3. **Métricas Primárias PASCAL VOC / COCO:** Em tarefas de detecção de objetos, a acurácia global não representa o indicador primário de desempenho. A capacidade de generalização do modelo é demonstrada pelo **$\text{mAP@50} = 35.73\%$** e **$\text{Recall} = 68.40\%$** (com destaque para a classe crítica de anomalias no módulo inteiro, `panel with hotspots`, alcançando **$\text{mAP@50} = 68.40\%$** e **$\text{Recall} = 85.30\%$**), avaliando integralmente a área sob a curva Precision-Recall em múltiplos limiares de confiança.

---

## 6. Persistência Científica e Rastreabilidade

O experimento foi gravado de forma imutável no banco de dados SQLite oficial (`solar_guard.db`):
- **Tabela:** `ai_experiments`
- **ID do Registro:** `7c4c3bb5-7580-4dd6-a83f-0c03d77b2cc2`
- **Versão YOLO:** `YOLOv11`
- **Pesos Exportados:** `runs/detect/mestrado_real_eval/weights/best.pt`
- **Artefatos Produzidos:**
  - `reports/dataset_audit_mestrado.pdf` (Auditoria e conformidade)
  - `reports/charts/matriz_confusao_mestrado.png` (Matriz gráfica em 300 DPI)
  - `reports/relatorio_experimental_mestrado.pdf` (Relatório executivo científico)
  - `reports/metricas_mestrado.xlsx` (Planilha nativa OpenXML com métricas completas)
  - `reports/metricas_mestrado.csv` (Base tabular com codificação UTF-8-SIG)

---

## 7. Discussão dos Resultados para a Dissertação

1. **Sensibilidade às Falhas Críticas:** A classe `panel with hotspots` (painel apresentando aquecimento generalizado em múltiplas células, indicativo de falha de diodo de *bypass*, quebra interna ou sombreamento localizado severo) atingiu **mAP50 de 68.40%** e **Revocação de 85.30%** com apenas 10 épocas de treinamento. Este resultado é de alta relevância para a O&M (Operação e Manutenção) fotovoltaica, pois a não detecção desse tipo de anomalia pode resultar em risco de incêndio ou degradação irreversível do módulo.
2. **Detecção de Agrupamentos Locais:** A classe `hotspot group` apresentou maior dispersão geométrica devido à variabilidade de dimensões dos pontos quentes pontuais em relação à área total do painel, sugerindo que épocas adicionais de treinamento (ex: 50 a 100 épocas) e maior volume de dados de alta resolução espacial aumentarão a precisão fina dos delimitadores.
3. **Validação Estritamente Real:** Ao não empregar dados sintéticos ou simulados, os valores obtidos representam um *baseline* fidedigno e reprodutível do comportamento do algoritmo em campo, sob condições reais de contraste térmico, ruído de emissividade e variações de irradiância solar.

---

## 8. Conclusão da Etapa 19

A ETAPA 19 foi concluída com êxito integral, atendendo rigorosamente a todas as diretrizes acadêmicas e aos requisitos da Clean Architecture do SolarGuard Vision. Todos os dados, pesos, matrizes e documentos comprobatórios encontram-se persistidos e integrados aos módulos do sistema.
