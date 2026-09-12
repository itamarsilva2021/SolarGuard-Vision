# Arquitetura do Sistema de Atualizações Assinadas (Secure Updater)
## Ed25519 (RFC 8032) + SHA-256 + Proteção Anti-TOCTOU e Anti-Rollback

Este documento especifica a arquitetura e os controles de segurança do mecanismo de atualização de software do **SolarGuard Vision**, garantindo imunidade contra adulteração de manifestos, injeção de instaladores maliciosos e ataques de downgrade.

---

## 1. Fluxo Criptográfico de Distribuição

```text
[Servidor de Release / Pipeline CI]
              │
              ▼
   1. Gera binário do instalador (.exe / .msi)
   2. Calcula SHA-256 do binário oficial
   3. Constrói o manifesto de atualização (versão, notas, url, sha256)
   4. Assina o manifesto canônico com a Chave Privada Ed25519
              │
              ▼
       [Manifesto Assinado]
              │
══════════════╪══════════════════════════════════════════════════════════
              │ Rede / Internet (Canal Não Confiável)
══════════════╪══════════════════════════════════════════════════════════
              │
              ▼
    [Cliente SolarGuard Vision]
              │
              ├─► 1. Validação da Assinatura Ed25519
              │      (Verifica chave pública confiável do emissor)
              │      [Falha] ──► ABORTA IMEDIATAMENTE (Sem download)
              │
              ├─► 2. Verificação de Rollback (SemVer)
              │      (Garante que a versão remota é estritamente mais recente)
              │      [Falha] ──► IGNORA VERSÃO ANTERIOR
              │
              ├─► 3. Download Seguro para Diretório Temporário Isolado
              │
              ├─► 4. Validação Rigorosa de Hash SHA-256 (64 KiB Chunks)
              │      [Falha] ──► DESCARTA E DELETA ARQUIVO IMEDIATAMENTE
              │
              └─► 5. Instalação Auditada
                     (Revalidação pré-execução anti-TOCTOU e despacho seguro)
```

---

## 2. Modelo de Ameaças e Mitigações

| Ameaça Criptográfica | Vetor de Ataque | Mitigação no SolarGuard Vision |
| :--- | :--- | :--- |
| **Injeção de Malware via MITM** | Atacante intercepta o tráfego de rede e substitui a URL por um executável com cavalo de Troia. | **Assinatura Ed25519:** Qualquer alteração na URL invalida a assinatura digital do manifesto. O cliente aborta antes de iniciar qualquer download. |
| **Manifesto Forjado (Rogue Key)** | Atacante cria um manifesto assinado com sua própria chave privada. | **Chave Pública Restrita:** O cliente só aceita manifestos cuja chave pública coincida com a chave confiável configurada (`trusted_public_key`). |
| **Substituição de Binário no Servidor de Arquivos** | Servidor de download é comprometido e o arquivo executável é adulterado. | **Verificação SHA-256 estrita:** O cliente compara o hash do arquivo baixado com o hash presente no manifesto assinado. Em caso de divergência, o arquivo é deletado imediatamente. |
| **Ataque de Downgrade / Rollback** | Atacante entrega uma versão antiga e vulnerável do software. | **Controle SemVer:** A versão remota deve ser estritamente superior à versão instalada (`remote_version > current_version`). |
| **Ataque TOCTOU (Time-of-Check to Time-of-Use)** | Malware local tenta sobrescrever o instalador no disco após o download e antes da execução. | **Revalidação Pré-Execução:** O método `install_update` recalcula e confere o SHA-256 imediatamente antes do despacho do subprocesso. |

---

## 3. Especificação do Manifesto Assinado

Exemplo estrutural do manifesto canônico assinado:

```json
{
  "version": "1.1.0",
  "release_date": "2026-09-12",
  "release_notes": "SolarGuard Vision v1.1.0 com modelos aprimorados e salvaguarda de dados.",
  "download_url": "https://releases.solarguard.ai/v1.1.0/SolarGuard_Setup.exe",
  "sha256": "c97fd107607cc6541c703b0010d390083b8912301ff43f12cac2f17a56e42b09",
  "mandatory": true,
  "signer_public_key_b64": "MzaED2Vwv8KQdspsV6snRel5Fkl+/BUy56gN68nG2YM=",
  "signature_b64": "v+fJ8mK1LqA53...<assinatura Ed25519 de 64 bytes em base64>..."
}
```

---

## 4. API do Cliente e Emissor

- **Emissor / CI Pipeline (`UpdateManifestSigner`):**
  - `UpdateManifestSigner.sign_manifest(manifest_data, private_key)`: serializa em formato canônico ordenado, assina via Ed25519 e anexa as chaves e assinatura Base64.
- **Cliente / Desktop (`UpdateManager`):**
  - `check_signed_manifest(manifest_data_or_json)`: valida a assinatura assimétrica e checa a progressão semântica.
  - `download_update(update_info)`: realiza download com conferência SHA-256 e exclusão atômica em caso de anomalia.
  - `install_update(installer_path, expected_sha256, silent, dry_run)`: executa a instalação silenciosa após checagem anti-TOCTOU.
