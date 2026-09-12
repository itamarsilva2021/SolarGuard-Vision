"""
Script de Revalidação Científica Experimental v2 (2026) para o SolarGuard Vision.

Executa:
- Treinamento YOLOv11 com dataset termográfico reestruturado e particionado de forma independente (sem vazamento de voo).
- Mapeamento de classes validado: 2 classes da IEC TS 62446-3 (0: hotspot group, 1: panel with hotspots).
- Avaliação científica rigorosa com pareamento IoU >= 0.45 e inclusão explícita de background para Falsos Negativos e Falsos Positivos.
- Consolidação e geração de experiments/revalidation_2026/results_v2.csv.
- Salvaguarda integral dos resultados anteriores (nenhum arquivo antigo é substituído).
"""

import csv
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Adiciona raiz do projeto ao sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import yaml
from src.infrastructure.ml.yolo_trainer import YoloV11Trainer
from src.infrastructure.ml.yolo_validator import YoloV11Validator
from src.application.services.experimental_evaluation_service import ExperimentalEvaluationService
from src.application.validation.classification_metrics import ClassificationMetricsCalculator
from src.application.validation.confusion_matrix_service import ConfusionMatrixService
from src.application.validation.scientific_validation_report import (
    ScientificValidationReport,
    ScientificValidationReportData,
)
from src.application.validation.benchmark_service import ModelBenchmarkResult
from src.core.logger import get_logger

logger = get_logger("Revalidation2026")


