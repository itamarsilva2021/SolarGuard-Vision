# Manual do Usuário - SolarGuard Vision

**Versão da Aplicação:** 1.0.0 (Research Edition)  
**Público-Alvo:** Engenheiros Eletricistas, Pesquisadores, Operadores de RPA e Técnicos de O&M Solar  
**Ambiente Operacional:** Microsoft Windows 10 / 11 (64 bits)  

---

## 1. Introdução

O **SolarGuard Vision** é uma estação de trabalho científica e operacional para processamento de inspeções termográficas aéreas em usinas fotovoltaicas. O sistema automatiza desde a leitura dos arquivos brutos capturados por drones DJI até a emissão do laudo técnico pericial em PDF conforme a norma **IEC TS 62446-3**.

---

## 2. Acesso e Controle de Usuários (RBAC)

Ao inicializar o sistema, é exibida a tela de autenticação segura:

1. **Credenciais Padrão de Primeiro Acesso:**
   - **Administrador:** Usuário: `admin` | Senha: `Admin@SolarGuard2026!` (mínimo de 12 caracteres com criptografia Argon2id, recomendado alterar no primeiro login).
2. **Níveis de Acesso:**
   - **ADMIN:** Configurações globais, backup, licença e gestão de usuários.
   - **INSPECTOR:** Criação de projetos, importação de voos, processamento de IA e geração de laudos.
   - **VIEWER:** Modo consulta com acesso a dashboards, visualização de mapas e download de laudos.

---

## 3. Guia Operacional Passo a Passo

### Etapa 1: Cadastro de Cliente e Usina Fotovoltaica
1. No menu lateral, acesse **Projetos / Usinas**.
2. Clique no botão **Novo Projeto**.
3. Preencha os campos obrigatórios:
   - *Nome da Usina / Fazenda Solar*;
   - *Capacidade Instalada (kWp ou MWp)*;
   - *Cliente Proprietário*;
   - *Coordenadas de Referência (Latitude / Longitude)*;
   - *Modelo do Módulo Fotovoltaico e Tecnologia das Células*.
4. Clique em **Salvar**.

---

### Etapa 2: Importação e Processamento de Voo DJI
1. Navegue até a aba **Inspeções** e clique em **Nova Inspeção**.
2. Selecione a pasta onde foram salvos os arquivos do cartão SD do drone (suporte a fotos `.JPG`, `.TIF`, `.RJPEG` de câmeras DJI Matrice 4T / Zenmuse H20T).
3. O sistema valida automaticamente:
   - Existência de metadados EXIF/XMP radiométricos;
   - Precisão do posicionamento RTK (fixo/flutuante);
   - Altitude relativa em relação ao solo ($AGL$);
   - Temperatura ambiente e umidade relativa registradas no voo.
4. Clique em **Iniciar Processamento Automático**.

---

### Etapa 3: Auditoria de Dataset e Treinamento de IA
Caso o operador deseje calibrar o modelo YOLOv11 com um novo lote de anotações:
1. Acesse o menu **Inteligência Artificial > Auditoria de Dataset**.
2. Selecione o diretório do dataset no padrão YOLO (contendo `data.yaml`).
3. O sistema executa instantaneamente:
   - Verificação de imagens sem rótulo e rótulos órfãos;
   - Análise de consistência sintática e polígonos de segmentação;
   - Diagnóstico de balanceamento com cálculo de $IR$ (*Imbalance Ratio*) e Entropia de Shannon.
4. O relatório de auditoria é gerado em PDF (`reports/dataset_audit.pdf`).
5. Para treinar, acesse **Treinamento YOLOv11**, defina as épocas (ex: 10 a 50 épocas) e clique em **Treinar Modelo**. O melhor ponto de checagem será salvo como `best.pt`.

---

### Etapa 4: Análise Radiométrica e Detecção de Falhas
1. Na visualização da imagem termográfica:
   - Alterne entre as paletas de cores científicas: **Ironbow**, **Rainbow**, **White Hot**, **Black Hot** ou **Arctic**.
   - Ajuste os parâmetros de calibração física se necessário (emissividade $\varepsilon$, temperatura refletida do céu e distância de voo).
   - Clique em qualquer pixel para consultar a temperatura radiométrica calibrada pontual ($^\circ\text{C}$).
2. O sistema exibe as caixas de detecção da IA destacando:
   - Classe de falha identificada (`hotspot`, `hotspot group`, `panel with hotspots`, etc.);
   - Nível de confiança preditiva da rede neural;
   - Temperatura máxima na anomalia e temperatura de referência saudável;
   - Gradiente de temperatura diferencial ($\Delta T$);
   - Classificação de severidade normatizada (Baixa, Média, Alta ou Crítica).

---

### Etapa 5: Visualização no Mapa Geoespacial Interativo
1. Acesse a aba **Mapa da Usina**.
2. O mapa satélite exibe todos os módulos com os ortomosaicos e as falhas plotadas em suas posições geográficas exatas com marcadores coloridos por severidade:
   - **Verde:** Temperatura operacional normal;
   - **Amarelo:** Severidade Baixa ($\Delta T < 10^\circ\text{C}$);
   - **Laranja:** Severidade Média ($10^\circ\text{C} \le \Delta T < 20^\circ\text{C}$);
   - **Vermelho:** Severidade Alta ($20^\circ\text{C} \le \Delta T < 40^\circ\text{C}$);
   - **Púrpura / Vinho:** Severidade Crítica ($\Delta T \ge 40^\circ\text{C}$).
3. Ao clicar em um marcador, visualize os dados do módulo: *String*, *Fileira*, *Coluna*, foto da falha e recomendação técnica de reparo.

---

### Etapa 6: Emissão do Laudo Técnico Pericial
1. Na aba **Relatórios**, clique em **Gerar Laudo Técnico**.
2. Selecione as opções desejadas:
   - Inclusão de imagens térmicas em alta resolução;
   - Tabela consolidada de anomalias com severidade e coordenadas GPS;
   - Anotação de Responsabilidade Técnica (ART/CREA do engenheiro responsável).
3. Formatos de exportação disponíveis:
   - **PDF Pericial:** Documento diagramado para apresentação jurídica e contratual;
   - **Excel (.xlsx):** Planilha nativa multi-aba com todos os registros tabulares para o time de manutenção;
   - **CSV:** Dados brutos tabulares estruturados.
4. Clique em **Exportar**. Os arquivos são salvos na pasta `reports/`.
