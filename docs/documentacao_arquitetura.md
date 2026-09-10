# Documentação de Arquitetura de Software - SolarGuard Vision

**Versão:** 1.0.0 (Research Edition)  
**Padrão Arquitetural:** Clean Architecture (Uncle Bob), Domain-Driven Design (DDD) tático, SOLID  
**Framework de Interface:** PySide6 (Qt for Python) - Padrão Model-View-ViewModel (MVVM)  

---

## 1. Visão Geral e Princípios Arquiteturais

O **SolarGuard Vision** foi construído sob o princípio fundamental da **independência de frameworks, bancos de dados e interfaces de usuário**. As regras de negócio centrais residem no núcleo do domínio e são agnósticas em relação aos mecanismos de entrega e persistência.

```mermaid
graph TD
    subgraph Presentation ["1. Presentation Layer (UI / CLI)"]
        UI[PySide6 Qt Views]
        VM[ViewModels & Controllers]
        CLI[Main CLI Runner]
    end

    subgraph Application ["2. Application Layer (Use Cases)"]
        PipService[InspectionPipelineService]
        TrainService[TrainingPipelineService]
        EvalService[ExperimentalEvaluationService]
        AuditService[DatasetAuditor]
        ReportService[ScientificValidationReport]
        GISService[GeoReferencingService]
    end

    subgraph Domain ["3. Domain Layer (Entities & Rules)"]
        Entities[Entities: Client, Project, Inspection, ThermalAnomaly]
        Enums[Enums: SeverityLevel, AnomalyType, PaletteType]
        Interfaces[Interfaces: Repositories & Engine Contracts]
        VO[Value Objects: GPSCoordinate, DeltaT]
    end

    subgraph Infrastructure ["4. Infrastructure Layer (External)"]
        DB[SQLite WAL DatabaseManager]
        Repos[SqliteRepositories & ExperimentRepository]
        DJI[DJI Metadata & RJPEG Parsers]
        YOLO[Ultralytics YOLOv11 Engine]
        Thermal[RadiometryEngine & AtmosphericModel]
        Security[PasswordHasher & LicenseManager]
    end

    Presentation --> Application
    Application --> Domain
    Infrastructure --> Domain
    Application ..-> Infrastructure
```

### 1.1. Regra de Dependência
As dependências do código apontam **estritamente de fora para dentro**:
- O **Domínio** não possui dependência de nenhuma biblioteca externa (nem Qt, nem Torch, nem SQLite).
- A **Aplicação** depende exclusivamente das entidades e interfaces do Domínio.
- A **Infraestrutura** implementa os contratos do Domínio usando drivers e bibliotecas externas.
- A **Apresentação** consome os Serviços de Aplicação através de injeção de dependências.

---

## 2. Aplicação dos Princípios SOLID

| Princípio SOLID | Implementação Prática no SolarGuard Vision |
| :--- | :--- |
| **S - Single Responsibility** | Cada classe possui uma única razão para mudar. Ex: `RadiometryEngine` calcula calibração física, `ThermalAnalyzer` analisa gradientes e `ConfusionMatrixService` gera visualizações. |
| **O - Open/Closed** | O sistema aceita novos modelos de sensores térmicos (ex: FLIR, DJI, Workswell) implementando novos `CalibrationProfile` sem alterar o motor radiométrico central. |
| **L - Liskov Substitution** | As implementações de repositório em disco (`SqliteExperimentRepository`) podem ser substituídas por instâncias em memória (`:memory:`) nos testes unitários sem alteração de comportamento. |
| **I - Interface Segregation** | Contratos enxutos e especializados (`IClientRepository`, `IProjectRepository`, `IExperimentRepository`, `IThermalProcessor`). |
| **D - Dependency Inversion** | Serviços de aplicação dependem de contratos abstratos (`IExperimentRepository`), os quais são injetados no construtor via Injeção de Dependências. |

---

## 3. Padrões de Projeto (Design Patterns) Adotados

### 3.1. Repository Pattern
Desacopla as operações CRUD e consultas do banco de dados relacional das regras de negócio:
- `ClientRepository`, `ProjectRepository`, `InspectionRepository`, `ThermalAnomalyRepository`, `SqliteExperimentRepository`.

