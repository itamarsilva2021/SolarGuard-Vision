-- ==============================================================================
-- SolarGuard Vision - Schema do Banco de Dados Relacional SQLite
-- Otimizado com Foreign Keys ativas, índices de consulta e integridade relacional
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- 1. TABELA DE CLIENTES
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    document TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    created_at TEXT NOT NULL
);

-- 2. TABELA DE PROJETOS / USINAS FOTOVOLTAICAS
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    client_id TEXT REFERENCES clients(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    client_name TEXT NOT NULL,
    location_name TEXT NOT NULL,
    capacity_kwp REAL NOT NULL,
    latitude REAL,
    longitude REAL,
    altitude_meters REAL,
    module_manufacturer TEXT,
    module_model TEXT,
    created_at TEXT NOT NULL
);

-- 3. TABELA DE INSPEÇÕES
CREATE TABLE IF NOT EXISTS inspections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    inspector_name TEXT NOT NULL,
    drone_model TEXT NOT NULL DEFAULT 'DJI Matrice 4T',
    status TEXT NOT NULL,
    irradiance_w_m2 REAL,
    ambient_temp_celsius REAL,
    wind_speed_m_s REAL,
    notes TEXT,
    date TEXT NOT NULL
);

-- 4. TABELA DE IMAGENS TÉRMICAS
CREATE TABLE IF NOT EXISTS thermal_images (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    width INTEGER NOT NULL DEFAULT 640,
    height INTEGER NOT NULL DEFAULT 512,
    latitude REAL,
    longitude REAL,
    altitude_meters REAL,
    flight_altitude_meters REAL,
    gimbal_pitch_degrees REAL,
    gimbal_yaw_degrees REAL,
    is_analyzed INTEGER NOT NULL DEFAULT 0,
    captured_at TEXT,
    
    -- Metadados térmicos radiométricos DJI
    emissivity REAL,
    reflected_temp_celsius REAL,
    ambient_temp_celsius REAL,
    relative_humidity REAL,
    distance_meters REAL,
    min_temp_celsius REAL,
    max_temp_celsius REAL,
    avg_temp_celsius REAL
);

-- 5. TABELA DE FALHAS / ANOMALIAS TÉRMICAS
CREATE TABLE IF NOT EXISTS thermal_anomalies (
    id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL REFERENCES thermal_images(id) ON DELETE CASCADE,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_xmin REAL NOT NULL,
    bbox_ymin REAL NOT NULL,
    bbox_xmax REAL NOT NULL,
    bbox_ymax REAL NOT NULL,
    bbox_is_normalized INTEGER NOT NULL DEFAULT 1,
    max_temp_celsius REAL NOT NULL,
    min_temp_celsius REAL,
    avg_temp_celsius REAL,
    delta_t_ref_temp REAL,
    crop_path TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

-- 6. TABELA DE RELATÓRIOS GERADOS
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    report_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    generated_by TEXT,
    generated_at TEXT NOT NULL
);

-- 7. TABELA DE USUÁRIOS E CONTROLE DE ACESSO
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'inspector',
    is_active INTEGER NOT NULL DEFAULT 1,
    last_login TEXT,
    created_at TEXT NOT NULL
);

-- 8. TABELA DE EXPERIMENTOS E BENCHMARKS DE IA (YOLOv11)
CREATE TABLE IF NOT EXISTS ai_experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    yolo_version TEXT NOT NULL DEFAULT 'YOLOv11',
    epochs INTEGER NOT NULL,
    batch_size INTEGER NOT NULL,
    learning_rate REAL NOT NULL,
    precision REAL NOT NULL,
    recall REAL NOT NULL,
    f1_score REAL NOT NULL,
    map50 REAL NOT NULL,
    map50_95 REAL NOT NULL,
    dataset_path TEXT,
    weights_path TEXT,
    training_duration_seconds REAL,
    hyperparameters_json TEXT,
    notes TEXT
);

-- 9. TABELA DE ANÁLISE TÉRMICA CIENTÍFICA
CREATE TABLE IF NOT EXISTS thermal_analysis (
    id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL REFERENCES thermal_images(id) ON DELETE CASCADE,
    emissivity REAL NOT NULL,
    reflected_temp_celsius REAL NOT NULL,
    ambient_temp_celsius REAL NOT NULL,
    relative_humidity REAL NOT NULL,
    distance_meters REAL NOT NULL,
    min_temp_celsius REAL NOT NULL,
    max_temp_celsius REAL NOT NULL,
    avg_temp_celsius REAL NOT NULL,
    global_delta_t REAL,
    algorithm_version TEXT NOT NULL DEFAULT 'v1.0-scientific',
    notes TEXT,
    created_at TEXT NOT NULL
);

-- 10. TABELA DE RESULTADOS DE DELTA T (IEC TS 62446-3)
CREATE TABLE IF NOT EXISTS delta_t_results (
    id TEXT PRIMARY KEY,
    analysis_id TEXT REFERENCES thermal_analysis(id) ON DELETE CASCADE,
    image_id TEXT NOT NULL REFERENCES thermal_images(id) ON DELETE CASCADE,
    hotspot_temp_celsius REAL NOT NULL,
    reference_temp_celsius REAL NOT NULL,
    delta_t REAL NOT NULL,
    severity TEXT NOT NULL,
    iec_class TEXT NOT NULL,
    reference_type TEXT NOT NULL DEFAULT 'healthy_module',
    created_at TEXT NOT NULL
);

