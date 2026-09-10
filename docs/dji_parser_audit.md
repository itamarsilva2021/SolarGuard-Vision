# Auditoria Técnica de Integração e Metadados DJI (Matrice 4T)

**Documento:** `docs/dji_parser_audit.md`  
**Aplicação:** SolarGuard Vision  
**Versão da Análise:** 1.0  
**Data:** 10 de Setembro de 2026  
**Status:** Auditado / Planejamento da Etapa 12B  

---

## 1. Sumário Executivo

Esta auditoria detalha o estado técnico atual dos módulos de extração de metadados e telemetria da aplicação **SolarGuard Vision** (`DjiThermalParser` e `MetadataExtractor`), confrontando a implementação existente com a especificação oficial de telemetria, posicionamento e metadados radiométricos da aeronave não tripulada **DJI Matrice 4T (M4T)**.

O objetivo é mapear:
1. Conformidade com os padrões de arquivo do DJI Matrice 4T (R-JPEG e TIFF radiométrico).
2. Metadados **EXIF** (Exchangeable Image File Format) suportados e lacunas.
3. Metadados **XMP** (Extensible Metadata Platform) no namespace proprietário `drone-dji:`.
4. Coordenadas e navegação **GPS / GNSS**.
5. Posicionamento de alta precisão **RTK** (Real-Time Kinematic) e métricas de acurácia.
6. Tipos de **Altitude** (relativa ao ponto de decolagem, absoluta MSL, elipsoidal WGS84, RTK).
7. Parâmetros radiométricos de **Temperatura e Ambiente** definidos na controladora DJI Pilot 2.
8. Caracterização geométrica e fotogramétrica do **Modelo do Sensor**.

---

## 2. Visão Geral da Arquitetura do DJI Matrice 4T

O **DJI Matrice 4T (M4T)** é uma aeronave da linha Enterprise desenvolvida especificamente para inspeções industriais e termografia de alta precisão. Seu payload multissensor integra:
- **Câmera Térmica Radiométrica (LWIR):** Sensor microbolômetro VOx não refrigerado de 640 × 512 pixels, pitch de 12 μm, banda espectral de 8 a 14 μm, taxa de quadros de 30 Hz, sensibilidade térmica (NETD) ≤ 50 mK @ f/1.0, e DFOV de 61° (focal equivalente ~40 mm).
- **Câmera Grande Angular (Wide):** Sensor CMOS 1/1.32" de 48 MP.
- **Câmera Teleobjetiva (Zoom):** Sensor CMOS 1/2" de 12 MP com zoom híbrido de até 56×.
- **Módulo RTK Integrado:** Suporte a posicionamento centimétrico via rede NTRIP ou estação base DJI D-RTK 2.

Cada disparo termográfico gera um arquivo **R-JPEG** (ex: `DJI_YYYYMMDDHHMMSS_0001_T.JPG`), contendo em um único container o frame visual/processado, o stream térmico cru (raw thermal digital counts) em segmentos JPEG de aplicação (`APP3`/`APP4`), blocos de metadados padronizados **TIFF/EXIF** e o bloco XML extendido **XMP** com namespace `http://www.dji.com/drone-dji/1.0/`.

---

## 3. Matriz de Auditoria: Campos DJI Matrice 4T

A tabela a seguir consolida a auditoria item a item entre o padrão gerado pelo DJI Matrice 4T e a leitura executada pelo `MetadataExtractor` e `DjiThermalParser` atuais:

