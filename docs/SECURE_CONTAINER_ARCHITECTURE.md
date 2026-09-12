# Arquitetura do Container Criptográfico Seguro (SGZ)
## ZIP + AES-256-GCM + Assinatura Assimétrica Ed25519 (RFC 8032)

Este documento descreve a especificação técnica do container criptográfico blindado implementado no **SolarGuard Vision** para salvaguarda de dados operacionais, exportação de laudos periciais, auditoria termográfica e backups de usinas solares fotovoltaicas.

---

## 1. Tríade de Segurança da Informação

O formato de container **SGZ (`.sgz` / `.zip.enc`)** foi concebido para atender rigorosamente aos três pilares da segurança cibernética:

| Pilar | Mecanismo Criptográfico | Garantia Técnica |
| :--- | :--- | :--- |
| **Confidencialidade** | **AES-256-GCM** (Galois/Counter Mode) + **Argon2id** | Cifragem simétrica de 256 bits com chave derivada por Argon2id (64 MiB RAM, 3 iterações, 4 lanes). Protege os dados em repouso contra vazamentos e espionagem industrial. |
| **Integridade** | **GCM Authentication Tag** (128 bits) + **SHA-256 Digest** + **CRC32 ZIP** | Qualquer alteração de 1 bit no ciphertext ou no cabeçalho é detectada antes da extração, bloqueando execuções corrompidas ou adulteradas. |
| **Autenticidade** | **Ed25519** (RFC 8032 - Edwards-curve Digital Signature) | Assinatura digital assimétrica gerada com chave privada do emissor e verificada com chave pública do receptor. Comprova autoria e garante o não-repúdio. |

---

## 2. Estrutura Binária do Container (`.sgz`)

O container unificado é serializado em disco segundo o layout canônico:

```text
+-------------------------------------------------------------------------+
| [00..03] Magic Bytes: "SGZ1" (4 Bytes)                                 |
+-------------------------------------------------------------------------+
| [04..07] Header Length: Big-Endian uint32 (4 Bytes)                     |
+-------------------------------------------------------------------------+
| [08..N]  Canonical Header JSON UTF-8                                   |
|          - Format: "SGZ" / Version: "1.0"                               |
|          - Timestamp ISO 8601 UTC                                       |
|          - KDF: Argon2id (iterations=3, memory=65536, lanes=4, salt_b64)|
|          - Cipher: AES-256-GCM (nonce_b64: 12 Bytes)                    |
|          - Ciphertext SHA-256 Digest                                    |
|          - Signer Ed25519 Public Key (Base64)                           |
|          - Ed25519 Digital Signature (Base64)                           |
|          - Structured Metadata (usina, drone, operador, auditoria)      |
+-------------------------------------------------------------------------+
| [N+1..M] AES-256-GCM Ciphertext + 16 Bytes Authentication Tag           |
|          (Payload decifrado = fluxo compactado ZIP DEFLATED)            |
+-------------------------------------------------------------------------+
```

---

## 3. Fluxo de Empacotamento (`pack`)

1. **Compactação ZIP:** Os arquivos de entrada (bancos SQLite, imagens R-JPEG, relatórios PDF/Excel) são compactados em memória no padrão `zipfile.ZIP_DEFLATED`.
2. **Derivação de Chave (KDF):** Um `salt` criptográfico de 16 bytes é gerado via `os.urandom(16)`. A chave AES de 256 bits (32 bytes) é derivada via `Argon2id` a partir da senha do operador.
3. **Cifragem AEAD:** Um `nonce` de 12 bytes (96 bits) é gerado exclusivamente para a operação. O fluxo ZIP é cifrado com `AESGCM(key)`, gerando o `ciphertext` com tag de 128 bits acoplada.
4. **Cálculo de Digest:** É computado o hash criptográfico `SHA-256` do ciphertext resultante.
5. **Serialização Canônica do Cabeçalho:** Todos os metadados técnicos são estruturados em JSON ordenado e canônico (`sort_keys=True`, sem espaços supérfluos).
6. **Assinatura Ed25519:** A chave privada Ed25519 assina os bytes do cabeçalho canônico (que já contém o hash do ciphertext). A assinatura gerada de 64 bytes é codificada em Base64 e inserida no cabeçalho final.
7. **Gravação Unificada:** O arquivo `.sgz` final é gravado no disco com cabeçalho delimitado por tamanho e o ciphertext contíguo.

---

## 4. Fluxo de Verificação e Desempacotamento (`unpack`)

1. **Validação de Formato:** Confere os magic bytes `SGZ1` e a consistência do comprimento do cabeçalho.
2. **Verificação de Autenticidade (Ed25519):**
   - Reconstrói os bytes canônicos do cabeçalho e verifica a assinatura com a chave pública confiável esperada.
   - **Se a assinatura for inválida ou forjada:** a operação é abortada imediatamente com rejeição de autenticidade.
3. **Verificação de Integridade (SHA-256):**
   - Confere se `hashlib.sha256(ciphertext)` bate rigorosamente com o digest assinado no cabeçalho.
4. **Decifração Autenticada (AES-256-GCM):**
   - Deriva a chave simétrica com Argon2id utilizando o salt do container e a senha fornecida.
   - Decifra o payload via `AESGCM.decrypt()`. Se a senha estiver incorreta ou qualquer bit do ciphertext tiver sido modificado, a autenticação GCM falha imediatamente.
5. **Mitigação contra Path Traversal (Anti-Zip Slip):**
   - Ao descompactar os arquivos contidos no ZIP decifrado, cada caminho de destino é inspecionado canonicamente. Qualquer tentativa de extração fora do diretório de destino (`../` ou caminhos absolutos arbitrários) lança `PermissionError` e é bloqueada.

---

## 5. Integração com o `BackupService`

O serviço de backup do SolarGuard Vision oferece dois métodos dedicados de nível empresarial:
- `backup_svc.create_secure_backup(passphrase, signing_key, custom_label)`: produz um snapshot blindado `.sgz` do banco SQLite e arquivos de configuração.
- `backup_svc.restore_secure_backup(package_path, passphrase, verify_key)`: valida assinatura, decifra e restaura com salvaguarda automática de snapshot pré-restauração (`.pre_restore.bak`).
- `backup_svc.list_backups()`: cataloga tanto arquivos legados `.zip` quanto arquivos blindados `.sgz`, expondo o atributo booleano `is_secure`.