-- 11. TABELA DE PREDIÇÕES BRUTAS YOLO
CREATE TABLE IF NOT EXISTS yolo_predictions (
    id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL REFERENCES thermal_images(id) ON DELETE CASCADE,
    model_version TEXT NOT NULL DEFAULT 'YOLOv11',
    inference_time_ms REAL NOT NULL,
    class_id INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_xmin REAL NOT NULL,
    bbox_ymin REAL NOT NULL,
    bbox_xmax REAL NOT NULL,
    bbox_ymax REAL NOT NULL,
    created_at TEXT NOT NULL
);

-- 12. TABELA DE DETECÇÕES CONSOLIDADAS CIENTÍFICAS
CREATE TABLE IF NOT EXISTS detections (
    id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL REFERENCES thermal_images(id) ON DELETE CASCADE,
    analysis_id TEXT REFERENCES thermal_analysis(id) ON DELETE SET NULL,
    delta_t_id TEXT REFERENCES delta_t_results(id) ON DELETE SET NULL,
    yolo_prediction_id TEXT REFERENCES yolo_predictions(id) ON DELETE SET NULL,
    class_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_xmin REAL NOT NULL,
    bbox_ymin REAL NOT NULL,
    bbox_xmax REAL NOT NULL,
    bbox_ymax REAL NOT NULL,
    delta_t REAL NOT NULL,
    max_temp_celsius REAL NOT NULL,
    avg_temp_celsius REAL NOT NULL,
    min_temp_celsius REAL,
    severity TEXT NOT NULL,
    crop_path TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

-- 13. TABELA DE MÓDULOS FOTOVOLTAICOS FÍSICOS SEGMENTADOS
CREATE TABLE IF NOT EXISTS solar_panels (
    id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL REFERENCES thermal_images(id) ON DELETE CASCADE,
    string_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    col_index INTEGER NOT NULL,
    panel_identifier TEXT NOT NULL,
    bbox_xmin REAL NOT NULL,
    bbox_ymin REAL NOT NULL,
    bbox_xmax REAL NOT NULL,
    bbox_ymax REAL NOT NULL,
    created_at TEXT NOT NULL
);

-- 14. TABELA DE ASSOCIAÇÃO ENTRE FALHAS E PAINÉIS FÍSICOS
CREATE TABLE IF NOT EXISTS panel_mappings (
    id TEXT PRIMARY KEY,
    detection_id TEXT REFERENCES detections(id) ON DELETE CASCADE,
    panel_id TEXT REFERENCES solar_panels(id) ON DELETE CASCADE,
    image_id TEXT NOT NULL REFERENCES thermal_images(id) ON DELETE CASCADE,
    string_id TEXT NOT NULL,
    row_index INTEGER NOT NULL,
    col_index INTEGER NOT NULL,
    panel_identifier TEXT NOT NULL,
    overlap_iou REAL NOT NULL,
    relative_x REAL NOT NULL,
    relative_y REAL NOT NULL,
    created_at TEXT NOT NULL
);

-- ==============================================================================
-- ÍNDICES PARA CONSULTAS DE ALTO DESEMPENHO
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_projects_client_id ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_inspections_project_id ON inspections(project_id);
CREATE INDEX IF NOT EXISTS idx_thermal_images_inspection_id ON thermal_images(inspection_id);
CREATE INDEX IF NOT EXISTS idx_thermal_anomalies_image_id ON thermal_anomalies(image_id);
CREATE INDEX IF NOT EXISTS idx_thermal_anomalies_type ON thermal_anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_thermal_anomalies_severity ON thermal_anomalies(severity);
CREATE INDEX IF NOT EXISTS idx_reports_inspection_id ON reports(inspection_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_ai_experiments_created_at ON ai_experiments(created_at);
CREATE INDEX IF NOT EXISTS idx_thermal_analysis_image_id ON thermal_analysis(image_id);
CREATE INDEX IF NOT EXISTS idx_delta_t_results_image_id ON delta_t_results(image_id);
CREATE INDEX IF NOT EXISTS idx_delta_t_results_analysis_id ON delta_t_results(analysis_id);
CREATE INDEX IF NOT EXISTS idx_yolo_predictions_image_id ON yolo_predictions(image_id);
CREATE INDEX IF NOT EXISTS idx_detections_image_id ON detections(image_id);
CREATE INDEX IF NOT EXISTS idx_detections_class ON detections(class_name);
CREATE INDEX IF NOT EXISTS idx_detections_severity ON detections(severity);
CREATE INDEX IF NOT EXISTS idx_solar_panels_image_id ON solar_panels(image_id);
CREATE INDEX IF NOT EXISTS idx_solar_panels_string_id ON solar_panels(string_id);
CREATE INDEX IF NOT EXISTS idx_panel_mappings_detection_id ON panel_mappings(detection_id);
CREATE INDEX IF NOT EXISTS idx_panel_mappings_panel_id ON panel_mappings(panel_id);
CREATE INDEX IF NOT EXISTS idx_panel_mappings_image_id ON panel_mappings(image_id);