| Categoria | Campo DJI / Tag | Tipo / Unidade | Presente no M4T | Suportado Atual | Status / Impacto |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **EXIF** | `Make` | String ("DJI") | Sim | Parcial (via `tag_dji`) | Não exposto no DTO |
| **EXIF** | `Model` | String ("Matrice 4T") | Sim | Não | Ignorado no EXIF |
| **EXIF** | `DateTimeOriginal` | Timestamp ISO | Sim | **Sim** | Mapeado para `captured_at` |
| **EXIF** | `SubsecTimeOriginal` | Fração de segundo | Sim | Não | Perda de precisão sub-segundo |
| **EXIF** | `ImageWidth` / `Length` | Inteiro (pixels) | Sim | **Sim** | Lido via PIL `img.size` |
| **EXIF** | `FocalLength` | Float (mm) | Sim | Não | Necessário para GSD exato |
| **EXIF** | `FocalLengthIn35mm` | Inteiro (mm eq.) | Sim | Não | Ausente |
| **GPS** | `GPSLatitude` + `Ref` | DMS -> Graus Decimais | Sim | **Sim** | Convertido em `GeoCoordinate.latitude` |
| **GPS** | `GPSLongitude` + `Ref` | DMS -> Graus Decimais | Sim | **Sim** | Convertido em `GeoCoordinate.longitude` |
| **GPS** | `GPSAltitude` + `Ref` | Float (metros) | Sim | **Sim** | Mapeado para `GeoCoordinate.altitude_meters` |
| **GPS** | `GPSMapDatum` | String ("WGS-84") | Sim | Não | Assume implicitamente WGS84 |
| **GPS** | `GPSDOP` | Float (Dilution) | Sim | Não | Indicador de qualidade não lido |
| **RTK** | `drone-dji:RtkFlag` | Inteiro (0, 16, 50) | Sim | **NÃO** | **Crítico:** Não valida se fixou RTK |
| **RTK** | `drone-dji:RtkStdLat` | Float (metros) | Sim | **NÃO** | Desvio padrão da latitude ausente |
| **RTK** | `drone-dji:RtkStdLon` | Float (metros) | Sim | **NÃO** | Desvio padrão da longitude ausente |
| **RTK** | `drone-dji:RtkStdHgt` | Float (metros) | Sim | **NÃO** | Desvio padrão vertical ausente |
| **RTK** | `drone-dji:RtkDiffAge` | Float (segundos) | Sim | **NÃO** | Idade da correção diferencial ausente |
| **Altitude** | `drone-dji:RelativeAltitude` | Float (metros) | Sim | **Sim** | Mapeado em `flight_altitude_meters` |
| **Altitude** | `drone-dji:AbsoluteAltitude` | Float (metros MSL) | Sim | **NÃO** | Não capturado (crucial para relevo) |
| **Gimbal** | `drone-dji:GimbalPitchDegree` | Float (graus, -90 nadir)| Sim | **Sim** | Mapeado em `gimbal_pitch_degrees` |
| **Gimbal** | `drone-dji:GimbalYawDegree` | Float (graus, azimute)| Sim | **Sim** | Mapeado em `gimbal_yaw_degrees` |
| **Gimbal** | `drone-dji:GimbalRollDegree` | Float (graus) | Sim | **NÃO** | Assume 0.0 sem verificar roll |
| **Drone** | `drone-dji:FlightPitchDegree` | Float (graus) | Sim | **NÃO** | Ângulo de arfagem da aeronave ausente |
| **Drone** | `drone-dji:FlightRollDegree` | Float (graus) | Sim | **NÃO** | Ângulo de rolagem da aeronave ausente |
| **Drone** | `drone-dji:FlightYawDegree` | Float (graus, heading)| Sim | **NÃO** | Direção de voo da aeronave ausente |
| **Drone** | `drone-dji:Model` | String | Sim | **Sim** | Capturado como `drone_model` |
| **Drone** | `drone-dji:DroneSerialNumber` | String | Sim | **NÃO** | Rastreabilidade de frota ausente |
| **Sensor** | `drone-dji:CameraSerialNumber`| String | Sim | **NÃO** | Identificação da câmera ausente |
| **Sensor** | `drone-dji:CameraType` | String ("Thermal") | Sim | **NÃO** | Não valida se a imagem é do sensor T |
| **Sensor** | `drone-dji:CalibratedFocalLength` | Float (pixels) | Sim | **NÃO** | Calibração intrínseca de fábrica |
| **Sensor** | `drone-dji:CalibratedOpticalCenterX` | Float (pixels) | Sim | **NÃO** | Ponto principal x ausente |
| **Sensor** | `drone-dji:CalibratedOpticalCenterY` | Float (pixels) | Sim | **NÃO** | Ponto principal y ausente |
| **Sensor** | `drone-dji:DewarpData` | String (k1,k2,p1,p2,k3)| Sim | **NÃO** | Distorção de lente não modelada |
| **Temperatura** | `drone-dji:ThermalGainMode` | "HighGain" / "LowGain" | Sim | **NÃO** | **Crítico:** Faixa de ganho ignorada |
| **Temperatura** | `drone-dji:Emissivity` | Float (0.1 a 1.0) | Sim | **NÃO** | Assume default (0.95) sem ler XMP |
| **Temperatura** | `drone-dji:ReflectedTemperature` | Float (°C) | Sim | **NÃO** | Assume default (25.0) sem ler XMP |
| **Temperatura** | `drone-dji:Distance` | Float (metros) | Sim | **NÃO** | Usa altitude em vez do target distance |
| **Temperatura** | `drone-dji:RelativeHumidity` | Float (%) | Sim | **NÃO** | Assume default (50%) sem ler XMP |

