"""
Mapeadores (Row Mappers) entre registros relacionais do SQLite e Entidades de Domínio.
Mantém o desacoplamento e conversão de tipos de dados (datas, enums, value objects).
"""

import sqlite3
from datetime import datetime
from typing import Optional

from src.domain.entities.client import Client
from src.domain.entities.project import Project
from src.domain.entities.inspection import Inspection
from src.domain.entities.thermal_image import ThermalImage
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.entities.report import Report, ReportType
from src.domain.entities.user import User
from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.enums.inspection_status import InspectionStatus
from src.domain.enums.user_role import UserRole

from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.domain.value_objects.delta_t import DeltaT
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.thermal_matrix_meta import ThermalMatrixMeta


def _parse_datetime(val: Optional[str | datetime]) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return None


def row_to_client(row: sqlite3.Row) -> Client:
    """Converte linha do SQLite para entidade Client."""
    return Client(
        id=row["id"],
        name=row["name"],
        document=row["document"],
        email=row["email"],
        phone=row["phone"],
        address=row["address"],
        created_at=_parse_datetime(row["created_at"]) or datetime.now(),
    )


def row_to_project(row: sqlite3.Row) -> Project:
    """Converte linha do SQLite para entidade Project."""
    coord = None
    if row["latitude"] is not None and row["longitude"] is not None:
        coord = GeoCoordinate(
            latitude=row["latitude"],
            longitude=row["longitude"],
            altitude_meters=row["altitude_meters"],
        )

    return Project(
        id=row["id"],
        client_id=row["client_id"],
        name=row["name"],
        client_name=row["client_name"],
        location_name=row["location_name"],
        capacity_kwp=row["capacity_kwp"],
        coordinate=coord,
        module_manufacturer=row["module_manufacturer"],
        module_model=row["module_model"],
        created_at=_parse_datetime(row["created_at"]) or datetime.now(),
    )


def row_to_inspection(row: sqlite3.Row) -> Inspection:
    """Converte linha do SQLite para entidade Inspection."""
    return Inspection(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        inspector_name=row["inspector_name"],
        drone_model=row["drone_model"] or "DJI Matrice 4T",
        status=InspectionStatus(row["status"]),
        irradiance_w_m2=row["irradiance_w_m2"],
        ambient_temp_celsius=row["ambient_temp_celsius"],
        wind_speed_m_s=row["wind_speed_m_s"],
        notes=row["notes"],
        date=_parse_datetime(row["date"]) or datetime.now(),
    )


def row_to_thermal_image(row: sqlite3.Row) -> ThermalImage:
    """Converte linha do SQLite para entidade ThermalImage."""
    coord = None
    if row["latitude"] is not None and row["longitude"] is not None:
        coord = GeoCoordinate(
            latitude=row["latitude"],
            longitude=row["longitude"],
            altitude_meters=row["altitude_meters"],
        )

    meta = None
    if row["emissivity"] is not None:
        meta = ThermalMatrixMeta(
            emissivity=row["emissivity"],
            reflected_temp_celsius=row["reflected_temp_celsius"] or 25.0,
            ambient_temp_celsius=row["ambient_temp_celsius"] or 28.0,
            relative_humidity=row["relative_humidity"] or 0.5,
            distance_meters=row["distance_meters"] or 25.0,
            min_temp_celsius=row["min_temp_celsius"] or 20.0,
            max_temp_celsius=row["max_temp_celsius"] or 65.0,
            avg_temp_celsius=row["avg_temp_celsius"] or 38.0,
            sensor_width=row["width"] or 640,
            sensor_height=row["height"] or 512,
        )

    return ThermalImage(
        id=row["id"],
        inspection_id=row["inspection_id"],
        file_path=row["file_path"],
        filename=row["filename"],
        width=row["width"],
        height=row["height"],
        coordinate=coord,
        flight_altitude_meters=row["flight_altitude_meters"],
        gimbal_pitch_degrees=row["gimbal_pitch_degrees"],
        gimbal_yaw_degrees=row["gimbal_yaw_degrees"],
        thermal_meta=meta,
        is_analyzed=bool(row["is_analyzed"]),
        captured_at=_parse_datetime(row["captured_at"]),
    )


def row_to_thermal_anomaly(row: sqlite3.Row) -> ThermalAnomaly:
    """Converte linha do SQLite para entidade ThermalAnomaly."""
    bbox = BoundingBox(
        x_min=row["bbox_xmin"],
        y_min=row["bbox_ymin"],
        x_max=row["bbox_xmax"],
        y_max=row["bbox_ymax"],
        is_normalized=bool(row["bbox_is_normalized"]),
    )

    delta_t = None
    if row["delta_t_ref_temp"] is not None:
        delta_t = DeltaT(
            t_max_celsius=row["max_temp_celsius"],
            t_ref_celsius=row["delta_t_ref_temp"],
        )

    return ThermalAnomaly(
        id=row["id"],
        image_id=row["image_id"],
        anomaly_type=AnomalyType(row["anomaly_type"]),
        severity=SeverityLevel(row["severity"]),
        confidence=row["confidence"],
        bbox=bbox,
        max_temp_celsius=row["max_temp_celsius"],
        min_temp_celsius=row["min_temp_celsius"],
        avg_temp_celsius=row["avg_temp_celsius"],
        delta_t=delta_t,
        crop_path=row["crop_path"],
        notes=row["notes"],
        created_at=_parse_datetime(row["created_at"]) or datetime.now(),
    )


def row_to_report(row: sqlite3.Row) -> Report:
    """Converte linha do SQLite para entidade Report."""
    return Report(
        id=row["id"],
        inspection_id=row["inspection_id"],
        title=row["title"],
        report_type=ReportType(row["report_type"]),
        file_path=row["file_path"],
        file_size_bytes=row["file_size_bytes"] or 0,
        generated_by=row["generated_by"],
        generated_at=_parse_datetime(row["generated_at"]) or datetime.now(),
    )


def row_to_user(row: sqlite3.Row) -> User:
    """Converte linha do SQLite para entidade User com suporte retrocompatível a must_change_password e bloqueio."""
    keys = row.keys() if hasattr(row, "keys") else []
    must_change = bool(row["must_change_password"]) if "must_change_password" in keys else False
    failed_attempts = int(row["failed_login_attempts"]) if ("failed_login_attempts" in keys and row["failed_login_attempts"] is not None) else 0
    locked_until = _parse_datetime(row["locked_until"]) if "locked_until" in keys else None
    lockout_count = int(row["lockout_count"]) if ("lockout_count" in keys and row["lockout_count"] is not None) else 0
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        salt=row["salt"],
        full_name=row["full_name"],
        email=row["email"],
        role=UserRole(row["role"]),
        is_active=bool(row["is_active"]),
        must_change_password=must_change,
        failed_login_attempts=failed_attempts,
        locked_until=locked_until,
        lockout_count=lockout_count,
        last_login=_parse_datetime(row["last_login"]),
        created_at=_parse_datetime(row["created_at"]) or datetime.now(),
    )