### 3.2. Result Pattern funcional
Elimina o lançamento indiscriminado de exceções em fluxos de negócio esperados:
- Classes `Result[T, E]`, `Success(value)` e `Failure(error)` padronizam respostas de operações assíncronas e validações.

### 3.3. Fachada (Facade Pattern)
- `DatasetAuditor`: Fornece interface simplificada que orquestra `DatasetValidator`, `DatasetStatisticsCalculator` e `DatasetBalanceAnalyzer`.
- `InspectionPipelineService`: Orquestra o fluxo end-to-end de 10 etapas desde o voo bruto até o mapa e laudo PDF.

### 3.4. Strategy Pattern
- `EmissivityModel`: Suporta diferentes estratégias de cálculo térmico (emissividade constante, emissividade angular de Fresnel, tabelas de materiais).

---

## 4. Fluxo de Execução End-to-End da Inspeção Automática

O diagrama de sequência a seguir ilustra a execução orquestrada pelo [`InspectionPipelineService`](file:///d:/OneDrive/AREA%20DE%20TRABALHO%20WINDOWS%2011/Documentos/ThermoPV%20AI/src/application/services/inspection_pipeline_service.py):

```mermaid
sequenceDiagram
    autonumber
    actor Inspetor
    participant UI as Presentation (PySide6)
    participant Pipe as InspectionPipelineService
    participant DJI as DJIMetadataParser
    participant Rad as RadiometryEngine
    participant AI as YoloV11Detector
    participant GIS as PanelMapper
    participant DB as SQLite Repositories
    participant Rep as ReportService

    Inspetor->>UI: Seleciona pasta com imagens do voo DJI
    UI->>Pipe: run_inspection_pipeline(flight_dir, inspection_id)
    
    rect rgb(240, 248, 255)
        note over Pipe,DJI: Fase 1: Importação e Metadados
        Pipe->>DJI: parse_flight_folder(flight_dir)
        DJI-->>Pipe: Metadados EXIF, XMP, GPS, RTK e matriz raw
    end

    rect rgb(255, 245, 238)
        note over Pipe,Rad: Fase 2: Radiometria Física e Temperatura
        Pipe->>Rad: calibrate_matrix(raw_matrix, exif_data)
        Rad-->>Pipe: Matriz Térmica Calibrada (°C)
    end

    rect rgb(245, 255, 245)
        note over Pipe,AI: Fase 3: Visão Computacional YOLOv11
        Pipe->>AI: detect_anomalies(thermal_matrix)
        AI-->>Pipe: Bounding boxes, classes e confianças
    end

    rect rgb(255, 250, 205)
        note over Pipe,GIS: Fase 4: Associação Topológica e Severidade
        Pipe->>GIS: map_boxes_to_panels(detections, gps_flight)
        GIS-->>Pipe: Módulo, String, Linha e Coluna indexados
        Pipe->>Pipe: Calcular Delta T e Severidade (IEC TS 62446-3)
    end

    rect rgb(240, 255, 255)
        note over Pipe,DB: Fase 5: Persistência e Emissão de Laudos
        Pipe->>DB: Persistir em thermal_analysis, delta_t, detections
        Pipe->>Rep: generate_pdf_and_interactive_map()
        Rep-->>Pipe: Laudo pericial PDF e mapa HTML salvos
    end

    Pipe-->>UI: InspectionPipelineResult (Sucesso com 100% dos dados)
    UI-->>Inspetor: Exibe Dashboard, Mapa e Laudo para download
```

---

## 5. Garantia de Qualidade e Estratégia de Testes

A integridade do software é assegurada por **207 testes automatizados** organizados em suítes piramidais:
1. **Testes Unitários:** Validação atômica de fórmulas matemáticas, decodificação de tags EXIF/XMP, criptografia de senhas e gerador de licenças.
2. **Testes de Integração:** Interação entre repositórios SQLite, geração de matrizes de confusão, geração de relatórios PDF ReportLab e planilhas OpenXML.
3. **Testes de Regressão Experimental:** Verificação de integridade dos pipelines com datasets térmicos reais de usinas solares.
4. **Testes de Sistema e Prontidão de Produção:** Testes de recuperação de desastres (Crash Dumps, rotação de backups e consistência relacional).