---

## 4. Análise Aprofundada dos Pilares de Integração

### 4.1. EXIF (Exchangeable Image File Format)
- **Estado Atual:**
  - O método `MetadataExtractor.extract_exif()` abre a imagem via PIL e consulta `img._getexif()`.
  - Converte as tags numéricas via `TAGS` e o dicionário `GPSInfo` via `GPSTAGS`.
  - Extrai com sucesso: `width`, `height`, `DateTimeOriginal` (convertido em `datetime`), e tuplas de coordenadas GPS em DMS.
- **Lacunas Identificadas:**
  - Não extrai tags de lente cruciais para cálculo fotogramétrico automático (`FocalLength`, `FocalLengthIn35mmFilm`).
  - Não captura `Make` e `Model` do cabeçalho EXIF principal.
  - Não captura frações de segundo (`SubsecTimeOriginal`), o que impede a correlação exata de registros de telemetria RTK de alta frequência (5 Hz / 10 Hz).

### 4.2. XMP e Namespace `drone-dji:`
- **Estado Atual:**
  - O método `MetadataExtractor.extract_dji_xmp()` lê o arquivo binário cru procurando marcadores `<x:xmpmeta` e `</x:xmpmeta>`.
  - Executa expressões regulares simples no formato de atributo XML:
    ```python
    re.search(r'drone-dji:GimbalPitchDegree="?([+-]?\d+\.?\d*)"?', xmp_str)
    re.search(r'drone-dji:GimbalYawDegree="?([+-]?\d+\.?\d*)"?', xmp_str)
    re.search(r'drone-dji:RelativeAltitude="?([+-]?\d+\.?\d*)"?', xmp_str)
    re.search(r'drone-dji:Model="?([^"\s>]+)"?', xmp_str)
    ```
- **Fragilidades e Lacunas:**
  - **Sintaxe XML Alternativa:** No XMP gerado por diferentes versões do firmware do Matrice 4T / DJI Pilot 2, tags podem aparecer como nós XML `<drone-dji:GimbalPitchDegree>-90.0</drone-dji:GimbalPitchDegree>` ou com prefixos de namespace alternativos (como `dji:` em vez de `drone-dji:`). A busca atual falharia silenciosamente nesses casos, retornando `None`.
  - **Limitação de Campos:** Apenas 4 campos são lidos, ignorando mais de 20 tags disponíveis.

### 4.3. GPS e Georreferenciamento
- **Estado Atual:**
  - Extrai latitude, longitude e altitude elipsoidal via bloco `GPSInfo` padrão.
  - Converte corretamente coordenadas DMS (graus, minutos, segundos) para graus decimais, respeitando os hemisférios (`S`, `W` negativos).
  - Instancia o Value Object `GeoCoordinate` garantindo imutabilidade e validação de domínio.
- **Lacunas:**
  - Não verifica se as coordenadas provêm de fixação autônoma de GPS ou de solução diferencial RTK.

### 4.4. RTK (Real-Time Kinematic)
- **Estado Atual:**
  - **Ausente.** Não existe suporte para leitura ou validação de RTK na base atual.
