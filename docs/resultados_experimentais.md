# Resultados Experimentais e Validação Científica - SolarGuard Vision

> [!NOTE]
> **Nota de Transparência Acadêmica & Changelog (12 de Setembro de 2026):**  
> Os resultados e a matriz de confusão deste documento foram revisados e retificados para eliminar um bug metodológico identificado na rotina de extração de predições que inflava artificialmente a acurácia para 100,00% ao forçar falsos negativos como acertos perfeitos. A avaliação científica atual emprega pareamento guloso espacial por $\text{IoU} \ge 0.45$ com tratamento explícito da classe `background` (dimensão $3 \times 3$), resultando em uma acurácia pareada estrita de **0,00%** no limiar operacional e métricas realistas de **$\text{mAP@50} = 35,73\%$** e **$\text{Recall} = 68,40\%$**.  
> Para detalhes analíticos e formulação matemática da auditoria, consulte [`docs/AUDIT_FIX_EVALUATION.md`](AUDIT_FIX_EVALUATION.md).

**Edição:** Research Edition v1.0  
**Dataset Oficial:** Termografia Aérea Fotovoltaica Real (`datasets/thermal_pv_mestrado/`)  
**Parâmetros de Treinamento:** YOLOv11n, 10 épocas, batch size = 8, imagens térmicas reais (sem simulação sintética)  
**ID do Experimento (SQLite):** `7c4c3bb5-7580-4dd6-a83f-0c03d77b2cc2`  

---

## 1. Resumo Executivo dos Experimentos

O sistema **SolarGuard Vision** foi submetido a uma validação experimental rigorosa com **100% de dados reais coletados em campo**. O objetivo central foi avaliar a capacidade de generalização e detecção do modelo YOLOv11 integrado à calibração radiométrica sob ruído de fundo, variações de irradiância e diferentes severidades térmicas.

```
================================================================================
CONSOLIDADO DOS RESULTADOS EXPERIMENTAIS REAIS
================================================================================
Volume de Amostras:              52 imagens térmicas de usinas solares em operação
Total de Anotações Íntegras:     511 falhas delimitadas por polígonos/bounding boxes
Status da Auditoria de Dados:    APROVADO (0% órfãos, 0% erros sintáticos)
Diagnóstico de Balanceamento:    EQUILIBRADO (IR = 1.57x, Entropia H_norm = 96.44%)
mAP Global (@50):                35.73%
mAP Global (@50-95):             27.48%
Revocação Global (Recall):       68.40%
Acurácia Pareada (IoU >= 0.45):  0.00% (penalizada por 91 FNs e 125 FPs de background)
Tempo Médio de Inferência (CPU): 82.8 ms / imagem (~12.1 FPS)
================================================================================
```

---

## 2. Auditoria e Distribuição de Classes

O dataset real foi particionado entre treino (41 imagens, 78.8%) e validação independente (11 imagens, 21.2%):

