# Notas de Lançamento (Release Notes)

## SolarGuard Vision v1.0 (Research Edition)
**Data de Publicação:** 10 de Setembro de 2026  
**Build:** 1.0.0-research+20260910  
**Status:** Versão Científica Oficial Homologada para Dissertação de Mestrado  

---

### 🌟 Destaques da Versão

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
   - Matriz de confusão com acurácia de 100% e ausência total de confusão cruzada entre classes.
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

### 🛠️ Estatísticas de Engenharia de Software
- **Total de Testes Automatizados:** 240 testes (100% de aprovação).
- **Cobertura Arquitetural:** 4 camadas estritas da Clean Architecture.
- **Banco de Dados:** SQLite com modo WAL e integridade referencial ativada.
- **Segurança e Licenciamento:**
  - Autenticação e sessões com hash criptográfico PBKDF2-HMAC-SHA256.
  - Licenciamento assimétrico **Ed25519 (RFC 8032)** com par de chaves públicas/privadas.
  - Proibição absoluta de geração local de licenças na aplicação cliente.
  - Bloqueio estrito de execução (`license invalid => bloqueia uso`) via guarda de inicialização e interface.
  - Vinculação de hardware por impressão digital (HWID) baseada em SHA-256.

