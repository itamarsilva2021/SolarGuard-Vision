# Arquitetura de Licenciamento Assimétrico Ed25519 - SolarGuard Vision

## 1. Visão Geral e Motivação

O **SolarGuard Vision** adota criptografia assimétrica de curva de Edwards **Ed25519** (RFC 8032 / Edwards25519 sobre o campo primo $2^{255} - 19$) como mecanismo padrão para controle de licenciamento, integridade e proteção contra pirataria e uso indevido em ambientes corporativos e industriais.

Historicamente, sistemas de desktop utilizavam chaves simétricas (como HMAC-SHA256 ou AES com chave compartilhada). Esse modelo apresenta uma vulnerabilidade intrínseca crítica: como o software cliente precisa verificar a assinatura da chave, o segredo criptográfico acaba sendo embutido ou derivado dentro do próprio binário distribuído, tornando o sistema vulnerável a descompilação, engenharia reversa e geração local de chaves fraudulentas (*keygens*).

Para mitigar esse risco de forma definitiva, o SolarGuard Vision implementa uma **separação criptográfica assimétrica estrita** entre Servidor e Cliente.

---

## 2. Arquitetura Assimétrica: Servidor vs. Cliente

```
┌────────────────────────────────────────────────────────┐
│                   SERVIDOR DE LICENÇAS                 │
│              (Ambiente Seguro / Infraestrutura)        │
│                                                        │
│   [ CHAVE PRIVADA Ed25519 ] (Nunca distribuída)       │
│                                                        │
│   Entrada: HWID do Cliente + Plano + Validade          │
│   Processo: Assinatura Digital Assimétrica             │
│   Saída: Token <payload_b64>.<assinatura_ed25519_b64>  │
└───────────────────────────┬────────────────────────────┘
                            │  Entrega do arquivo .key
                            ▼
┌────────────────────────────────────────────────────────┐
│                   CLIENTE DESKTOP                      │
│             (SolarGuard Vision - Estação Windows)      │
│                                                        │
│   [ CHAVE PÚBLICA Ed25519 ] (Apenas verificação)       │
│                                                        │
│   Processo: public_key.verify(assinatura, payload)     │
│   Validação: HWID local == HWID da licença             │
│              Data atual <= Data de expiração           │
│                                                        │
│   Resultado:                                           │
│   - Válida   => Libera operação e diagnóstico IA       │
│   - Inválida => BLOQUEIA TOTALMENTE O USO DO SOFTWARE  │
└────────────────────────────────────────────────────────┘
```

### 2.1 Servidor (Autoridade de Emissão - `LicenseIssuer`)
- **Detenção da Chave Privada (`Ed25519PrivateKey`):** A chave privada permanece sob posse exclusiva da autoridade de licenciamento do SolarGuard Vision.
- **Responsabilidade:** Único componente autorizado a gerar e assinar tokens criptográficos.
- **Isolamento:** Localizado em [`src/infrastructure/security/license_issuer.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/infrastructure/security/license_issuer.py) e utilitário CLI [`scripts/issue_license.py`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/scripts/issue_license.py).

### 2.2 Cliente Desktop (`LicenseManager`)
- **Detenção da Chave Pública (`Ed25519PublicKey`):** O aplicativo desktop instalado nas estações de trabalho detém **unicamente a chave pública oficial** (32 bytes em Base64).
- **Proibição Estrita de Geração Local:** O cliente não possui o método `generate_license_key` nem qualquer acesso à chave privada. É matematicamente impossível para o cliente gerar uma licença válida para si mesmo.
- **Validação Pura:** O cliente atua estritamente como um validador assimétrico.

---

## 3. Estrutura do Token de Licença

O token de ativação é uma string compacta e transportável composta por duas partes separadas por um ponto (`.`):

$$\text{Token} = \langle \text{Payload}_{\text{Base64}} \rangle \,.\, \langle \text{Signature}_{\text{Ed25519\_Base64}} \rangle$$

### 3.1 Payload JSON Serializado
```json
{
  "client": "Enel Green Power Brasil S.A.",
  "type": "enterprise",
  "hwid": "AA8077A9D996D1FE64144A2C",
  "issued": "2026-09-11T18:30:00",
  "expires": "2027-09-11T18:30:00",
  "max_plants": 250
}
```

### 3.2 Assinatura Digital
- O servidor assina digitalmente a representação em bytes do `Payload_Base64` utilizando `private_key.sign(payload_bytes)`.
- A assinatura resultante de 64 bytes é codificada em Base64 URL-safe.
- Qualquer alteração em um único caractere do payload (por exemplo, adulterar a data de expiração ou o HWID) invalida a assinatura matemática em tempo constante.

---

## 4. Hardware Fingerprinting (HWID)

Para evitar clonagem de arquivos de licença entre diferentes computadores ou servidores da planta solar, a licença é atrelada à impressão digital física do computador:

$$\text{HWID} = \text{SHA256}(\text{MAC Address} \parallel \text{Node Name} \parallel \text{Processor} \parallel \text{OS})[0:24]$$

- Caso o HWID contido na licença não coincida com o HWID da máquina local, a licença é considerada inválida (`is_valid = False`).
- **Licença Enterprise Flutuante:** Para ambientes corporativos conteinerizados ou clusters de alta disponibilidade, o servidor pode emitir a chave com `hwid = "*"`, permitindo execução flutuante sob autorização contratual.

---

## 5. Política de Bloqueio Estrito: `license invalid => bloqueia uso`

Diferente de sistemas permissivos que permitem acesso mesmo na ausência de licença, o SolarGuard Vision estabelece **bloqueio mandatório**:

1. **Na Inicialização (`main.py`):**
   - O aplicativo executa `lic_mgr.check_current_license()`.
   - Se `lic_info.is_valid is False` (arquivo ausente, expirado ou forjado):
     - A interface principal **NÃO** é aberta.
     - O sistema exibe o diálogo modal obrigatório [`LicenseActivationDialog`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/presentation/license_dialog.py).
     - Se o operador fechar ou não fornecer uma chave válida, o software encerra imediatamente com código de erro `sys.exit(1)`.

2. **Na Janela Principal (`MainWindow`):**
   - A guarda `check_license_guard(index)` intercepta qualquer tentativa de troca de abas (Dashboard, Inspeções, Relatórios, Auditoria de Dataset, Configurações).
   - Se a licença se tornar inválida durante o uso (ex: expiração de vigência), todos os módulos operacionais são imediatamente bloqueados, redirecionando o operador para a aba de ativação de licença.

---

## 6. Procedimento Operacional de Emissão de Licenças

Para a equipe de suporte e vendas emitir uma licença oficial:

1. Obter o HWID da máquina do cliente (exibido na tela de ativação ou via comando `python main.py --hwid`).
2. No ambiente seguro do servidor, executar o utilitário oficial:
   ```bash
   python scripts/issue_license.py \
       --client "Usina Solar São Francisco" \
       --hwid "AA8077A9D996D1FE64144A2C" \
       --type professional \
       --days 365 \
       --plants 50 \
       --out "licenca_cliente.key"
   ```
3. O arquivo `licenca_cliente.key` gerado é encaminhado com segurança para o cliente.
4. O cliente seleciona o arquivo ou cola o token na interface do SolarGuard Vision para desbloquear o uso completo.
