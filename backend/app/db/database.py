import os
import sqlite3
import uuid
from pathlib import Path

import bcrypt


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "satellite.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dataset_sources (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    satellite TEXT,
    sensor TEXT,
    product_level TEXT,
    licence TEXT,
    source_url TEXT,
    acquisition_start TEXT,
    acquisition_end TEXT,
    local_path TEXT,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    dataset_source_id TEXT,
    source TEXT,
    satellite TEXT,
    sensor TEXT,
    product_name TEXT,
    product_level TEXT,
    acquisition_datetime TEXT,
    processing_datetime TEXT,
    file_path TEXT,
    file_size INTEGER,
    checksum TEXT,
    crs TEXT,
    bounding_box TEXT,
    resolution TEXT,
    width INTEGER,
    height INTEGER,
    band_count INTEGER,
    bands TEXT,
    polarization TEXT,
    orbit_info TEXT,
    cloud_cover REAL,
    processing_status TEXT,
    quality_status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_source_id)
        REFERENCES dataset_sources(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tiles (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    tile_index TEXT,
    bounds TEXT,
    centroid TEXT,
    crs TEXT,
    width INTEGER,
    height INTEGER,
    resolution TEXT,
    image_path TEXT,
    thumbnail_path TEXT,
    mask_path TEXT,
    embedding_id TEXT,
    processing_status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scene_id)
        REFERENCES scenes(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    scene_id TEXT,
    tile_id TEXT,
    vector BLOB,
    vector_dimension INTEGER,
    source TEXT,
    model_name TEXT,
    model_version TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scene_id)
        REFERENCES scenes(id)
        ON DELETE CASCADE,
    FOREIGN KEY(tile_id)
        REFERENCES tiles(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS change_detections (
    id TEXT PRIMARY KEY,
    scene_a_id TEXT,
    scene_b_id TEXT,
    tile_a_id TEXT,
    tile_b_id TEXT,
    change_type TEXT,
    confidence REAL,
    quality_score REAL,
    changed_area REAL,
    earliest_supporting_observation TEXT,
    change_map_path TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scene_a_id)
        REFERENCES scenes(id)
        ON DELETE SET NULL,
    FOREIGN KEY(scene_b_id)
        REFERENCES scenes(id)
        ON DELETE SET NULL,
    FOREIGN KEY(tile_a_id)
        REFERENCES tiles(id)
        ON DELETE SET NULL,
    FOREIGN KEY(tile_b_id)
        REFERENCES tiles(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS processing_runs (
    id TEXT PRIMARY KEY,
    run_type TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS analyst_reviews (
    id TEXT PRIMARY KEY,
    change_id TEXT,
    decision TEXT,
    reason TEXT,
    reviewer TEXT,
    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processing_run_id TEXT,
    FOREIGN KEY(change_id)
        REFERENCES change_detections(id)
        ON DELETE CASCADE,
    FOREIGN KEY(processing_run_id)
        REFERENCES processing_runs(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS provenance (
    id TEXT PRIMARY KEY,
    entity_type TEXT,
    entity_id TEXT,
    input_files TEXT,
    input_checksums TEXT,
    model_name TEXT,
    model_version TEXT,
    model_source TEXT,
    model_license TEXT,
    steps TEXT,
    parameters TEXT,
    software_version TEXT,
    timestamp TEXT,
    hardware TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quality_metrics (
    id TEXT PRIMARY KEY,
    change_id TEXT,
    cloud_coverage REAL,
    valid_pixels REAL,
    registration_quality REAL,
    illumination_consistency REAL,
    overlap_ratio REAL,
    sensor_compatibility REAL,
    quality_score REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(change_id)
        REFERENCES change_detections(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clustering_results (
    id TEXT PRIMARY KEY,
    cluster_id TEXT,
    tile_id TEXT,
    centroid TEXT,
    algorithm TEXT,
    model_name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(tile_id)
        REFERENCES tiles(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    organization TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id TEXT PRIMARY KEY,
    dataset_source_id TEXT,
    source_path TEXT,
    status TEXT,
    total_files INTEGER DEFAULT 0,
    valid_files INTEGER DEFAULT 0,
    invalid_files INTEGER DEFAULT 0,
    total_scenes INTEGER DEFAULT 0,
    total_tiles INTEGER DEFAULT 0,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_source_id)
        REFERENCES dataset_sources(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS aoi (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    geometry TEXT NOT NULL,
    crs TEXT,
    area REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dataset_quality (
    id TEXT PRIMARY KEY,
    scene_id TEXT,
    no_data_ratio REAL,
    cloud_ratio REAL,
    shadow_ratio REAL,
    valid_pixel_ratio REAL,
    registration_quality REAL,
    illumination_consistency REAL,
    quality_score REAL,
    status TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scene_id)
        REFERENCES scenes(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dataset_checksums (
    id TEXT PRIMARY KEY,
    scene_id TEXT,
    file_path TEXT NOT NULL,
    algorithm TEXT NOT NULL DEFAULT 'SHA256',
    checksum TEXT NOT NULL,
    file_size INTEGER,
    calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scene_id)
        REFERENCES scenes(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS retrieval_queries (
    id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_type TEXT NOT NULL,
    expected_result TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id TEXT PRIMARY KEY,
    evaluation_type TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    dataset_name TEXT,
    model_name TEXT,
    run_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id)
        REFERENCES processing_runs(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_scenes_source
ON scenes(source);

CREATE INDEX IF NOT EXISTS idx_scenes_sensor
ON scenes(sensor);

CREATE INDEX IF NOT EXISTS idx_scenes_acquisition
ON scenes(acquisition_datetime);

CREATE INDEX IF NOT EXISTS idx_scenes_status
ON scenes(processing_status);

CREATE INDEX IF NOT EXISTS idx_scenes_dataset_source
ON scenes(dataset_source_id);

CREATE INDEX IF NOT EXISTS idx_tiles_scene
ON tiles(scene_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_tile
ON embeddings(tile_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_scene
ON embeddings(scene_id);

CREATE INDEX IF NOT EXISTS idx_change_scene_a
ON change_detections(scene_a_id);

CREATE INDEX IF NOT EXISTS idx_change_scene_b
ON change_detections(scene_b_id);

CREATE INDEX IF NOT EXISTS idx_users_email
ON users(email);

CREATE INDEX IF NOT EXISTS idx_users_role
ON users(role);

CREATE INDEX IF NOT EXISTS idx_users_status
ON users(status);

CREATE INDEX IF NOT EXISTS idx_ingestion_source
ON ingestion_runs(dataset_source_id);
"""


def get_admin_credentials():
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if not admin_email or not admin_password:
        return None
    return admin_email.strip().lower(), admin_password


def create_admin_user(conn):
    credentials = get_admin_credentials()
    if credentials is None:
        return
    admin_email, admin_password = credentials

    existing_admin = conn.execute(
        """
        SELECT id
        FROM users
        WHERE role = 'ADMIN'
        LIMIT 1
        """
    ).fetchone()

    password_hash = bcrypt.hashpw(
        admin_password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    if existing_admin is None:
        conn.execute(
            """
            INSERT INTO users (
                id,
                full_name,
                email,
                organization,
                password_hash,
                role,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                "System Administrator",
                admin_email,
                "DGIS Operations",
                password_hash,
                "ADMIN",
                "ACTIVE",
            ),
        )
    else:
        conn.execute(
            """
            UPDATE users
            SET
                email = ?,
                password_hash = ?,
                status = 'ACTIVE'
            WHERE id = ?
            """,
            (
                admin_email,
                password_hash,
                existing_admin["id"],
            ),
        )


def initialize_schema(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    existing_tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "scenes" in existing_tables:
        scene_columns = {row[1] for row in conn.execute("PRAGMA table_info(scenes)")}
        if "dataset_source_id" not in scene_columns:
            conn.execute("ALTER TABLE scenes ADD COLUMN dataset_source_id TEXT")
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        """
        UPDATE provenance
        SET model_name = 'LocalHistogramBaseline',
            model_source = 'Experimental color-histogram fallback; not a multimodal model',
            model_license = 'Project license not specified'
        WHERE model_name = 'LocalCLIPEmbeddingModel'
        """
    )
    conn.execute(
        "UPDATE embeddings SET model_name = 'LocalHistogramBaseline' WHERE model_name = 'LocalCLIPEmbeddingModel'"
    )
    create_admin_user(conn)
    conn.commit()


def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def init_db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    try:
        initialize_schema(conn)
    finally:
        conn.close()


def database_exists():
    return DB_PATH.exists()


def get_database_path():
    return DB_PATH


def get_table_names():
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        return [row["name"] for row in rows]

    finally:
        conn.close()


def get_database_stats():
    conn = get_connection()

    try:
        tables = [
            "dataset_sources",
            "scenes",
            "tiles",
            "embeddings",
            "change_detections",
            "analyst_reviews",
            "processing_runs",
            "provenance",
            "quality_metrics",
            "clustering_results",
            "users",
            "sessions",
            "password_reset_tokens",
            "ingestion_runs",
            "aoi",
            "dataset_quality",
            "dataset_checksums",
            "retrieval_queries",
            "evaluation_results",
        ]

        stats = {}

        for table in tables:
            row = conn.execute(
                f"SELECT COUNT(*) AS count FROM {table}"
            ).fetchone()

            stats[table] = row["count"]

        return stats

    finally:
        conn.close()


if __name__ == "__main__":
    print("Initializing SIH26227 database...")

    init_db()

    print(f"\nDatabase created at:")
    print(DB_PATH)

    print("\nTables:")

    for table in get_table_names():
        print(f" - {table}")

    print("\nDatabase statistics:")

    stats = get_database_stats()

    for table, count in stats.items():
        print(f" - {table}: {count}")

    print("\nDatabase initialization completed successfully.")