- **Impacto no DJI Matrice 4T:**
  - O DJI Matrice 4T grava no XMP o campo `drone-dji:RtkFlag`:
    - `0`: Sem RTK (GPS autônomo comum, erro típico de 1.5 m a 3.0 m).
    - `16`: RTK Float (solução ambígua, precisão decimétrica ~0.3 m a 0.8 m).
    - `50`: RTK Fixed (solução inteira convergida, precisão centimétrica ~1.5 cm a 2.5 cm).
  - Além disso, grava os desvios padrão de acurácia `RtkStdLat`, `RtkStdLon` e `RtkStdHgt`.
  - **Risco:** Em inspeções solares de grande escala, mapear um hotspot com erro de 3 metros (sem RTK) pode atribuir a falha à string ou mesa vizinha. É indispensável identificar e alertar o nível de confiabilidade do RTK no relatório.

### 4.5. Altitude (Relativa vs. Absoluta vs. RTK)
- **Estado Atual:**
  - O sistema captura `drone-dji:RelativeAltitude` como `flight_altitude_meters` e `GPSAltitude` no `GeoCoordinate.altitude_meters`.
- **Lacunas:**
  - O Matrice 4T registra três conceitos distintos de altitude:
    1. `RelativeAltitude`: Altitude relativa em relação ao ponto de decolagem (Home Point). Essencial para cálculo de GSD (Ground Sample Distance) local e distância objeto-câmera.
    2. `AbsoluteAltitude`: Altitude da aeronave acima do geoide / nível médio do mar (MSL). Fundamental para modelos digitais de superfície (MDS) e correção barométrica.
    3. `RtkAltitude`: Altitude elipsoidal WGS84 de altíssima precisão fornecida pela antena GNSS do RTK.
  - A falta da distinção explícita no domínio pode gerar inconsistências quando o drone decola de um local em desnível em relação aos módulos fotovoltaicos.

### 4.6. Temperatura e Parâmetros Radiométricos
- **Estado Atual:**
  - Criamos na Etapa 11B o motor científico completo (`RadiometryEngine`, `EmissivityModel`, `ReflectedTemperatureModel`, `AtmosphericCompensation`, `CalibrationProfiles`).
  - No entanto, a extração de metadados em `DjiThermalParser.extract_metadata()` ainda define valores ambientais estáticos hardcoded:
    ```python
    emissivity = 0.95
    reflected_temp_celsius = 25.0
    ambient_temp_celsius = 28.0
    relative_humidity = 0.50
    ```
- **Conformidade com Matrice 4T:**
  - O operador em campo insere a emissividade, distância, temperatura refletida e umidade relativa diretamente no aplicativo DJI Pilot 2 antes do voo.
  - O DJI Matrice 4T grava esses valores no cabeçalho XMP/DIRP:
    - `drone-dji:Emissivity`
    - `drone-dji:ReflectedTemperature`
    - `drone-dji:Distance`
    - `drone-dji:RelativeHumidity`
    - `drone-dji:ThermalGainMode` ("HighGain" ou "LowGain")
  - **Benefício:** A extração desses parâmetros reais evitará o uso de estimativas e alimentará automaticamente a camada científica desenvolvida na Etapa 11B.

### 4.7. Modelo do Sensor e Geometria Óptica
- **Estado Atual:**
  - O sistema registra resolução padrão 640×512 e `drone-dji:Model`.
- **Lacunas:**
  - O Matrice 4T possui parâmetros de calibração geométrica de fábrica embutidos no XMP (`CalibratedFocalLength`, `CalibratedOpticalCenterX`, `CalibratedOpticalCenterY`, `DewarpData`).
  - A câmera térmica é nomeada como `CameraType="Thermal"` ou sufixo de arquivo `_T.JPG` (enquanto o sensor visual é `_W.JPG` e zoom é `_Z.JPG`). Atualmente não há validação se a imagem importada é de fato o canal térmico ou o visual de apoio.

---

## 5. Matriz de Conformidade com o DJI Matrice 4T

| Módulo / Requisito | Nível de Conformidade | Avaliação |
| :--- | :---: | :--- |
| **Identificação de Arquivo M4T** | 80% | Identifica arquivos `.JPG` com assinatura DJI e extensões TIFF. |
| **GPS WGS84 Básico** | 95% | Extração robusta de latitude, longitude e altitude elipsoidal. |
| **Orientação Espacial (Gimbal)** | 70% | Extrai Pitch e Yaw; ausência de Roll e atitude da aeronave. |
| **Qualidade e Fixação RTK** | **0%** | **Inexistente.** Não valida status RTK (Fixed/Float/Single). |
| **Diferenciação de Altitudes** | 50% | Lê altitude relativa, mas ignora altitude ortométrica absoluta. |
| **Parâmetros Radiométricos DJI**| 25% | Utiliza defaults fixos em vez de ler as tags gravadas pelo Pilot 2. |
| **Modo de Ganho Térmico** | **0%** | Não diferencia High Gain (-20 a 150°C) de Low Gain (0 a 500°C). |
| **Calibração Óptica e GSD** | 40% | Utiliza FOV e focal teóricos sem ler os parâmetros calibrados. |