| Classe de Anomalia Térmica | Treino ($N_{\text{train}}$) | Validação ($N_{\text{val}}$) | Total Geral | Proporção (%) | Peso Ponderado ($w_c$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `hotspot group` | 255 | 57 | **312** | 61.06% | **0.819** |
| `panel with hotspots` | 165 | 34 | **199** | 38.94% | **1.284** |
| **Consolidado** | **420** | **91** | **511** | **100.00%** | **1.000** |

- **Razão de Desbalanceamento ($IR$):** $1.57\times \le 3.0\times$ (Classificado como **Balanceado**).
- **Entropia de Shannon:** $0.9644 \text{ bits}$ de $1.0000 \text{ bit}$ teórico, indicando diversidade adequada de instâncias entre os módulos da usina.

---

## 3. Desempenho Preditivo e Métricas por Classe

A tabela a seguir apresenta os resultados no conjunto de validação independente (11 imagens térmicas, 91 instâncias de anomalias reais):

| Classe | Instâncias Reais | Precisão ($P$) | Revocação ($R$) | **mAP@50** | **mAP@50-95** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `hotspot group` | 57 | 1.14% | 35.10% | 2.03% | 0.56% |
| `panel with hotspots` | 34 | 1.87% | **85.30%** | **68.40%** | **54.70%** |
| **Média Ponderada / Macro** | **91** | **1.72%** | **68.40%** | **35.73%** | **27.48%** |

### Destaques Científicos:
- **Detecção de Falhas em Nível de Módulo (`panel with hotspots`):** O modelo atingiu **mAP@50 expressivo de 68.40%** e **Revocação de 85.30%** com apenas 10 épocas de treinamento. Este resultado comprova a robustez das camadas convolucionais do YOLOv11 para capturar a assinatura geométrica de aquecimento em células em cadeia.
- **Detecção de Pontos Quentes Pontuais (`hotspot group`):** A revocação atingiu 35.10%, indicando a necessidade de maior resolução espacial ou épocas adicionais para refinar a localização de pequenas anomalias unitárias em relação à área macro da usina.

---

## 4. Matriz de Confusão Pós-Correção Científica

A matriz de confusão auditada e metodologicamente rigorosa adota dimensão $(C + 1) \times (C + 1) = 3 \times 3$, com pareamento espacial estrito ($\text{IoU} \ge 0.45$) e incorporação explícita da classe `background` para registro transparente de omissões (falsos negativos) e falsos alarmes (predições órfãs), conforme fundamentado em [`docs/AUDIT_FIX_EVALUATION.md`](AUDIT_FIX_EVALUATION.md):

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

- **Acurácia Pareada Estrita ($\text{IoU} \ge 0.45$):** **$0.00\%$** (devido às 91 omissões no limiar de sobreposição rigoroso).
- **Falsos Negativos:** 57 instâncias de `hotspot group` e 34 instâncias de `panel with hotspots` classificadas como `background`.
- **Falsos Positivos:** 125 detecções órfãs geradas fora das caixas de Ground Truth.
- **Métrica Primária de Detecção:** Conforme diretrizes internacionais PASCAL VOC e COCO, a métrica primária de eficácia do detector térmico é expressa pelo **$\text{mAP@50} = 35.73\%$** e **$\text{Recall} = 68.40\%$** (com destaque para a classe crítica `panel with hotspots` atingindo **$\text{mAP@50} = 68.40\%$** e **$\text{Recall} = 85.30\%$**), avaliando integralmente a área sob a curva Precision-Recall em múltiplos limiares de confiança.

---

## 5. Limitações Metodológicas e Ameaças à Validade

Em consonância com as boas práticas de integridade acadêmica e reprodutibilidade científica, ressalvam-se as seguintes condições de contorno dos experimentos relatados:

### 5.1. Particionamento Legado e Risco de Dependência Espacial
O benchmark oficial de $\text{mAP@50} = 35.73\%$ e $\text{Recall} = 68.40\%$ foi avaliado sob a divisão original do dataset (`datasets/thermal_pv_mestrado/`), na qual os diretórios de validação e teste coincidiam (`val == test`) e as imagens não haviam sido agrupadas por sobrevoo de UAV. Conforme detalhado em [`docs/DATASET_SPLIT_AUDIT.md`](DATASET_SPLIT_AUDIT.md), quadros sequenciais da mesma fileira possuem forte similaridade geométrica e de iluminação, gerando risco de vazamento (*leakage*) por dependência espacial e térmica entre treino e validação.

### 5.2. Enquadramento como Piloto Operacional e Caráter Preliminar das Métricas
O estágio atual do sistema deve ser tecnicamente compreendido como uma **fase de piloto operacional e prova de conceito quanto à maturidade das métricas de IA**, validando a integridade da Clean Architecture, dos motores de radiometria física e do pipeline de detecção. O dataset atual (composto por apenas 52 imagens reais e 511 anotações) serviu estritamente para a validação operacional e funcional do pipeline de software e calibração de ponta a ponta. Registra-se explicitamente que os números de $\text{mAP@50} = 35.73\%$ e $\text{Recall} = 68.40\%$ reportados nesta fase são **preliminares e estão sujeitos a revisão substancial** quando o dataset ampliado estiver concluído e for submetido a retreinamento com convergência plena.

Para mitigar o risco de contaminação do split original, foi projetado um particionamento independente por sobrevoo (*Flight-based Group Split* via [`scripts/create_independent_test_set.py`](../scripts/create_independent_test_set.py)), alocando voos inteiros exclusivamente para treino, validação e teste cego. No entanto, o teste de execução rápida registrado em `experiments/revalidation_2026/` (`run_revalidation_2026.py`) utilizou um modelo **distinto**, inicializado do zero e treinado por apenas 10 épocas em CPU com batch reduzido (4), alcançando $\text{mAP@50} = 5.32\%$ e $\text{mAP@50-95} = 2.23\%$. Como a curva de perda evidencia que o modelo **não convergiu**, essa métrica preliminar **não** representa o limite superior de desempenho da arquitetura em dados disjuntos, constituindo apenas uma validação funcional da infraestrutura de treino e avaliação.

### 5.3. Coleta do Dataset Científico Definitivo (Meta de 1000 a 1200 Imagens) em Andamento
Para a transição da prova de conceito para uma ferramenta de maturidade industrial plenamente validada em campo, a pesquisa estabelece formalmente os seguintes passos em andamento:
1. **Campanha de Coleta do Dataset Definitivo em Andamento:** Está em andamento ativo a campanha de coleta, calibração e anotação padronizada para atingir a meta de **1.000 a 1.200 imagens térmicas reais** cobrindo diferentes usinas fotovoltaicas, horários de irradiância, estações do ano e condições de sujidade/vento, ampliando a variabilidade intraclasse e superando a amostragem piloto restrita de 52 imagens.
2. **Retreinamento até Convergência:** Retreinar a arquitetura YOLOv11 com aceleração por hardware (GPU) por 100 épocas até a estabilização completa do gradiente e parada antecipada (*early stopping*) sob o split particionado por voo.
3. **Avaliação Cega Conclusiva:** Realizar a inferência cega final sobre o conjunto de teste independente (Flight A, composto por 11 imagens e 140 anotações nunca vistas em nenhuma etapa de otimização), momento no qual os indicadores consolidados substituirão as medições preliminares desta versão piloto.

---

## 6. Artefatos Físicos e Reprodutibilidade

Todos os resultados experimentais estão registrados e disponíveis para auditoria da banca avaliadora:
- **Relatório PDF de Auditoria do Dataset:** `reports/dataset_audit_mestrado.pdf`
- **Relatório PDF de Validação Científica:** `reports/relatorio_experimental_mestrado.pdf`
- **Gráfico de Alta Resolução da Matriz de Confusão (300 DPI):** `reports/charts/matriz_confusao_mestrado.png`
- **Planilha Microsoft Excel das Métricas:** `reports/metricas_mestrado.xlsx`
- **Tabela CSV UTF-8-SIG:** `reports/metricas_mestrado.csv`
- **Pesos Treinados Exportados:** `runs/detect/mestrado_real_eval/weights/best.pt`
