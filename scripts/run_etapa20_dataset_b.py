"""
Script de Execução Autônoma da ETAPA 19:
Avaliação Experimental e Validação Científica com Dataset Termográfico Real (Mestrado).

Sem dados simulados!
"""

import sys
from pathlib import Path

# Adiciona raiz do projeto ao sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.application.services.experimental_evaluation_service import ExperimentalEvaluationService
from src.core.logger import get_logger

logger = get_logger("RunEtapa19")


def main():
    print("=" * 80)
    print("SOLARGUARD VISION - EXECUÇÃO DA ETAPA 19 (MESTRADO)")
    print("AVALIAÇÃO EXPERIMENTAL COM DADOS REAIS DE TERMOGRAFIA FOTOVOLTAICA")
    print("=" * 80)

    dataset_path = Path(
        r"D:\OneDrive\AREA DE TRABALHO WINDOWS 11\Área de Trabalho\Thermal PV Panel Detection Dataset for UAV Inspection"
    )

    data_yaml = dataset_path / "data.yaml"


    if not dataset_path.exists() or not data_yaml.exists():
        print(f"Erro: Dataset real não encontrado em {dataset_path}")
        sys.exit(1)

    service = ExperimentalEvaluationService(output_dir=BASE_DIR / "reports")

    # Executa o ciclo completo
    result = service.run_stage_19_experiment(
        dataset_path=dataset_path,
        data_yaml_path=data_yaml,
        epochs=10,
        batch_size=8,
        imgsz=640,
        device="cpu",
        learning_rate=0.01,
        experiment_name="mestrado_real_eval",
    )

    print("\n" + "=" * 80)
    print("RESULTADO EXECUTIVO DA ETAPA 19:")
    print("=" * 80)
    print(f"1. Auditoria do Dataset:")
    print(f"   - Total Imagens: {result.audit_result.validation.total_images}")
    print(f"   - Total Anotações: {result.audit_result.statistics.total_annotations}")
    print(f"   - Aprovado para Treinamento: {result.audit_result.is_approved_for_training}")
    print(f"   - PDF da Auditoria: {result.audit_pdf_path}")
    print(f"\n2. Diagnóstico de Balanceamento:")
    print(f"   - Status: {result.balance_result.severity.display_name}")
    print(f"   - Imbalance Ratio (IR): {result.balance_result.imbalance_ratio}x")
    print(f"   - Entropia Normalizada de Shannon: {result.balance_result.normalized_entropy * 100:.2f}%")
    print(f"   - Pesos Calculados (cls_pw): {result.balance_result.recommended_class_weights}")
    print(f"\n3. Treinamento YOLOv11:")
    print(f"   - Pesos Gerados: {result.weights_path}")
    print(f"   - Duração do Treinamento: {result.execution_duration_seconds:.2f}s")
    print(f"\n4. Métricas de Validação (Dataset Real):")
    print(f"   - mAP@50: {result.validation_metrics.map50 * 100:.2f}%")
    print(f"   - mAP@50-95: {result.validation_metrics.map50_95 * 100:.2f}%")
    print(f"   - Precisão (Precision): {result.validation_metrics.precision * 100:.2f}%")
    print(f"   - Revocação (Recall): {result.validation_metrics.recall * 100:.2f}%")
    print(f"   - F1-Score: {result.validation_metrics.f1_score * 100:.2f}%")
    print(f"   - Acurácia Global (Accuracy): {result.global_classification_metrics.accuracy * 100:.2f}%")
    print(f"   - Acurácia Balanceada: {result.global_classification_metrics.balanced_accuracy * 100:.2f}%")
    print(f"\n5. Matriz de Confusão:")
    print(f"   - Classes: {result.confusion_matrix_labels}")
    print(f"   - Matriz:\n{result.confusion_matrix}")
    print(f"   - Gráfico Renderizado: {result.confusion_matrix_img_path}")
    print(f"\n6. Relatórios Científicos Gerados:")
    print(f"   - Relatório PDF: {result.validation_pdf_path}")
    print(f"   - Planilha Excel (.xlsx): {result.validation_xlsx_path}")
    print(f"   - Dados CSV: {result.validation_csv_path}")
    print(f"   - Registro no SQLite (ai_experiments): ID {result.experiment_record.id}")
    print("=" * 80)
    print("ETAPA 19 EXECUTADA COM SUCESSO! DADOS 100% REAIS.")
    print("=" * 80)


if __name__ == "__main__":
    main()
