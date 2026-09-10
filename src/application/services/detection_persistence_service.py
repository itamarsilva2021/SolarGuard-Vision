"""
Serviço de Aplicação para Persistência Científica de Inferências de IA e Termografia.
Persiste de forma transacional imagem, classe, confiança, bounding box, delta T,
temperaturas máxima e média, e classificação de severidade normativa.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from src.core.result import Result, Success, Failure
from src.core.logger import get_logger
from src.domain.interfaces.repositories import IThermalImageRepository, IThermalAnomalyRepository
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.enums.severity_level import SeverityLevel
from src.domain.enums.anomaly_type import AnomalyType
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.delta_t import DeltaT
from src.application.dtos.scientific_detection_dtos import (
    ThermalAnalysisDTO,
    DeltaTResultDTO,
    YoloPredictionDTO,
    DetectionRecordDTO,
    DetectionPersistenceRequest,
    DetectionPersistenceResult,
)
from src.infrastructure.database.repositories.sqlite_detection_repository import (
    SqliteDetectionRepository,
)

logger = get_logger("DetectionPersistenceService")


class DetectionPersistenceService:
    """
    Orquestrador para a persistência científica completa das inferências de IA,
    cálculos de Delta T e radiometria em conformidade com a norma IEC TS 62446-3.
    """

    def __init__(
        self,
        detection_repo: Optional[SqliteDetectionRepository] = None,
        image_repo: Optional[IThermalImageRepository] = None,
        anomaly_repo: Optional[IThermalAnomalyRepository] = None,
    ) -> None:
        self.detection_repo = detection_repo or SqliteDetectionRepository()
        self.image_repo = image_repo
        self.anomaly_repo = anomaly_repo

    def persist_inference(
        self, request: DetectionPersistenceRequest
    ) -> Result[DetectionPersistenceResult, str]:
        """
        Executa a persistência científica completa e transacional das detecções da imagem.
        
        :param request: Objeto com id da imagem, anomalias e parâmetros radiométricos.
        :return: Result contendo DetectionPersistenceResult ou erro.
        """
        # 1. Validação de existência da imagem se image_repo disponível
        if self.image_repo:
            img = self.image_repo.get_by_id(request.image_id)
            if not img:
                return Failure(f"Imagem térmica não encontrada com ID: {request.image_id}")

        if not request.anomalies:
            logger.info(f"Nenhuma anomalia a persistir para a imagem {request.image_id}. Criando análise de fundo.")

        # 2. Resumo de temperaturas da cena
        if request.anomalies:
            max_temps = [a.max_temp_celsius for a in request.anomalies]
            min_temps = [a.min_temp_celsius for a in request.anomalies if a.min_temp_celsius is not None]
            avg_temps = [a.avg_temp_celsius for a in request.anomalies if a.avg_temp_celsius is not None]
            scene_max = max(max_temps)
            scene_min = min(min_temps) if min_temps else scene_max - 15.0
            scene_avg = float(sum(avg_temps) / len(avg_temps)) if avg_temps else (scene_max + scene_min) / 2.0
        else:
            scene_min = 25.0
            scene_max = 45.0
            scene_avg = 35.0

        ref_temp = request.reference_temp_celsius or (scene_avg - 5.0)
        global_delta = round(scene_max - ref_temp, 2)

        # 3. Criação do Registro de Análise Térmica
        analysis_dto = ThermalAnalysisDTO(
            image_id=request.image_id,
            emissivity=request.emissivity,
            reflected_temp_celsius=request.reflected_temp_celsius,
            ambient_temp_celsius=request.ambient_temp_celsius,
            relative_humidity=request.relative_humidity,
            distance_meters=request.distance_meters,
            min_temp_celsius=round(scene_min, 2),
            max_temp_celsius=round(scene_max, 2),
            avg_temp_celsius=round(scene_avg, 2),
            global_delta_t=global_delta,
            notes=request.notes,
        )

        predictions_list: List[YoloPredictionDTO] = []
        delta_t_list: List[DeltaTResultDTO] = []
        detections_list: List[DetectionRecordDTO] = []
        critical_count = 0

        # Mapeamento de classes de anomalias para id numérico YOLO
        class_name_to_id = {
            "hotspot": 0,
            "disconnected_module": 1,
            "pid": 2,
            "soiling": 3,
            "shading": 4,
            "healthy_module": 5,
        }

        # 4. Processamento individual de cada anomalia
        for anomaly in request.anomalies:
            cls_name = anomaly.anomaly_type.value if hasattr(anomaly.anomaly_type, "value") else str(anomaly.anomaly_type)
            cls_id = class_name_to_id.get(cls_name, 0)

            # A. Predição YOLO
            pred_id = str(uuid.uuid4())
            pred_dto = YoloPredictionDTO(
                id=pred_id,
                image_id=request.image_id,
                class_id=cls_id,
                class_name=cls_name,
                confidence=anomaly.confidence,
                bbox=anomaly.bbox,
            )
            predictions_list.append(pred_dto)

            # B. Delta T e Severidade Normativa (IEC TS 62446-3)
            dt_id = str(uuid.uuid4())
            if anomaly.delta_t is not None and hasattr(anomaly.delta_t, "value"):
                calculated_dt = float(anomaly.delta_t.value)
                hotspot_t = getattr(anomaly.delta_t, "t_max_celsius", anomaly.max_temp_celsius)
                ref_t = getattr(anomaly.delta_t, "t_ref_celsius", ref_temp)
            elif anomaly.delta_t is not None and hasattr(anomaly.delta_t, "delta_t"):
                calculated_dt = float(anomaly.delta_t.delta_t)
                hotspot_t = getattr(anomaly.delta_t, "hotspot_temp", anomaly.max_temp_celsius)
                ref_t = getattr(anomaly.delta_t, "ref_temp", ref_temp)
            elif anomaly.delta_t is not None and isinstance(anomaly.delta_t, (int, float)):
                calculated_dt = float(anomaly.delta_t)
                hotspot_t = anomaly.max_temp_celsius
                ref_t = round(hotspot_t - calculated_dt, 2)
            else:
                hotspot_t = anomaly.max_temp_celsius
                ref_t = ref_temp
                calculated_dt = round(hotspot_t - ref_t, 2)

            # Classificação normativa IEC TS 62446-3
            sev_level = SeverityLevel.from_delta_t(calculated_dt)
            if sev_level == SeverityLevel.CRITICAL:
                iec_class_str = "Classe 3"
                critical_count += 1
            elif sev_level == SeverityLevel.MEDIUM:
                iec_class_str = "Classe 2"
            elif sev_level == SeverityLevel.LOW:
                iec_class_str = "Classe 1"
            else:
                iec_class_str = "Informativo"

            dt_dto = DeltaTResultDTO(
                id=dt_id,
                analysis_id=analysis_dto.id,
                image_id=request.image_id,
                hotspot_temp_celsius=hotspot_t,
                reference_temp_celsius=ref_t,
                delta_t=calculated_dt,
                severity=sev_level.value,
                iec_class=iec_class_str,
            )
            delta_t_list.append(dt_dto)

            # C. Detecção Consolidada
            det_dto = DetectionRecordDTO(
                image_id=request.image_id,
                analysis_id=analysis_dto.id,
                delta_t_id=dt_id,
                yolo_prediction_id=pred_id,
                class_name=cls_name,
                confidence=anomaly.confidence,
                bbox=anomaly.bbox,
                delta_t=calculated_dt,
                max_temp_celsius=anomaly.max_temp_celsius,
                avg_temp_celsius=anomaly.avg_temp_celsius or (anomaly.max_temp_celsius - 5.0),
                min_temp_celsius=anomaly.min_temp_celsius,
                severity=sev_level.value,
                crop_path=getattr(anomaly, "crop_path", None),
                notes=getattr(anomaly, "notes", None),
            )
            detections_list.append(det_dto)

            # D. Compatibilidade com tabela legada thermal_anomalies
            if self.anomaly_repo:
                try:
                    anomaly.image_id = request.image_id
                    anomaly.severity = sev_level
                    self.anomaly_repo.save(anomaly)
                except Exception as leg_err:
                    logger.warning(f"Erro ao sincronizar anomalia na tabela legada: {leg_err}")

        # 5. Execução da Transação Atômica no Banco SQLite
        try:
            self.detection_repo.save_full_inference_transaction(
                analysis=analysis_dto,
                predictions=predictions_list,
                delta_t_list=delta_t_list,
                detections=detections_list,
            )
        except Exception as db_err:
            msg = f"Falha na transação atômica de persistência científica: {db_err}"
            logger.error(msg)
            return Failure(msg)

        result = DetectionPersistenceResult(
            image_id=request.image_id,
            analysis_id=analysis_dto.id,
            saved_detections_count=len(detections_list),
            saved_predictions_count=len(predictions_list),
            saved_delta_t_count=len(delta_t_list),
            critical_anomalies_count=critical_count,
            created_at=datetime.now(),
            detections=detections_list,
        )
        return Success(result)

    def get_detections_for_image(self, image_id: str) -> List[DetectionRecordDTO]:
        """Consulta todas as detecções científicas de uma imagem."""
        return self.detection_repo.get_detections_by_image_id(image_id)

    def get_detections_for_inspection(self, inspection_id: str) -> List[DetectionRecordDTO]:
        """Consulta todas as detecções científicas de uma inspeção."""
        return self.detection_repo.get_detections_by_inspection_id(inspection_id)

    def get_thermal_analysis(self, image_id: str) -> Optional[ThermalAnalysisDTO]:
        """Recupera os metadados da sessão radiométrica da imagem."""
        return self.detection_repo.get_thermal_analysis_by_image_id(image_id)
