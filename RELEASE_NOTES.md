# Notas de Lançamento (Release Notes)

## SolarGuard Vision v1.0.1 (Security Hardening & Scientific Audit Edition)
**Data de Publicação:** 12 de Setembro de 2026  
**Build:** 1.0.1-audit+20260912  
**Status:** Versão Homologada com Auditoria Científica e Hardening de Segurança  

---

### 🌟 Destaques da Versão v1.0.1

1. **Correção Metodológica na Avaliação Científica de IA:**
   - Eliminação da anomalia metodológica que forçava falsos negativos como predições perfeitas e inflava a acurácia para 100,00%.
   - Implementação do pareamento guloso com limiar estrito de sobreposição espacial ($\text{IoU} \ge 0.45$) e matriz de confusão $3 \times 3$ com classe explícita `background`.
   - Retificação transparente: a acurácia pareada estrita é de **0,00%** (sob penalização estrita de omissões espaciais), enquanto o desempenho do detector é referenciado pelas métricas primárias internacionais PASCAL VOC/COCO: **$\text{mAP@50} = 35.73\%$** e **$\text{Recall} = 68.40\%$** (com destaque para a classe crítica de módulo `panel with hotspots` atingindo **$\text{mAP@50} = 68.40\%$** e **$\text{Recall} = 85.30\%$**).
   - Documentação de auditoria completa registrada em [`docs/AUDIT_FIX_EVALUATION.md`](docs/AUDIT_FIX_EVALUATION.md).

2. **Migração de Autenticação para Argon2id (RFC 9106):**
   - Adoção de **Argon2id** como algoritmo padrão de hash de senhas (64 MiB RAM, 3 iterações, 4 lanes paralelas, sal criptográfico de 16 bytes).
   - Implementação de política de segurança com tamanho mínimo de **12 caracteres**.
   - Migração transparente e automática: hashes legados PBKDF2-HMAC-SHA256 são convertidos para Argon2id no momento do login bem-sucedido.

3. **Segregação Criptográfica de Chaves Ed25519 (RFC 8032):**
   - Separação completa e estrita entre as autoridades de **Licenciamento** e de **Atualização de Software** (uso de pares de chaves assimétricas independentes).
   - Expulso absoluto de chaves privadas do repositório do cliente: carregamento via variável de ambiente `SOLARGUARD_LICENSE_PRIV_KEY` ou cofre de segredos.
   - Saneamento do histórico do Git com `git-filter-repo`, eliminando chaves expostas e protegendo ferramentas de servidor no `.gitignore`.

4. **Blindagem do Mecanismo de Atualização (`UpdateManager`):**
   - Restrição estrita de downloads a conexões criptografadas **HTTPS** com TLS em ambiente de produção.
   - Bloqueio automático de `http://`, `file://` e caminhos locais/UNC, com suporte a `allow_local_source=True` restrito a testes automatizados.
   - Validação imediata de integridade via digest SHA-256 e proteção pré-execução anti-TOCTOU.

5. **Engenharia de Software e Testes:**
   - **274 Testes Automatizados** cobrindo todas as camadas (100% de aprovação).
   - Ambiente reprodutível com `uv.lock`.

---

## SolarGuard Vision v1.0 (Research Edition)
**Data de Publicação:** 10 de Setembro de 2026  
**Build:** 1.0.0-research+20260910  
**Status:** Versão Científica Inicial para Dissertação de Mestrado  

---

### 🌟 Destaques da Versão v1.0

1. **Camada Científica de Radiometria Físico-Matemática:**
   - Implementação da equação de Planck inversa com calibração de fábrica por perfis de câmera.
   - Modelo de atenuação por transmitância atmosférica ($\tau_{\text{atm}}$) em função da umidade relativa e distância de voo.
   - Modelo de emissividade angular de Fresnel com alerta para ângulos de visada superiores a $60^\circ$.
   - Modelo de temperatura aparente refletida do céu baseado nas equações de Swinbank e Berdahl.

2. **Integração Completa com Drones DJI Matrice 4T:**
   - Leitura e decodificação avançada de metadados EXIF e XMP.
   - Suporte nativo a coordenadas RTK (centimétricas) e altitude relativa ($AGL$).
   - Extração da matriz radiométrica bruta a partir de imagens térmicas R-JPEG de 16 bits.

3. **Inteligência Artificial YOLOv11 & Validação Real:**
   - Fine-tuning do modelo YOLOv11 com pesos `best.pt` em imagens termográficas reais de usinas solares.
   - Suporte a polígonos de segmentação com conversão dinâmica para bounding boxes.
   - Avaliação experimental em dados reais de campo com $\text{mAP@50} = 35.73\%$ e $\text{Recall} = 68.40\%$ (revisados na v1.0.1).
   - Rastreabilidade integral de experimentos e persistência na tabela `ai_experiments`.

4. **Mapeamento Topológico Geoespacial:**
   - Indexação automática por algoritmo de *Point-in-Polygon* (PIP).
   - Associação de cada detecção à sua respectiva *String*, Fileira e Coluna física no arranjo fotovoltaico.

5. **Classificação Normativa IEC TS 62446-3:2017:**
   - Cálculo automático do gradiente térmico diferencial ($\Delta T$).
   - Categorização em quatro níveis: Baixa, Média, Alta e Crítica.

6. **Compêndio Documental e Laudos Periciais:**
   - Emissão de relatórios em múltiplos formatos: PDF diagramado (ReportLab), planilhas Excel nativas (OpenXML) e CSV estruturado.
   - 8 documentos técnicos e acadêmicos gerados na pasta `docs/`.

---

### 🛠️ Estatísticas de Engenharia de Software (v1.0 Baseline)
- **Total de Testes Automatizados:** 240 testes (100% de aprovação no baseline v1.0).
- **Cobertura Arquitetural:** 4 camadas estritas da Clean Architecture.
- **Banco de Dados:** SQLite com modo WAL e integridade referencial ativada.
- **Segurança e Licenciamento:**
   - Autenticação de usuários (suporte legado a PBKDF2-HMAC-SHA256, atualizado para Argon2id na v1.0.1).
   - Licenciamento assimétrico **Ed25519 (RFC 8032)** com par de chaves públicas/privadas.
   - Proibição absoluta de geração local de licenças na aplicação cliente.
   - Bloqueio estrito de execução (`license invalid => bloqueia uso`) via guarda de inicialização e interface.
   - Vinculação de hardware por impressão digital (HWID) baseada em SHA-256.