---

## 6. Riscos Identificados

1. **Risco de Falsa Certeza Cartográfica:**
   - Sem a verificação de `RtkFlag`, a aplicação pode classificar imagens capturadas com erro métrico de GPS comum como georreferenciadas com alta precisão, gerando incerteza na localização de módulos defeituosos no mapa e no relatório.
2. **Risco de Divergência Radiométrica em Campo:**
   - Se o operador configurou no DJI Pilot 2 emissividade de 0.85 ou temperatura refletida de 10°C e a aplicação adotar valores padrão hardcoded (0.95 e 25°C), a temperatura absoluta calculada divergirá da observada em campo pelo piloto.
3. **Risco de Troca de Canal de Imagem:**
   - Sem validar `CameraType` ou sufixo `_T.JPG`, o usuário pode acidentalmente carregar a foto do sensor RGB Wide (`_W.JPG`) no pipeline térmico, causando falhas de interpretação ou mapas de calor incorretos.
4. **Risco de Falha na Leitura de XMP Não Padronizado:**
   - A dependência de regex rígido de atributo XML (`attribute="..."`) falha em formatos de nó XML aberto (`<node>...</node>`) presentes em firmwares atualizados do M4T.

---

## 7. Plano de Implementação (Proposta para Etapa 12B)

A implementação das correções será estruturada respeitando Clean Architecture, mantendo total compatibilidade retroativa e sem alterar interfaces públicas:

### Fase 1: Enriquecimento do Objeto de Valor de Telemetria e DTOs
- Criar ou enriquecer o VO `RtkStatus` (com enum `RtkFixType`: `NONE`, `FLOAT`, `FIXED`, e métricas de desvio padrão em cm).
- Expandir `ThermalMatrixMeta` para incluir `gain_mode` ("HighGain" / "LowGain"), `rtk_flag`, `absolute_altitude_meters` e desvios RTK.

### Fase 2: Parser Especializado `DjiMetadataParser`
- Criar um parser XMP baseado em XML DOM / ElementTree robusto (com fallback para regex multiformato), capaz de ler nós e atributos indistintamente.
- Extrair tags completas:
  - `drone-dji:RtkFlag`, `RtkStdLat`, `RtkStdLon`, `RtkStdHgt`
  - `drone-dji:AbsoluteAltitude`
  - `drone-dji:Emissivity`, `drone-dji:ReflectedTemperature`, `drone-dji:Distance`, `drone-dji:RelativeHumidity`
  - `drone-dji:ThermalGainMode`
  - `drone-dji:FlightPitchDegree`, `FlightRollDegree`, `FlightYawDegree`
  - `drone-dji:CameraType`, `drone-dji:CameraSerialNumber`

### Fase 3: Integração com a Camada Radiométrica Científica (Etapa 11B)
- Conectar os metadados reais extraídos do XMP diretamente aos modelos criados na Etapa 11B (`EmissivityModel`, `AtmosphericCompensation`, `CalibrationProfiles`), selecionando automaticamente o perfil Planck correspondente ao `gain_mode` do sensor.

---

## 8. Conclusão da Auditoria

A camada atual de ingestão de imagens possui uma base funcional estável para extração de GPS e orientação de gimbal, mas opera de forma simplificada em relação ao potencial e às especificações reais do **DJI Matrice 4T**. 

A integração completa das tags **RTK**, **Altitudes Diferenciadas** e **Parâmetros Radiométricos Nativos** elevará o **SolarGuard Vision** ao padrão ouro de inspeções solares industriais, garantindo precisão submétrica na localização de anomalias e exatidão termodinâmica em conformidade com as normas **IEC TS 62446-3** e **ISO 18434-1**.