def main():
    print("=" * 80)
    print("SOLARGUARD VISION - REEXECUÇÃO DE TREINAMENTO E VALIDAÇÃO v2 (2026)")
    print("AVALIAÇÃO CIENTÍFICA CORRIGIDA COM SPLIT INDEPENDENTE E 2 CLASSES")
    print("=" * 80)

    start_time = time.time()
    out_dir = BASE_DIR / "experiments" / "revalidation_2026"
    out_dir.mkdir(parents=True, exist_ok=True)
    weights_dir = out_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = BASE_DIR / "datasets" / "thermal_pv_mestrado"
    data_yaml_path = dataset_path / "data.yaml"

    if not data_yaml_path.exists():
        print(f"Erro: data.yaml não encontrado em {data_yaml_path}")
        sys.exit(1)

    yaml_data = yaml.safe_load(data_yaml_path.read_text(encoding="utf-8")) or {}
    class_names = {idx: name for idx, name in enumerate(yaml_data.get("names", []))}
    print("\n1. Configuração do Dataset Carregada:")
    print(f"   - Dataset: {dataset_path.name}")
    print(f"   - Arquivo: {data_yaml_path}")
    print(f"   - Classes do Treinamento: {class_names}")
    print(f"   - Divisões: Train={yaml_data.get('train')}, Val={yaml_data.get('val')}, Test={yaml_data.get('test')}")

    # -------------------------------------------------------------------------
    # 1. TREINAMENTO SUPERVISIONADO COM OS HIPERPARÂMETROS CALIBRADOS
    # -------------------------------------------------------------------------
    epochs = 10
    batch_size = 4
    imgsz = 640
    device = "cpu"
    learning_rate = 0.01

    print("\n2. Iniciando Treinamento YOLOv11:")
    print(f"   - Épocas: {epochs} | Batch: {batch_size} | Resolução: {imgsz}x{imgsz} | Dispositivo: {device}")
    
    trainer = YoloV11Trainer(output_dir=out_dir / "runs")
    trained_weights_path = trainer.train(
        data_yaml=data_yaml_path,
        epochs=epochs,
        imgsz=imgsz,
        batch_size=batch_size,
        device=device,
        learning_rate=learning_rate,
        experiment_name="yolo11n_revalidation",
        use_thermal_augmentations=True,
    )
    print(f"   - Treinamento finalizado. Pesos salvos em: {trained_weights_path}")

    # Copia pesos finais para o diretório oficial da revalidação
    final_best_pt = weights_dir / "best.pt"
    shutil.copy2(trained_weights_path, final_best_pt)

    # -------------------------------------------------------------------------
    # 2. VALIDAÇÃO FORMAL ULTRALYTICS (mAP50, mAP50-95, Precision, Recall, F1)
    # -------------------------------------------------------------------------
    print("\n3. Executando Validação Formal Ultralytics no Conjunto Independente:")
    validator = YoloV11Validator(class_names=class_names)
    val_metrics = validator.evaluate(
        weights_path=final_best_pt,
        data_yaml=data_yaml_path,
        imgsz=imgsz,
        device=device,
    )
    print(f"   - mAP@50:    {val_metrics.map50 * 100:.2f}%")
    print(f"   - mAP@50-95: {val_metrics.map50_95 * 100:.2f}%")
    print(f"   - Precision: {val_metrics.precision * 100:.2f}%")
    print(f"   - Recall:    {val_metrics.recall * 100:.2f}%")
    print(f"   - F1-Score:  {val_metrics.f1_score * 100:.2f}%")

    # -------------------------------------------------------------------------
    # 3. AVALIAÇÃO CIENTÍFICA CORRIGIDA (IoU >= 0.45 COM BACKGROUND EXPLÍCITO)
    # -------------------------------------------------------------------------
    print("\n4. Executando Pareamento Científico Rigoroso (IoU >= 0.45 com Background):")
    eval_service = ExperimentalEvaluationService(output_dir=out_dir)
    y_true, y_pred, labels_list = eval_service._extract_real_ground_truth_and_predictions(
        dataset_dir=dataset_path,
        weights_path=final_best_pt,
        class_names=class_names,
        device=device,
    )
    print(f"   - Total de pares avaliados: {len(y_true)}")

    # Matriz de Confusão
    cm_service = ConfusionMatrixService(labels=labels_list)
    cm_matrix, resolved_labels = cm_service.compute(
        y_true=y_true,
        y_pred=y_pred,
        labels=labels_list,
    )
    cm_img_path = out_dir / "confusion_matrix_v2.png"
    cm_service.plot(
        matrix=cm_matrix,
        labels=resolved_labels,
        output_path=cm_img_path,
        title="Matriz de Confusão v2 - Revalidação Científica 2026",
    )
    print(f"   - Matriz de Confusão gerada:\n{cm_matrix}")
    print(f"   - Gráfico da Matriz salvo em: {cm_img_path}")

    # Cálculo das métricas de classificação com target_classes
    target_classes = [class_names[i] for i in sorted(class_names.keys())]
    class_metrics = ClassificationMetricsCalculator.calculate_from_labels(
        y_true=y_true,
        y_pred=y_pred,
        labels=resolved_labels,
        target_classes=target_classes,
    )
    print(f"\n   Métricas de Detecção & Classificação (Alvo: {target_classes}):")
    print(f"   - Acurácia Global (Accuracy): {class_metrics.accuracy * 100:.2f}%")
    print(f"   - Acurácia Balanceada:       {class_metrics.balanced_accuracy * 100:.2f}%")
    print(f"   - Precisão Macro:            {class_metrics.macro_precision * 100:.2f}%")
    print(f"   - Revocação Macro:           {class_metrics.macro_recall * 100:.2f}%")
    print(f"   - F1 Macro:                  {class_metrics.macro_f1 * 100:.2f}%")
    print(f"   - Precisão Ponderada:        {class_metrics.weighted_precision * 100:.2f}%")
    print(f"   - Revocação Ponderada:       {class_metrics.weighted_recall * 100:.2f}%")
    print(f"   - F1 Ponderado:              {class_metrics.weighted_f1 * 100:.2f}%")

    # -------------------------------------------------------------------------
    # 4. GERAÇÃO DO ARQUIVO results_v2.csv
    # -------------------------------------------------------------------------
    csv_v2_path = out_dir / "results_v2.csv"
    with open(csv_v2_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_name",
            "timestamp",
            "dataset",
            "epochs",
            "batch_size",
            "imgsz",
            "mAP50",
            "mAP50-95",
            "Precision",
            "Recall",
            "F1",
            "Accuracy",
            "Balanced_Accuracy",
            "Macro_Precision",
            "Macro_Recall",
            "Macro_F1",
            "Weighted_Precision",
            "Weighted_Recall",
            "Weighted_F1",
            "Inference_Time_ms",
            "FPS",
        ])
        writer.writerow([
            "revalidation_2026_v2",
            datetime.now().isoformat(),
            dataset_path.name,
            epochs,
            batch_size,
            imgsz,
            round(val_metrics.map50, 4),
            round(val_metrics.map50_95, 4),
            round(val_metrics.precision, 4),
            round(val_metrics.recall, 4),
            round(val_metrics.f1_score, 4),
            round(class_metrics.accuracy, 4),
            round(class_metrics.balanced_accuracy, 4),
            round(class_metrics.macro_precision, 4),
            round(class_metrics.macro_recall, 4),
            round(class_metrics.macro_f1, 4),
            round(class_metrics.weighted_precision, 4),
            round(class_metrics.weighted_recall, 4),
            round(class_metrics.weighted_f1, 4),
            round(val_metrics.inference_time_ms, 2),
            round(val_metrics.fps, 1),
        ])
        
        # Linha em branco e detalhamento por classe
        writer.writerow([])
        writer.writerow(["--- DETALHAMENTO POR CLASSE ---"])
        writer.writerow(["Class_Name", "TP", "FP", "FN", "TN", "Total_Samples", "Precision", "Recall", "Specificity", "F1_Score", "Balanced_Accuracy"])
        for c_name, cm in class_metrics.per_class_metrics.items():
            writer.writerow([
                c_name,
                cm.true_positives,
                cm.false_positives,
                cm.false_negatives,
                cm.true_negatives,
                cm.total_samples,
                round(cm.precision, 4),
                round(cm.recall, 4),
                round(cm.specificity, 4),
                round(cm.f1_score, 4),
                round(cm.balanced_accuracy, 4),
            ])

    print("\n5. Arquivo CSV consolidado gerado com sucesso:")
    print(f"   - Caminho: {csv_v2_path}")

    # -------------------------------------------------------------------------
    # 5. GERAÇÃO DE METADADOS JSON E RELATÓRIO CIENTÍFICO PDF/XLSX
    # -------------------------------------------------------------------------
    sha256_hash = hashlib.sha256(final_best_pt.read_bytes()).hexdigest()
    best_json_v2 = weights_dir / "best.json"
    manifest_v2 = {
        "model_name": "best.pt",
        "experiment": "revalidation_2026_v2",
        "architecture": "YOLOv11n",
        "framework": "Ultralytics / PyTorch",
        "created_at": datetime.now().isoformat(),
        "sha256": sha256_hash,
        "classes": class_names,
        "num_classes": len(class_names),
        "metrics": {
            "map50": round(val_metrics.map50, 4),
            "map50_95": round(val_metrics.map50_95, 4),
            "precision": round(val_metrics.precision, 4),
            "recall": round(val_metrics.recall, 4),
            "f1": round(val_metrics.f1_score, 4),
            "accuracy": round(class_metrics.accuracy, 4),
            "balanced_accuracy": round(class_metrics.balanced_accuracy, 4),
            "inference_time_ms": round(val_metrics.inference_time_ms, 2),
            "fps": round(val_metrics.fps, 1),
        },
        "dataset_split": {
            "train": "train/images",
            "val": "valid/images",
            "test": "test/images",
            "isolation_rule": "Flight-based Group Split (sem vazamento de voo)",
        },
    }
    best_json_v2.write_text(json.dumps(manifest_v2, indent=2), encoding="utf-8")
    print(f"   - Manifesto JSON gerado: {best_json_v2}")

    # Relatório em PDF e Excel
    benchmark_res = ModelBenchmarkResult(
        model_name="YOLOv11n (Revalidation v2)",
        precision=val_metrics.precision,
        recall=val_metrics.recall,
        f1_score=val_metrics.f1_score,
        map50=val_metrics.map50,
        map50_95=val_metrics.map50_95,
        inference_time_ms=val_metrics.inference_time_ms,
        fps=val_metrics.fps,
    )

    report_data = ScientificValidationReportData(
        model_name="YOLOv11n SolarGuard Vision (Revalidação 2026)",
        dataset_name="Thermal PV Mestrado (Split Independente)",
        metrics=class_metrics,
        benchmark=benchmark_res,
        confusion_matrix_img=cm_img_path,
        notes=(
            "Revalidação experimental v2 conduzida no âmbito da dissertação de mestrado. "
            "Avaliação independente com isolamento estrito de voos entre treino, validação e teste. "
            "Métricas calculadas conforme a formulação canônica de detecção de objetos com IoU >= 0.45."
        ),
    )

    sci_reporter = ScientificValidationReport()
    pdf_path = out_dir / "relatorio_revalidacao_2026.pdf"
    xlsx_path = out_dir / "metricas_revalidacao_2026.xlsx"
    sci_reporter.export_pdf(report_data, pdf_path)
    sci_reporter.export_excel(report_data, xlsx_path)
    print(f"   - Relatório PDF: {pdf_path}")
    print(f"   - Relatório Excel: {xlsx_path}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"REVALIDAÇÃO EXPERIMENTAL 2026 CONCLUÍDA EM {elapsed:.2f}s!")
    print(f"TODOS OS ARQUIVOS SALVOS EM: {out_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
