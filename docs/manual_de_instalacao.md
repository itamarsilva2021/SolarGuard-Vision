# Manual de Instalação e Implantação - SolarGuard Vision

**Versão da Release:** 1.0.0 (Research Edition)  
**Sistema Operacional Homologado:** Microsoft Windows 10 / 11 (64 bits)  

---

## 1. Requisitos de Hardware e Software

| Componente | Requisitos Mínimos (Operação em Campo) | Requisitos Recomendados (Estação de Pesquisa) |
| :--- | :--- | :--- |
| **Processador (CPU)** | Intel Core i5 8ª Geração ou AMD Ryzen 5 (4 núcleos) | Intel Core i7 12ª+ Geração ou AMD Ryzen 7 (8+ núcleos) |
| **Memória RAM** | 8 GB DDR4 | 16 GB ou 32 GB DDR4/DDR5 |
| **Armazenamento** | 10 GB livres (SSD SATA) | 50 GB livres (SSD NVMe M.2) |
| **Placa de Vídeo (GPU)** | Gráficos Integrados (Execução em CPU via PyTorch) | NVIDIA GeForce RTX 3060 / 4060 ou superior (CUDA 12+) |
| **Resolução de Tela** | $1366 \times 768$ | $1920 \times 1080$ (Full HD) ou superior |
| **Sistema Operacional** | Windows 10 64-bit (Build 19041+) | Windows 11 64-bit |

---

## 2. Instalação para Usuários Finais (Instalador Executável)

O SolarGuard Vision disponibiliza um instalador automatizado para Windows que dispensa a instalação prévia de interpretadores ou bibliotecas externas.

### Passo a Passo de Instalação:
1. Faça o download do arquivo de instalação:
   ```
   Setup_SolarGuard_Vision_v1.0.0.exe
   ```
2. Execute o instalador com privilégios de administrador.
3. Siga as etapas do assistente:
   - Aceite os termos de licença de uso da versão de pesquisa;
   - Escolha o diretório de destino (padrão: `C:\Program Files\SolarGuard Vision`);
   - Marque a opção de criar atalho na Área de Trabalho e no Menu Iniciar.
4. Conclua a instalação e marque a opção **Iniciar o SolarGuard Vision**.
5. No primeiro início, o sistema gerará o banco de dados inicial e a chave de avaliação de 14 dias vinculada ao HWID da máquina.

---

## 3. Instalação a partir do Código-Fonte (Desenvolvimento e Pesquisa)

Para pesquisadores e desenvolvedores que desejam estender os algoritmos ou auditar os testes:

### 3.1. Pré-Requisitos
- **Python 3.12.x (64 bits)** instalado e adicionado ao `PATH` do Windows.
- **Git** instalado.

### 3.2. Clonagem e Configuração do Ambiente Virtual
Abra o PowerShell no diretório desejado e execute:

```powershell
# 1. Clonar o repositório
git clone https://github.com/itamar/solarguard-vision.git
cd solarguard-vision

# 2. Criar o ambiente virtual Python 3.12
python -m venv .venv

# 3. Ativar o ambiente virtual
.venv\Scripts\Activate.ps1
```

### 3.3. Instalação e Reprodutibilidade com `uv` (Recomendado)
O SolarGuard Vision adota o gerenciador de dependências **`uv`** com lockfile determinístico **`uv.lock`**, permitindo instalar apenas os grupos necessários para cada finalidade:

```powershell
# Opção A: Instalação Enxuta de Produção (Apenas Runtime)
# Instala estritamente as dependências necessárias para operação desktop e inferência
uv sync --no-dev

# Opção B: Instalação para Treinamento e Experimentação Científica
uv sync --group training

# Opção C: Instalação Completa de Desenvolvimento e Testes (CI/CD)
# Inclui pytest, pytest-cov, ruff, mypy e pyinstaller
uv sync --all-groups
```

### 3.4. Instalação Tradicional com `pip`
Caso prefira o ecossistema padrão:
```powershell
pip install --upgrade pip
pip install -e .                 # Apenas produção
pip install -e ".[training,dev]" # Desenvolvimento completo
```

### 3.5. Diagnóstico de Prontidão do Sistema
Execute o comando de auto-diagnóstico do SolarGuard Vision:

```powershell
uv run python main.py --check-system
```

Saída esperada:
```
=================================================================
       SOLARGUARD VISION v1.0.0 - DIAGNÓSTICO DE SISTEMA
=================================================================
[+] Versão da Aplicação: 1.0.0
[+] Idioma configurado: pt_BR
[+] Tema ativo: dark
[+] Banco de dados SQLite operacional em: data/solarguard.sqlite3
[+] Todos os subsistemas operacionais e validados com sucesso.
=================================================================
```

### 3.6. Execução dos Testes Automatizados
Para certificar a integridade de todas as camadas arquiteturais:

```powershell
uv run pytest -v
```

---

## 4. Compilação do Instalador Windows (Packaging)

Para recriar o binário autocontido `.exe` e o pacote de instalação Inno Setup:

```powershell
# Executar o script automatizado de compilação
.venv\Scripts\python.exe packaging/build_installer.py
```

O artefato final será gerado em:
```
dist/Setup_SolarGuard_Vision_v1.0.0.exe
```
