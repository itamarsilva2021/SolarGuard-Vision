# Auditoria Técnica de Radiometria e Processamento Térmico — SolarGuard Vision

**Data da Auditoria:** 10/09/2026  
**Escopo:** Avaliação da fidelidade radiométrica, leitura de matrizes térmicas por pixel, decodificação de formatos (R-JPEG, TIFF) e compatibilidade com o sensor térmico do drone **DJI Matrice 4T**.  
**Status do Código:** Análise estática e dinâmica sem alteração de código-fonte.  

---

## 1. Estado Atual da Implementação

A camada de imagem e radiometria do SolarGuard Vision está estruturada principalmente em:
- [`src/infrastructure/imaging/dji_thermal_parser.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/imaging/dji_thermal_parser.py)
- [`src/infrastructure/imaging/metadata_extractor.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/imaging/metadata_extractor.py)
- [`src/infrastructure/imaging/preview_generator.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/imaging/preview_generator.py)
- [`src/infrastructure/thermal/thermal_processor.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/thermal/thermal_processor.py)
- [`src/infrastructure/thermal/thermal_analyzer.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/thermal/thermal_analyzer.py)

### 1.1 Como as imagens térmicas estão sendo carregadas
O fluxo de entrada passa pelo método `DjiThermalParser.extract_temperature_matrix(file_path)`:
1. **TIFF (.tif, .tiff):** Carregado via `cv2.imread(str(file_path), cv2.IMREAD_UNCHANGED)`.
   - Se os dados forem `uint16`, invoca o método privado `_convert_uint16_to_celsius()`.
2. **JPEG (.jpg, .jpeg):** Invoca `_extract_dji_rjpeg_payload(file_path)`.
   - Caso retorne `None`, executa um *fallback sintético* lendo em escala de cinza 8-bit (`cv2.IMREAD_GRAYSCALE`).
   - Normaliza os valores 0–255 linearmente para uma faixa estimada fixa de **25.0°C a 75.0°C** (`25.0 + (gray / 255.0) * 50.0`).

### 1.2 Análise da Leitura Real de Temperatura por Pixel
| Formato de Imagem | Leitura Real por Pixel? | Mecanismo Empregado |
| :--- | :---: | :--- |
| **TIFF Radiométrico 16-bit** | **SIM (Real/Direta)** | Converte valores brutos do sensor em centi-Kelvin ($T_{\text{cK}} / 100 - 273.15$) ou deci-Kelvin ($T_{\text{dK}} / 10 - 273.15$). |
| **TIFF 8-bit / Monocromático** | **NÃO (Estimada)** | Mapeamento linear sintético para faixa de 20°C–80°C. |
| **DJI R-JPEG (Matrice 4T)** | **NÃO (Estimada)** | **Lacuna crítica:** O método `_extract_dji_rjpeg_payload` detecta apenas a assinatura `b"DJI"`, executa `pass` e retorna `None`. Em seguida, o parser recorre à interpolação da luminância visual de 8 bits (25°C–75°C). |

### 1.3 Análise do Suporte a Metadados Térmicos DJI
- **Telemetria de Voo e Orientação de Câmera:** **100% Suportado e Funcional.**
  - `MetadataExtractor.extract_dji_xmp()` extrai via Expressões Regulares os blocos XMP proprietários:
    - `drone-dji:GimbalPitchDegree`
    - `drone-dji:GimbalYawDegree`
    - `drone-dji:RelativeAltitude`
    - `drone-dji:Model`
  - `MetadataExtractor.extract_exif()` extrai coordenadas GPS WGS84 e timestamp.
- **Parâmetros Radiométricos Ambientais do Sensor:** **Estáticos / Hardcoded.**
  - Emissividade (0.95), Temperatura Refletida (25.0°C), Temperatura Ambiente (28.0°C) e Umidade (50%) são preenchidos com valores padrão e não extraídos do cabeçalho binário radiométrico DJI.

---

## 2. Aderência ao DJI Matrice 4T

A câmera térmica integrada do **DJI Matrice 4T** possui as seguintes especificações industriais:
- **Resolução Térmica:** $640 \times 512$ pixels.
- **Banda Espectral:** LWIR (Long-Wave Infrared, $8 \text{ a } 14\,\mu\text{m}$).
- **Taxa de Quadros:** 30 Hz.
- **Sensibilidade Térmica (NETD):** $\le 50\,\text{mK} @ f/1.0$.
- **Formato Radiométrico Oficial:** **DJI R-JPEG**. O arquivo JPEG padrão contém um fluxo térmico comprimido embutido em segmentos proprietários (geralmente nos marcadores JPEG `APP3` / `APP4` ou metadados de fabricante `DIRP` - DJI Infrared Raw Processing).
- **Faixas de Ganho:**
  - *High Gain:* $-20^\circ\text{C} \text{ a } 150^\circ\text{C}$ (maior sensibilidade, ideal para inspeção solar fotovoltaica).
  - *Low Gain:* $0^\circ\text{C} \text{ a } 500^\circ\text{C}$.

### Diagnóstico de Aderência
O sistema atual **reconhece o arquivo R-JPEG como JPG**, extrai suas coordenadas geográficas e ângulos de voo perfeitamente, porém **não descompacta o canal LWIR bruto de 16 bits**. Consequentemente:
- A matriz térmica gerada reflete a intensidade visual da imagem JPEG renderizada com colormap pelo drone, e não a temperatura física pontual captada pelo bolômetro.
- Se a imagem do drone foi gravada com paleta "White Hot" ou "Ironbow", a conversão em escala de cinza distorce a curva real de temperatura radiométrica.

---

## 3. Riscos Identificados

1. **Falso Diagnóstico de Severidade IEC TS 62446-3:**
   - Como o $\Delta T$ depende de subtrações precisas ($T_{\text{max}} - T_{\text{ref}}$), estimar temperatura a partir de luminância de 8 bits comprimida por JPEG (com perdas por artefatos de compressão DCT) introduz erros de $\pm 3^\circ\text{C}$ a $\pm 10^\circ\text{C}$, podendo classificar um defeito Médio como Crítico ou vice-versa.
2. **Incompatibilidade com Paletas Coloridas de Voo:**
   - Se o operador configurou o drone Matrice 4T para gravar na tela com paleta *Ironbow* ou *Rainbow*, a conversão de OpenCV `cv2.IMREAD_GRAYSCALE` calcula pesos ponderados de canais RGB ($0.299R + 0.587G + 0.114B$), que **não correspondem à escala monotônica de temperatura**, tornando os dados térmicos incorretos.
3. **Laudos Periciais Contestáveis:**
   - Laudos de engenharia emitidos sem a leitura da matriz radiométrica original do fabricante perdem validade jurídica e técnica em perícias de garantia de módulos fotovoltaicos.

---

## 4. Lacunas Técnicas Detalhadas (Gaps)

| ID | Componente | Lacuna Identificada | Impacto |
| :---: | :--- | :--- | :--- |
| **GAP-01** | `DjiThermalParser` | `_extract_dji_rjpeg_payload` está em formato stub (`pass` / `return None`). | Imagens R-JPEG caem obrigatoriamente no fallback de 8-bits. |
| **GAP-02** | `DjiThermalParser` | Falta integração com o desempacotador oficial **DJI Thermal SDK (DIRP)** ou decodificador do container térmico R-JPEG. | Ausência de leitura do mapa de $640 \times 512$ em 16-bit nativo. |
| **GAP-03** | `MetadataExtractor` | Parâmetros de calibração atmosférica (emissividade, distância real, umidade, reflexão) não são lidos dos metadados radiométricos do drone. | Impossibilidade de aplicar correções radiométricas finas da atmosfera. |
| **GAP-04** | `ThermalProcessor` | Suporte apenas a TIFF 16-bit padrão; falta tratamento específico de TIFFs radiométricos exportados pelo DJI Thermal Analysis Tool. | Restrição ao processar arquivos exportados por softwares terceiros. |

---

## 5. Plano de Correção e Evolução (Roadmap de Radiometria)

Para elevar a radiometria do SolarGuard Vision ao estado de arte profissional, propõe-se um plano em 3 etapas sucessivas:

### Fase 1: Implementação de Decodificador R-JPEG Nativo em Python
- Implementar a extração do fluxo binário de 16 bits contido nos marcadores `APP3`/`APP4` do JPEG do Matrice 4T sem depender de binários externos:
  - Localização do cabeçalho binário `DJI` e do bloco bruto de dados térmicos comprimidos ou lineares.
  - Conversão dos valores brutos do sensor em temperaturas absolutas calibradas utilizando a equação de calibração radiométrica de Planck.
  - Manter o fallback atual de 8 bits exclusivamente para imagens ópticas ou térmicas não-radiométricas de demonstração.

### Fase 2: Suporte ao DJI Thermal SDK Oficial (Wrapper DIRP)
- Criar um adaptador de infraestrutura (`DjiThermalSdkAdapter`):
  - Comunicação via `ctypes` com a biblioteca nativa do fabricante (`libdirp.dll` no Windows x64).
  - Capacidade de ajustar dinamicamente parâmetros ambientais:
    - Emissividade do vidro fotovoltaico (0.90 – 0.96).
    - Distância do alvo (obtida diretamente da altitude de voo do XMP).
    - Umidade relativa e temperatura ambiente.
  - Extração de matriz float32 nativa calibrada com precisão de $\pm 0.1^\circ\text{C}$.

### Fase 3: Validação com Dataset Radiométrico Real
- Criar suíte de testes de integração com amostras autênticas do DJI Matrice 4T:
  - Verificação de dimensões exatas ($640 \times 512$).
  - Validação de faixa física plausível (ex: painéis a $30^\circ\text{C} \dots 95^\circ\text{C}$).
  - Verificação da preservação de metadados durante todo o ciclo de vida (banco de dados $\to$ análise de $\Delta T$ $\to$ mapa $\to$ laudo PDF).

---

## 6. Conclusão da Auditoria

O SolarGuard Vision possui uma arquitetura perfeitamente preparada para radiometria profissional (interfaces `IThermalParser`, `ThermalMatrixMeta`, `ThermalMetrics` e cálculos normativos IEC completos). O gargalo reside unicamente na etapa de **desempacotamento do payload térmico do R-JPEG**. 

A infraestrutura atual não precisa ser reescrita; a interface pública `extract_temperature_matrix(file_path)` permanecerá idêntica, permitindo a substituição do método de extração sem quebrar nenhum módulo posterior (Clean Architecture & Open/Closed Principle preservados).
