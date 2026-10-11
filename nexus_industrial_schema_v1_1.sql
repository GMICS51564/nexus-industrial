-- ============================================================
-- NEXUS INDUSTRIAL — Schéma relationnel physique V1
-- Base cible : SQLite 3.38+
-- Encodage : UTF-8
--
-- IMPORTANT
-- - Schéma de prototype/démonstration ; ne pas utiliser directement
--   comme système de production nucléaire ou système qualité officiel.
-- - Exécuter avec PRAGMA foreign_keys = ON sur CHAQUE connexion.
-- - Les UUID sont stockés en TEXT.
-- - Horodatages stockés en UTC ISO-8601.
-- - Les données historiques ne sont pas supprimées en cascade.
-- - Les contrôles applicatifs complémentaires sont décrits dans la
--   documentation d'architecture.
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

BEGIN IMMEDIATE;

-- ============================================================
-- 00. IDENTITÉ, RÔLES, PERMISSIONS, PARAMÉTRAGE
-- ============================================================

CREATE TABLE users (
    id                  TEXT PRIMARY KEY,
    username            TEXT NOT NULL UNIQUE,
    email               TEXT UNIQUE,
    display_name        TEXT NOT NULL,
    password_hash       TEXT,
    auth_provider       TEXT NOT NULL DEFAULT 'local'
                        CHECK (auth_provider IN ('local','external','demo')),
    external_subject    TEXT,
    status              TEXT NOT NULL DEFAULT 'invited'
                        CHECK (status IN ('invited','active','suspended','disabled')),
    last_login_at       TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (auth_provider <> 'local' OR password_hash IS NOT NULL OR status = 'invited'),
    CHECK (auth_provider = 'local' OR external_subject IS NOT NULL)
);

CREATE UNIQUE INDEX uq_users_provider_subject
    ON users(auth_provider, external_subject)
    WHERE external_subject IS NOT NULL;

CREATE TABLE roles (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE permissions (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    description         TEXT NOT NULL,
    module              TEXT NOT NULL
);

CREATE TABLE user_roles (
    user_id             TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    role_id             TEXT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    scope_type          TEXT NOT NULL DEFAULT 'global'
                        CHECK (scope_type IN ('global','site','workshop','island','workstation')),
    scope_id            TEXT,
    assigned_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    assigned_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (user_id, role_id, scope_type, scope_id),
    CHECK ((scope_type = 'global' AND scope_id IS NULL) OR
           (scope_type <> 'global' AND scope_id IS NOT NULL))
);

CREATE TABLE role_permissions (
    role_id             TEXT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    permission_id       TEXT NOT NULL REFERENCES permissions(id) ON DELETE RESTRICT,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE app_settings (
    setting_key         TEXT PRIMARY KEY,
    setting_value       TEXT NOT NULL,
    value_type          TEXT NOT NULL DEFAULT 'string'
                        CHECK (value_type IN ('string','integer','number','boolean','json')),
    description         TEXT,
    updated_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE units (
    code                TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    dimension           TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    is_base_unit        INTEGER NOT NULL DEFAULT 0 CHECK (is_base_unit IN (0,1)),
    conversion_to_base  REAL CHECK (conversion_to_base IS NULL OR conversion_to_base > 0),
    CHECK (is_base_unit = 0 OR conversion_to_base = 1.0)
);

CREATE TABLE calendars (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    timezone            TEXT NOT NULL DEFAULT 'UTC',
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE shifts (
    id                  TEXT PRIMARY KEY,
    calendar_id         TEXT NOT NULL REFERENCES calendars(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    day_of_week         INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time          TEXT NOT NULL,
    end_time            TEXT NOT NULL,
    break_minutes       INTEGER NOT NULL DEFAULT 0 CHECK (break_minutes >= 0),
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    UNIQUE (calendar_id, code, day_of_week, valid_from)
);

CREATE TABLE calendar_exceptions (
    id                  TEXT PRIMARY KEY,
    calendar_id         TEXT NOT NULL REFERENCES calendars(id) ON DELETE RESTRICT,
    exception_date      TEXT NOT NULL,
    exception_type      TEXT NOT NULL
                        CHECK (exception_type IN ('closed','special_hours','holiday','maintenance')),
    start_time          TEXT,
    end_time            TEXT,
    description         TEXT,
    UNIQUE (calendar_id, exception_date, exception_type),
    CHECK ((exception_type = 'closed' AND start_time IS NULL AND end_time IS NULL)
        OR (exception_type <> 'closed' AND start_time IS NOT NULL AND end_time IS NOT NULL))
);

-- ============================================================
-- 01. ORGANISATION ET RESSOURCES
-- ============================================================

CREATE TABLE sites (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT,
    timezone            TEXT NOT NULL DEFAULT 'UTC',
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE workshops (
    id                  TEXT PRIMARY KEY,
    site_id             TEXT NOT NULL REFERENCES sites(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (site_id, code)
);

CREATE TABLE production_islands (
    id                  TEXT PRIMARY KEY,
    workshop_id         TEXT NOT NULL REFERENCES workshops(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (workshop_id, code)
);

CREATE TABLE workstations (
    id                  TEXT PRIMARY KEY,
    island_id           TEXT NOT NULL REFERENCES production_islands(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    location_reference  TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (island_id, code)
);

CREATE TABLE resources (
    id                  TEXT PRIMARY KEY,
    workstation_id      TEXT NOT NULL REFERENCES workstations(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    resource_type       TEXT NOT NULL
                        CHECK (resource_type IN ('machine','equipment','human_group','other')),
    capacity_unit       TEXT REFERENCES units(code) ON DELETE RESTRICT,
    nominal_capacity    REAL CHECK (nominal_capacity IS NULL OR nominal_capacity > 0),
    calendar_id         TEXT REFERENCES calendars(id) ON DELETE RESTRICT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive','retired')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================
-- 02. PRODUITS, VERSIONS, GAMMES ET OPÉRATIONS STANDARD
-- ============================================================

CREATE TABLE products (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT,
    base_unit_code      TEXT NOT NULL REFERENCES units(code) ON DELETE RESTRICT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE product_versions (
    id                  TEXT PRIMARY KEY,
    product_id          TEXT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    version_code        TEXT NOT NULL,
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','validated','superseded')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    UNIQUE (product_id, version_code),
    UNIQUE (id, product_id)
);

CREATE TABLE routes (
    id                  TEXT PRIMARY KEY,
    product_version_id  TEXT NOT NULL REFERENCES product_versions(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    version_code        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','validated','retired')),
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    UNIQUE (product_version_id, code, version_code),
    UNIQUE (id, product_version_id)
);

CREATE TABLE route_operations (
    id                      TEXT PRIMARY KEY,
    route_id                TEXT NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
    operation_code          TEXT NOT NULL,
    name                    TEXT NOT NULL,
    sequence_number         INTEGER NOT NULL CHECK (sequence_number > 0),
    default_workstation_id  TEXT REFERENCES workstations(id) ON DELETE RESTRICT,
    setup_time_seconds      INTEGER NOT NULL DEFAULT 0 CHECK (setup_time_seconds >= 0),
    cycle_time_seconds      INTEGER CHECK (cycle_time_seconds IS NULL OR cycle_time_seconds > 0),
    expected_yield          REAL CHECK (expected_yield IS NULL OR (expected_yield > 0 AND expected_yield <= 1)),
    is_quality_gate         INTEGER NOT NULL DEFAULT 0 CHECK (is_quality_gate IN (0,1)),
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (route_id, sequence_number),
    UNIQUE (route_id, operation_code),
    UNIQUE (id, route_id)
);

CREATE TABLE operation_resources (
    id                  TEXT PRIMARY KEY,
    route_operation_id  TEXT NOT NULL REFERENCES route_operations(id) ON DELETE RESTRICT,
    resource_id         TEXT NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
    required_quantity   REAL NOT NULL DEFAULT 1 CHECK (required_quantity > 0),
    is_mandatory        INTEGER NOT NULL DEFAULT 1 CHECK (is_mandatory IN (0,1)),
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    UNIQUE (route_operation_id, resource_id, valid_from)
);

-- ============================================================
-- 03. ORDRES DE FABRICATION ET EXÉCUTION
-- ============================================================

CREATE TABLE production_orders (
    id                  TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES data_sources(id) ON DELETE RESTRICT,
    order_number        TEXT NOT NULL,
    product_version_id  TEXT NOT NULL REFERENCES product_versions(id) ON DELETE RESTRICT,
    route_id            TEXT NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
    planned_quantity    REAL NOT NULL CHECK (planned_quantity > 0),
    unit_code           TEXT NOT NULL REFERENCES units(code) ON DELETE RESTRICT,
    planned_start_at    TEXT NOT NULL,
    planned_end_at      TEXT,
    actual_start_at     TEXT,
    actual_end_at       TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','planned','released','in_progress','completed','cancelled','on_hold')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (planned_end_at IS NULL OR planned_end_at >= planned_start_at),
    CHECK (actual_end_at IS NULL OR actual_start_at IS NULL OR actual_end_at >= actual_start_at),
    UNIQUE (source_id, order_number)
);

CREATE TABLE planned_operations (
    id                      TEXT PRIMARY KEY,
    production_order_id     TEXT NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    route_operation_id      TEXT NOT NULL REFERENCES route_operations(id) ON DELETE RESTRICT,
    sequence_number         INTEGER NOT NULL CHECK (sequence_number > 0),
    workstation_id          TEXT NOT NULL REFERENCES workstations(id) ON DELETE RESTRICT,
    planned_start_at        TEXT,
    planned_end_at          TEXT,
    planned_setup_seconds   INTEGER NOT NULL DEFAULT 0 CHECK (planned_setup_seconds >= 0),
    planned_run_seconds     INTEGER NOT NULL CHECK (planned_run_seconds >= 0),
    planned_quantity        REAL NOT NULL CHECK (planned_quantity > 0),
    status                  TEXT NOT NULL DEFAULT 'to_do'
                            CHECK (status IN ('to_do','ready','in_progress','completed','blocked','cancelled')),
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (planned_end_at IS NULL OR planned_start_at IS NULL OR planned_end_at >= planned_start_at),
    UNIQUE (production_order_id, sequence_number),
    UNIQUE (id, production_order_id)
);

CREATE TABLE operation_executions (
    id                  TEXT PRIMARY KEY,
    planned_operation_id TEXT NOT NULL REFERENCES planned_operations(id) ON DELETE RESTRICT,
    execution_number    INTEGER NOT NULL CHECK (execution_number > 0),
    resource_id         TEXT REFERENCES resources(id) ON DELETE RESTRICT,
    started_at          TEXT,
    ended_at            TEXT,
    execution_type      TEXT NOT NULL DEFAULT 'initial'
                        CHECK (execution_type IN ('initial','rework','trial')),
    status              TEXT NOT NULL DEFAULT 'planned'
                        CHECK (status IN ('planned','in_progress','completed','interrupted','cancelled')),
    recorded_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at),
    UNIQUE (planned_operation_id, execution_number),
    UNIQUE (id, planned_operation_id)
);

CREATE TABLE time_records (
    id                  TEXT PRIMARY KEY,
    execution_id        TEXT NOT NULL REFERENCES operation_executions(id) ON DELETE RESTRICT,
    time_category       TEXT NOT NULL
                        CHECK (time_category IN ('setup','run','waiting','downtime','rework')),
    duration_seconds    INTEGER NOT NULL CHECK (duration_seconds >= 0),
    started_at          TEXT,
    ended_at            TEXT,
    source_type         TEXT NOT NULL DEFAULT 'manual'
                        CHECK (source_type IN ('manual','import','calculated')),
    source_reference    TEXT,
    recorded_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE quantity_records (
    id                  TEXT PRIMARY KEY,
    execution_id        TEXT NOT NULL REFERENCES operation_executions(id) ON DELETE RESTRICT,
    quantity_type       TEXT NOT NULL
                        CHECK (quantity_type IN ('good','scrap','rework','pending')),
    quantity            REAL NOT NULL CHECK (quantity >= 0),
    unit_code           TEXT NOT NULL REFERENCES units(code) ON DELETE RESTRICT,
    recorded_at         TEXT NOT NULL,
    recorded_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    source_reference    TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE production_events (
    id                      TEXT PRIMARY KEY,
    planned_operation_id    TEXT NOT NULL REFERENCES planned_operations(id) ON DELETE RESTRICT,
    event_type              TEXT NOT NULL
                            CHECK (event_type IN ('stop','waiting','changeover','incident','rework','other')),
    started_at              TEXT NOT NULL,
    ended_at                TEXT,
    reason_code             TEXT,
    description             TEXT,
    impact_category         TEXT NOT NULL
                            CHECK (impact_category IN ('time','quality','capacity','other')),
    source_reference        TEXT,
    recorded_by             TEXT REFERENCES users(id) ON DELETE RESTRICT,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE deviation_records (
    id                  TEXT PRIMARY KEY,
    planned_operation_id TEXT NOT NULL REFERENCES planned_operations(id) ON DELETE RESTRICT,
    deviation_type      TEXT NOT NULL
                        CHECK (deviation_type IN ('time','schedule','quantity','quality','other')),
    detected_at         TEXT NOT NULL,
    reference_value     REAL NOT NULL,
    observed_value      REAL NOT NULL,
    deviation_value     REAL NOT NULL,
    unit_code           TEXT NOT NULL REFERENCES units(code) ON DELETE RESTRICT,
    severity            TEXT NOT NULL DEFAULT 'information'
                        CHECK (severity IN ('information','low','high','critical')),
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','qualified','treated','closed')),
    calculation_version TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (abs(deviation_value - (observed_value - reference_value)) < 0.000001)
);

-- ============================================================
-- 04. QUALITÉ / Q-TRACE
-- ============================================================

CREATE TABLE control_plans (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    product_version_id  TEXT REFERENCES product_versions(id) ON DELETE RESTRICT,
    route_operation_id  TEXT REFERENCES route_operations(id) ON DELETE RESTRICT,
    version_code        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','validated','retired')),
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    CHECK (product_version_id IS NOT NULL OR route_operation_id IS NOT NULL),
    UNIQUE (code, version_code)
);

CREATE TABLE control_points (
    id                  TEXT PRIMARY KEY,
    control_plan_id     TEXT NOT NULL REFERENCES control_plans(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    control_type        TEXT NOT NULL
                        CHECK (control_type IN ('visual','dimensional','documentary','other')),
    measurement_unit    TEXT REFERENCES units(code) ON DELETE RESTRICT,
    lower_limit         REAL,
    upper_limit         REAL,
    target_value        REAL,
    is_mandatory        INTEGER NOT NULL DEFAULT 1 CHECK (is_mandatory IN (0,1)),
    sequence_number     INTEGER NOT NULL CHECK (sequence_number > 0),
    CHECK (lower_limit IS NULL OR upper_limit IS NULL OR lower_limit <= upper_limit),
    UNIQUE (control_plan_id, code),
    UNIQUE (id, control_plan_id)
);

CREATE TABLE inspections (
    id                  TEXT PRIMARY KEY,
    control_plan_id     TEXT NOT NULL REFERENCES control_plans(id) ON DELETE RESTRICT,
    planned_operation_id TEXT REFERENCES planned_operations(id) ON DELETE RESTRICT,
    production_order_id TEXT REFERENCES production_orders(id) ON DELETE RESTRICT,
    inspector_id        TEXT REFERENCES users(id) ON DELETE RESTRICT,
    inspection_type     TEXT NOT NULL
                        CHECK (inspection_type IN ('incoming','in_process','final','other')),
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    status              TEXT NOT NULL DEFAULT 'planned'
                        CHECK (status IN ('planned','in_progress','completed','cancelled')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (completed_at IS NULL OR completed_at >= started_at),
    CHECK (planned_operation_id IS NOT NULL OR production_order_id IS NOT NULL)
);

CREATE TABLE inspection_results (
    id                  TEXT PRIMARY KEY,
    inspection_id       TEXT NOT NULL REFERENCES inspections(id) ON DELETE RESTRICT,
    control_point_id    TEXT NOT NULL REFERENCES control_points(id) ON DELETE RESTRICT,
    measured_value      REAL,
    text_value          TEXT,
    result_status       TEXT NOT NULL
                        CHECK (result_status IN ('conforming','nonconforming','indeterminate','not_applicable')),
    comment             TEXT,
    recorded_at         TEXT NOT NULL,
    recorded_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE (inspection_id, control_point_id),
    CHECK (measured_value IS NOT NULL OR text_value IS NOT NULL OR
           result_status IN ('indeterminate','not_applicable'))
);

CREATE TABLE nonconformities (
    id                  TEXT PRIMARY KEY,
    reference_code      TEXT NOT NULL UNIQUE,
    inspection_result_id TEXT REFERENCES inspection_results(id) ON DELETE RESTRICT,
    production_order_id TEXT REFERENCES production_orders(id) ON DELETE RESTRICT,
    planned_operation_id TEXT REFERENCES planned_operations(id) ON DELETE RESTRICT,
    description         TEXT NOT NULL,
    severity            TEXT NOT NULL
                        CHECK (severity IN ('minor','major','critical')),
    detected_at         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','analysis','treatment','closed')),
    origin_type         TEXT NOT NULL
                        CHECK (origin_type IN ('inspection','production','audit','other')),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (inspection_result_id IS NOT NULL OR production_order_id IS NOT NULL
           OR planned_operation_id IS NOT NULL)
);

CREATE TABLE dispositions (
    id                  TEXT PRIMARY KEY,
    nonconformity_id    TEXT NOT NULL REFERENCES nonconformities(id) ON DELETE RESTRICT,
    decision_type       TEXT NOT NULL
                        CHECK (decision_type IN ('rework','scrap','authorized_acceptance','hold','other')),
    decision_reason     TEXT NOT NULL,
    decided_by          TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    decided_at          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','approved','rejected','cancelled')),
    approved_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    approved_at         TEXT,
    CHECK ((status <> 'approved') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);

CREATE TABLE rework_records (
    id                  TEXT PRIMARY KEY,
    nonconformity_id    TEXT NOT NULL REFERENCES nonconformities(id) ON DELETE RESTRICT,
    production_order_id TEXT NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    planned_operation_id TEXT REFERENCES planned_operations(id) ON DELETE RESTRICT,
    duration_seconds    INTEGER NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
    quantity            REAL CHECK (quantity IS NULL OR quantity >= 0),
    cost_minor_units    INTEGER CHECK (cost_minor_units IS NULL OR cost_minor_units >= 0),
    currency_code       TEXT,
    status              TEXT NOT NULL DEFAULT 'planned'
                        CHECK (status IN ('planned','in_progress','completed','cancelled')),
    completed_at        TEXT,
    CHECK ((cost_minor_units IS NULL AND currency_code IS NULL) OR
           (cost_minor_units IS NOT NULL AND currency_code IS NOT NULL AND length(currency_code) = 3))
);

-- ============================================================
-- 05. CHANTIER 5S / STANDARDS / AUDITS
-- ============================================================

CREATE TABLE work_zones (
    id                  TEXT PRIMARY KEY,
    workstation_id      TEXT REFERENCES workstations(id) ON DELETE RESTRICT,
    island_id           TEXT REFERENCES production_islands(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT,
    owner_id            TEXT REFERENCES users(id) ON DELETE RESTRICT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    CHECK (workstation_id IS NOT NULL OR island_id IS NOT NULL)
);

CREATE TABLE standard_documents (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    zone_id             TEXT NOT NULL REFERENCES work_zones(id) ON DELETE RESTRICT,
    standard_type       TEXT NOT NULL
                        CHECK (standard_type IN ('equipment','access','platform','tooling','visual','other')),
    owner_id            TEXT REFERENCES users(id) ON DELETE RESTRICT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','active','retired')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE standard_versions (
    id                  TEXT PRIMARY KEY,
    standard_document_id TEXT NOT NULL REFERENCES standard_documents(id) ON DELETE RESTRICT,
    version_code        TEXT NOT NULL,
    content_reference   TEXT,
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','approved','superseded')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    approved_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    approved_at         TEXT,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    CHECK ((status <> 'approved') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
    UNIQUE (standard_document_id, version_code)
);

CREATE TABLE audit_templates (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    version_code        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','active','retired')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (code, version_code)
);

CREATE TABLE audit_criteria (
    id                  TEXT PRIMARY KEY,
    audit_template_id   TEXT NOT NULL REFERENCES audit_templates(id) ON DELETE RESTRICT,
    code                TEXT NOT NULL,
    label               TEXT NOT NULL,
    description         TEXT,
    weight              REAL NOT NULL DEFAULT 1 CHECK (weight >= 0),
    maximum_score       REAL NOT NULL CHECK (maximum_score > 0),
    is_mandatory        INTEGER NOT NULL DEFAULT 0 CHECK (is_mandatory IN (0,1)),
    is_critical         INTEGER NOT NULL DEFAULT 0 CHECK (is_critical IN (0,1)),
    sequence_number     INTEGER NOT NULL CHECK (sequence_number > 0),
    UNIQUE (audit_template_id, code),
    UNIQUE (audit_template_id, sequence_number)
);

CREATE TABLE audits (
    id                  TEXT PRIMARY KEY,
    audit_template_id   TEXT NOT NULL REFERENCES audit_templates(id) ON DELETE RESTRICT,
    zone_id             TEXT NOT NULL REFERENCES work_zones(id) ON DELETE RESTRICT,
    auditor_id          TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    planned_at          TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    status              TEXT NOT NULL DEFAULT 'planned'
                        CHECK (status IN ('planned','in_progress','completed','cancelled')),
    overall_score       REAL CHECK (overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)),
    comments            TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
);

CREATE TABLE audit_results (
    id                  TEXT PRIMARY KEY,
    audit_id            TEXT NOT NULL REFERENCES audits(id) ON DELETE RESTRICT,
    audit_criterion_id  TEXT NOT NULL REFERENCES audit_criteria(id) ON DELETE RESTRICT,
    score               REAL,
    applicability       TEXT NOT NULL DEFAULT 'applicable'
                        CHECK (applicability IN ('applicable','not_applicable')),
    comment             TEXT,
    evidence_document_id TEXT REFERENCES documents(id) ON DELETE RESTRICT,
    recorded_at         TEXT NOT NULL,
    recorded_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE (audit_id, audit_criterion_id),
    CHECK ((applicability = 'not_applicable' AND score IS NULL) OR
           (applicability = 'applicable' AND score IS NOT NULL AND score >= 0))
);

CREATE TABLE site_findings (
    id                  TEXT PRIMARY KEY,
    zone_id             TEXT NOT NULL REFERENCES work_zones(id) ON DELETE RESTRICT,
    audit_id            TEXT REFERENCES audits(id) ON DELETE RESTRICT,
    audit_result_id     TEXT REFERENCES audit_results(id) ON DELETE RESTRICT,
    description         TEXT NOT NULL,
    severity            TEXT NOT NULL
                        CHECK (severity IN ('low','medium','high','critical')),
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','qualified','treated','closed')),
    detected_at         TEXT NOT NULL,
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (audit_id IS NOT NULL OR audit_result_id IS NOT NULL)
);

-- ============================================================
-- 06. ORION — ANALYSES ET RECOMMANDATIONS
-- ============================================================

CREATE TABLE analysis_runs (
    id                      TEXT PRIMARY KEY,
    analysis_type           TEXT NOT NULL
                            CHECK (analysis_type IN ('descriptive','anomaly','comparison','capacity','effectiveness','other')),
    scope_type              TEXT NOT NULL
                            CHECK (scope_type IN ('site','workshop','island','workstation','order','operation','quality','five_s','improvement','custom')),
    scope_reference         TEXT,
    period_start            TEXT,
    period_end              TEXT,
    method_name             TEXT NOT NULL,
    method_version          TEXT NOT NULL,
    parameters_json         TEXT NOT NULL DEFAULT '{}'
                            CHECK (json_valid(parameters_json)),
    input_snapshot_reference TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued','running','completed','failed','cancelled')),
    started_at              TEXT NOT NULL,
    completed_at            TEXT,
    created_by              TEXT REFERENCES users(id) ON DELETE RESTRICT,
    error_summary           TEXT,
    CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start),
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);

CREATE TABLE analysis_metrics (
    id                  TEXT PRIMARY KEY,
    analysis_run_id     TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    metric_code         TEXT NOT NULL,
    metric_value        REAL,
    unit_code           TEXT REFERENCES units(code) ON DELETE RESTRICT,
    sample_size         INTEGER CHECK (sample_size IS NULL OR sample_size >= 0),
    definition_version  TEXT NOT NULL,
    quality_status      TEXT NOT NULL DEFAULT 'valid'
                        CHECK (quality_status IN ('valid','provisional','insufficient_data','invalid')),
    dimensions_json     TEXT NOT NULL DEFAULT '{}'
                        CHECK (json_valid(dimensions_json)),
    UNIQUE (analysis_run_id, metric_code, dimensions_json)
);

CREATE TABLE analysis_findings (
    id                  TEXT PRIMARY KEY,
    analysis_run_id     TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    finding_type        TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    evidence_reference  TEXT,
    severity            TEXT NOT NULL DEFAULT 'information'
                        CHECK (severity IN ('information','low','medium','high','critical')),
    confidence_level    TEXT NOT NULL DEFAULT 'not_assessed'
                        CHECK (confidence_level IN ('low','medium','high','not_assessed')),
    status              TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','reviewed','accepted','rejected')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE recommendations (
    id                  TEXT PRIMARY KEY,
    analysis_finding_id  TEXT NOT NULL REFERENCES analysis_findings(id) ON DELETE RESTRICT,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    rationale           TEXT NOT NULL,
    expected_benefit    TEXT,
    limitations         TEXT,
    status              TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','under_review','accepted_for_study','rejected','converted','withdrawn')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    reviewed_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_at         TEXT
);

-- ============================================================
-- 07. CAPAX — MODÈLES, SCÉNARIOS, EXÉCUTIONS
-- ============================================================

CREATE TABLE capacity_models (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    scope_type          TEXT NOT NULL
                        CHECK (scope_type IN ('site','workshop','island','workstation','route','custom')),
    site_id             TEXT REFERENCES sites(id) ON DELETE RESTRICT,
    workshop_id         TEXT REFERENCES workshops(id) ON DELETE RESTRICT,
    island_id           TEXT REFERENCES production_islands(id) ON DELETE RESTRICT,
    workstation_id      TEXT REFERENCES workstations(id) ON DELETE RESTRICT,
    route_id            TEXT REFERENCES routes(id) ON DELETE RESTRICT,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','validated','archived')),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (
        (scope_type = 'site' AND site_id IS NOT NULL AND workshop_id IS NULL AND island_id IS NULL AND workstation_id IS NULL AND route_id IS NULL) OR
        (scope_type = 'workshop' AND site_id IS NULL AND workshop_id IS NOT NULL AND island_id IS NULL AND workstation_id IS NULL AND route_id IS NULL) OR
        (scope_type = 'island' AND site_id IS NULL AND workshop_id IS NULL AND island_id IS NOT NULL AND workstation_id IS NULL AND route_id IS NULL) OR
        (scope_type = 'workstation' AND site_id IS NULL AND workshop_id IS NULL AND island_id IS NULL AND workstation_id IS NOT NULL AND route_id IS NULL) OR
        (scope_type = 'route' AND site_id IS NULL AND workshop_id IS NULL AND island_id IS NULL AND workstation_id IS NULL AND route_id IS NOT NULL) OR
        (scope_type = 'custom' AND site_id IS NULL AND workshop_id IS NULL AND island_id IS NULL AND workstation_id IS NULL AND route_id IS NULL)
    )
);

CREATE TABLE capacity_model_versions (
    id                  TEXT PRIMARY KEY,
    capacity_model_id   TEXT NOT NULL REFERENCES capacity_models(id) ON DELETE RESTRICT,
    version_number      INTEGER NOT NULL CHECK (version_number > 0),
    model_definition_json TEXT NOT NULL CHECK (json_valid(model_definition_json)),
    assumptions_json    TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(assumptions_json)),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (capacity_model_id, version_number),
    UNIQUE (id, capacity_model_id)
);

CREATE TABLE simulation_scenarios (
    id                      TEXT PRIMARY KEY,
    capacity_model_version_id TEXT NOT NULL REFERENCES capacity_model_versions(id) ON DELETE RESTRICT,
    name                    TEXT NOT NULL,
    scenario_type           TEXT NOT NULL
                            CHECK (scenario_type IN ('baseline','improvement','sensitivity')),
    parameters_json         TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(parameters_json)),
    created_by              TEXT REFERENCES users(id) ON DELETE RESTRICT,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (capacity_model_version_id, name),
    UNIQUE (id, capacity_model_version_id)
);

CREATE TABLE simulation_runs (
    id                      TEXT PRIMARY KEY,
    simulation_scenario_id  TEXT NOT NULL REFERENCES simulation_scenarios(id) ON DELETE RESTRICT,
    run_number              INTEGER NOT NULL CHECK (run_number > 0),
    algorithm_version       TEXT NOT NULL,
    input_snapshot_reference TEXT NOT NULL,
    started_at              TEXT NOT NULL,
    completed_at            TEXT,
    status                  TEXT NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued','running','completed','failed','cancelled')),
    error_summary           TEXT,
    created_by              TEXT REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (completed_at IS NULL OR completed_at >= started_at),
    UNIQUE (simulation_scenario_id, run_number)
);

CREATE TABLE simulation_results (
    id                  TEXT PRIMARY KEY,
    simulation_run_id   TEXT NOT NULL REFERENCES simulation_runs(id) ON DELETE RESTRICT,
    metric_code         TEXT NOT NULL,
    metric_value        REAL,
    unit_code           TEXT REFERENCES units(code) ON DELETE RESTRICT,
    reference_value     REAL,
    difference_value    REAL,
    result_status       TEXT NOT NULL DEFAULT 'valid'
                        CHECK (result_status IN ('valid','provisional','insufficient_data','invalid')),
    explanation         TEXT,
    dimensions_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(dimensions_json)),
    UNIQUE (simulation_run_id, metric_code, dimensions_json)
);

-- ============================================================
-- 08. DOSSIERS D'AMÉLIORATION, ACTIONS, PREUVES ET GAINS
-- ============================================================

CREATE TABLE improvement_cases (
    id                  TEXT PRIMARY KEY,
    case_number         TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    origin_type         TEXT NOT NULL
                        CHECK (origin_type IN ('production','quality','five_s','capacity','analysis','manual')),
    priority            TEXT NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('low','normal','high','urgent')),
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','qualified','analysis','actions','verification','closed','cancelled')),
    owner_id            TEXT REFERENCES users(id) ON DELETE RESTRICT,
    opened_at           TEXT NOT NULL,
    target_date         TEXT,
    closed_at           TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (target_date IS NULL OR target_date >= opened_at),
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE case_deviations (
    case_id             TEXT NOT NULL REFERENCES improvement_cases(id) ON DELETE RESTRICT,
    deviation_id        TEXT NOT NULL REFERENCES deviation_records(id) ON DELETE RESTRICT,
    PRIMARY KEY (case_id, deviation_id)
);

CREATE TABLE case_nonconformities (
    case_id             TEXT NOT NULL REFERENCES improvement_cases(id) ON DELETE RESTRICT,
    nonconformity_id    TEXT NOT NULL REFERENCES nonconformities(id) ON DELETE RESTRICT,
    PRIMARY KEY (case_id, nonconformity_id)
);

CREATE TABLE case_findings (
    case_id             TEXT NOT NULL REFERENCES improvement_cases(id) ON DELETE RESTRICT,
    finding_id          TEXT NOT NULL REFERENCES site_findings(id) ON DELETE RESTRICT,
    PRIMARY KEY (case_id, finding_id)
);

CREATE TABLE case_analysis_runs (
    case_id             TEXT NOT NULL REFERENCES improvement_cases(id) ON DELETE RESTRICT,
    analysis_run_id     TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    PRIMARY KEY (case_id, analysis_run_id)
);

CREATE TABLE action_items (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL REFERENCES improvement_cases(id) ON DELETE RESTRICT,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    action_type         TEXT NOT NULL
                        CHECK (action_type IN ('corrective','preventive','improvement','investigation')),
    owner_id            TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    priority            TEXT NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('low','normal','high','urgent')),
    status              TEXT NOT NULL DEFAULT 'to_do'
                        CHECK (status IN ('to_do','in_progress','blocked','to_verify','completed','cancelled')),
    start_date          TEXT,
    due_date            TEXT,
    completed_at        TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (due_date IS NULL OR start_date IS NULL OR due_date >= start_date),
    CHECK (completed_at IS NULL OR completed_at >= created_at)
);

CREATE TABLE action_evidence (
    id                  TEXT PRIMARY KEY,
    action_item_id      TEXT NOT NULL REFERENCES action_items(id) ON DELETE RESTRICT,
    document_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    evidence_type       TEXT NOT NULL
                        CHECK (evidence_type IN ('document','photo','measurement','approval','other')),
    description         TEXT,
    recorded_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    recorded_at         TEXT NOT NULL
);

CREATE TABLE effectiveness_reviews (
    id                      TEXT PRIMARY KEY,
    action_item_id          TEXT NOT NULL REFERENCES action_items(id) ON DELETE RESTRICT,
    reviewed_by             TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    reference_period_start  TEXT NOT NULL,
    reference_period_end    TEXT NOT NULL,
    evaluation_period_start TEXT NOT NULL,
    evaluation_period_end   TEXT NOT NULL,
    result                  TEXT NOT NULL
                            CHECK (result IN ('effective','partially_effective','ineffective','insufficient_data')),
    methodology             TEXT NOT NULL,
    conclusion              TEXT NOT NULL,
    reviewed_at             TEXT NOT NULL,
    CHECK (reference_period_end >= reference_period_start),
    CHECK (evaluation_period_end >= evaluation_period_start),
    CHECK (evaluation_period_start > reference_period_end)
);

CREATE TABLE benefit_estimates (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL REFERENCES improvement_cases(id) ON DELETE RESTRICT,
    action_item_id      TEXT REFERENCES action_items(id) ON DELETE RESTRICT,
    benefit_type        TEXT NOT NULL
                        CHECK (benefit_type IN ('time','capacity','cost','quality','lead_time','other')),
    baseline_value      REAL,
    target_value        REAL,
    unit_code           TEXT REFERENCES units(code) ON DELETE RESTRICT,
    currency_code       TEXT,
    assumptions         TEXT NOT NULL,
    estimated_at        TEXT NOT NULL,
    estimated_by        TEXT REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (currency_code IS NULL OR length(currency_code) = 3)
);

CREATE TABLE benefit_measurements (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL REFERENCES improvement_cases(id) ON DELETE RESTRICT,
    action_item_id      TEXT REFERENCES action_items(id) ON DELETE RESTRICT,
    reference_start     TEXT NOT NULL,
    reference_end       TEXT NOT NULL,
    evaluation_start    TEXT NOT NULL,
    evaluation_end      TEXT NOT NULL,
    baseline_value      REAL NOT NULL,
    observed_value      REAL NOT NULL,
    difference_value    REAL NOT NULL,
    unit_code           TEXT NOT NULL REFERENCES units(code) ON DELETE RESTRICT,
    measurement_method  TEXT NOT NULL,
    data_source_reference TEXT,
    measured_at         TEXT NOT NULL,
    validated_by        TEXT REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (reference_end >= reference_start),
    CHECK (evaluation_end >= evaluation_start),
    CHECK (evaluation_start > reference_end),
    CHECK (abs(difference_value - (observed_value - baseline_value)) < 0.000001)
);

-- ============================================================
-- 09. SOURCES, IMPORTS, DOCUMENTS, NOTIFICATIONS ET RAPPORTS
-- ============================================================

CREATE TABLE data_sources (
    id                  TEXT PRIMARY KEY,
    source_type         TEXT NOT NULL
                        CHECK (source_type IN ('manual','file_import','synthetic','connector')),
    name                TEXT NOT NULL,
    description         TEXT,
    origin_reference    TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE import_jobs (
    id                  TEXT PRIMARY KEY,
    source_id           TEXT NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
    filename            TEXT NOT NULL,
    file_hash           TEXT,
    status              TEXT NOT NULL DEFAULT 'received'
                        CHECK (status IN ('received','analyzed','awaiting_confirmation','processing','completed','completed_with_rejections','failed')),
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    rows_total          INTEGER NOT NULL DEFAULT 0 CHECK (rows_total >= 0),
    rows_valid          INTEGER NOT NULL DEFAULT 0 CHECK (rows_valid >= 0),
    rows_rejected       INTEGER NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (rows_valid + rows_rejected <= rows_total),
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);

CREATE TABLE import_mappings (
    id                  TEXT PRIMARY KEY,
    import_job_id       TEXT NOT NULL REFERENCES import_jobs(id) ON DELETE RESTRICT,
    source_column       TEXT NOT NULL,
    target_field        TEXT NOT NULL,
    conversion_rule     TEXT,
    validation_rule     TEXT,
    UNIQUE (import_job_id, source_column)
);

CREATE TABLE import_errors (
    id                  TEXT PRIMARY KEY,
    import_job_id       TEXT NOT NULL REFERENCES import_jobs(id) ON DELETE RESTRICT,
    row_number          INTEGER NOT NULL CHECK (row_number > 0),
    field_name          TEXT,
    error_code          TEXT NOT NULL,
    error_message       TEXT NOT NULL,
    raw_value           TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE documents (
    id                  TEXT PRIMARY KEY,
    document_type       TEXT NOT NULL,
    title               TEXT NOT NULL,
    storage_reference   TEXT NOT NULL,
    mime_type           TEXT,
    checksum            TEXT,
    version_code        TEXT,
    uploaded_by         TEXT REFERENCES users(id) ON DELETE RESTRICT,
    uploaded_at         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','archived','quarantined')),
    UNIQUE (storage_reference)
);

CREATE TABLE notification_events (
    id                  TEXT PRIMARY KEY,
    recipient_user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    notification_type   TEXT NOT NULL,
    entity_type         TEXT NOT NULL,
    entity_id           TEXT NOT NULL,
    message             TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    read_at             TEXT,
    delivery_status     TEXT NOT NULL DEFAULT 'pending'
                        CHECK (delivery_status IN ('pending','delivered','failed','not_applicable'))
);

CREATE TABLE report_definitions (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT,
    report_type         TEXT NOT NULL,
    definition_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(definition_json)),
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE report_runs (
    id                  TEXT PRIMARY KEY,
    report_definition_id TEXT NOT NULL REFERENCES report_definitions(id) ON DELETE RESTRICT,
    parameters_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(parameters_json)),
    scope_description   TEXT,
    data_snapshot_reference TEXT,
    output_document_id  TEXT REFERENCES documents(id) ON DELETE RESTRICT,
    status              TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','running','completed','failed','cancelled')),
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    created_by          TEXT REFERENCES users(id) ON DELETE RESTRICT,
    error_summary       TEXT,
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);

-- ============================================================
-- 10. ASSOCIATIONS DOCUMENTAIRES GÉNÉRIQUES
-- ============================================================

-- Table d'association polymorphe contrôlée par l'application.
-- Les FK vers l'objet métier ne peuvent pas être génériques en SQL.
-- À réserver aux pièces jointes transversales ; les preuves d'action
-- disposent aussi de leur relation dédiée.
CREATE TABLE entity_documents (
    id                  TEXT PRIMARY KEY,
    entity_type         TEXT NOT NULL
                        CHECK (entity_type IN ('production_order','planned_operation','inspection','nonconformity','audit','improvement_case','action_item','analysis_run','simulation_run')),
    entity_id           TEXT NOT NULL,
    document_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    relationship_type   TEXT NOT NULL DEFAULT 'attachment'
                        CHECK (relationship_type IN ('attachment','evidence','reference','report')),
    added_by            TEXT REFERENCES users(id) ON DELETE RESTRICT,
    added_at            TEXT NOT NULL,
    UNIQUE (entity_type, entity_id, document_id, relationship_type)
);

-- ============================================================
-- 11. AUDIT LOG ET MÉTADONNÉES DE SCHÉMA
-- ============================================================

CREATE TABLE audit_logs (
    id                  TEXT PRIMARY KEY,
    actor_user_id       TEXT REFERENCES users(id) ON DELETE RESTRICT,
    event_type          TEXT NOT NULL,
    entity_type         TEXT NOT NULL,
    entity_id           TEXT,
    occurred_at         TEXT NOT NULL,
    before_snapshot     TEXT CHECK (before_snapshot IS NULL OR json_valid(before_snapshot)),
    after_snapshot      TEXT CHECK (after_snapshot IS NULL OR json_valid(after_snapshot)),
    reason              TEXT,
    correlation_id      TEXT
);

CREATE TABLE schema_migrations (
    version             INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    applied_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    checksum            TEXT
);

-- ============================================================
-- 12. INDEX DE PERFORMANCE
-- ============================================================

CREATE INDEX idx_workshops_site ON workshops(site_id);
CREATE INDEX idx_islands_workshop ON production_islands(workshop_id);
CREATE INDEX idx_workstations_island ON workstations(island_id);
CREATE INDEX idx_resources_workstation ON resources(workstation_id);
CREATE INDEX idx_resources_calendar ON resources(calendar_id);

CREATE INDEX idx_product_versions_product ON product_versions(product_id, status);
CREATE INDEX idx_routes_product_version ON routes(product_version_id, status);
CREATE INDEX idx_route_operations_route_seq ON route_operations(route_id, sequence_number);
CREATE INDEX idx_operation_resources_resource ON operation_resources(resource_id);

CREATE INDEX idx_orders_status_plan_start ON production_orders(status, planned_start_at);
CREATE INDEX idx_orders_product_version ON production_orders(product_version_id);
CREATE INDEX idx_orders_route ON production_orders(route_id);
CREATE INDEX idx_planned_ops_order_seq ON planned_operations(production_order_id, sequence_number);
CREATE INDEX idx_planned_ops_workstation_status ON planned_operations(workstation_id, status);
CREATE INDEX idx_planned_ops_dates ON planned_operations(planned_start_at, planned_end_at);
CREATE INDEX idx_executions_operation ON operation_executions(planned_operation_id, execution_number);
CREATE INDEX idx_executions_resource_dates ON operation_executions(resource_id, started_at, ended_at);
CREATE INDEX idx_time_records_execution_category ON time_records(execution_id, time_category);
CREATE INDEX idx_quantity_records_execution_type ON quantity_records(execution_id, quantity_type);
CREATE INDEX idx_production_events_operation_start ON production_events(planned_operation_id, started_at);
CREATE INDEX idx_deviations_status_detected ON deviation_records(status, detected_at);
CREATE INDEX idx_deviations_operation ON deviation_records(planned_operation_id);

CREATE INDEX idx_control_points_plan_seq ON control_points(control_plan_id, sequence_number);
CREATE INDEX idx_inspections_status_started ON inspections(status, started_at);
CREATE INDEX idx_inspections_order ON inspections(production_order_id);
CREATE INDEX idx_inspections_operation ON inspections(planned_operation_id);
CREATE INDEX idx_inspection_results_status ON inspection_results(result_status);
CREATE INDEX idx_nonconformities_status_severity ON nonconformities(status, severity, detected_at);
CREATE INDEX idx_nonconformities_order ON nonconformities(production_order_id);
CREATE INDEX idx_dispositions_nc ON dispositions(nonconformity_id, decided_at);
CREATE INDEX idx_rework_nc ON rework_records(nonconformity_id);

CREATE INDEX idx_work_zones_island ON work_zones(island_id);
CREATE INDEX idx_work_zones_workstation ON work_zones(workstation_id);
CREATE INDEX idx_standards_zone_status ON standard_documents(zone_id, status);
CREATE INDEX idx_standard_versions_document ON standard_versions(standard_document_id, valid_from);
CREATE INDEX idx_audits_zone_date ON audits(zone_id, started_at);
CREATE INDEX idx_audits_status_date ON audits(status, planned_at);
CREATE INDEX idx_audit_results_audit ON audit_results(audit_id);
CREATE INDEX idx_findings_zone_status ON site_findings(zone_id, status, detected_at);

CREATE INDEX idx_analysis_scope_period ON analysis_runs(scope_type, scope_reference, period_start, period_end);
CREATE INDEX idx_analysis_status_started ON analysis_runs(status, started_at);
CREATE INDEX idx_analysis_metrics_code ON analysis_metrics(metric_code);
CREATE INDEX idx_analysis_findings_run_severity ON analysis_findings(analysis_run_id, severity);
CREATE INDEX idx_recommendations_status ON recommendations(status);

CREATE INDEX idx_capacity_models_status ON capacity_models(status);
CREATE INDEX idx_capacity_versions_model ON capacity_model_versions(capacity_model_id, version_number);
CREATE INDEX idx_scenarios_version ON simulation_scenarios(capacity_model_version_id);
CREATE INDEX idx_simulation_runs_scenario_status ON simulation_runs(simulation_scenario_id, status);
CREATE INDEX idx_simulation_results_metric ON simulation_results(metric_code);

CREATE INDEX idx_cases_status_priority ON improvement_cases(status, priority, opened_at);
CREATE INDEX idx_actions_owner_status_due ON action_items(owner_id, status, due_date);
CREATE INDEX idx_actions_case_status ON action_items(case_id, status);
CREATE INDEX idx_effectiveness_action_reviewed ON effectiveness_reviews(action_item_id, reviewed_at);
CREATE INDEX idx_benefit_estimates_case ON benefit_estimates(case_id);
CREATE INDEX idx_benefit_measurements_case ON benefit_measurements(case_id, measured_at);

CREATE INDEX idx_import_jobs_status ON import_jobs(status, started_at);
CREATE INDEX idx_import_errors_job_row ON import_errors(import_job_id, row_number);
CREATE INDEX idx_documents_checksum ON documents(checksum);
CREATE INDEX idx_notifications_user_unread ON notification_events(recipient_user_id, read_at, created_at);
CREATE INDEX idx_report_runs_definition_date ON report_runs(report_definition_id, started_at);
CREATE INDEX idx_entity_documents_entity ON entity_documents(entity_type, entity_id);
CREATE INDEX idx_audit_logs_entity_time ON audit_logs(entity_type, entity_id, occurred_at);
CREATE INDEX idx_audit_logs_actor_time ON audit_logs(actor_user_id, occurred_at);

-- ============================================================
-- 13. TRIGGERS DE COHÉRENCE INTER-TABLES
-- ============================================================

-- Un ordre doit utiliser une gamme rattachée à la version de produit choisie.
CREATE TRIGGER trg_order_route_product_consistency
BEFORE INSERT ON production_orders
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM routes r
        WHERE r.id = NEW.route_id
          AND r.product_version_id = NEW.product_version_id
    )
    THEN RAISE(ABORT, 'route does not belong to production order product version')
    END;
END;

CREATE TRIGGER trg_order_route_product_consistency_update
BEFORE UPDATE OF route_id, product_version_id ON production_orders
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM routes r
        WHERE r.id = NEW.route_id
          AND r.product_version_id = NEW.product_version_id
    )
    THEN RAISE(ABORT, 'route does not belong to production order product version')
    END;
END;

-- Une opération planifiée doit utiliser une opération standard appartenant
-- à la gamme du produit/version de l'ordre.
CREATE TRIGGER trg_planned_operation_route_consistency
BEFORE INSERT ON planned_operations
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM production_orders po
        JOIN route_operations ro ON ro.id = NEW.route_operation_id
        WHERE po.id = NEW.production_order_id
          AND po.route_id = ro.route_id
    )
    THEN RAISE(ABORT, 'planned operation route does not match production order route')
    END;
END;

CREATE TRIGGER trg_planned_operation_route_consistency_update
BEFORE UPDATE OF production_order_id, route_operation_id ON planned_operations
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM production_orders po
        JOIN route_operations ro ON ro.id = NEW.route_operation_id
        WHERE po.id = NEW.production_order_id
          AND po.route_id = ro.route_id
    )
    THEN RAISE(ABORT, 'planned operation route does not match production order route')
    END;
END;

-- Un résultat de contrôle doit pointer vers un point du même plan
-- que l'inspection.
CREATE TRIGGER trg_inspection_result_plan_consistency
BEFORE INSERT ON inspection_results
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM inspections i
        JOIN control_points cp ON cp.id = NEW.control_point_id
        WHERE i.id = NEW.inspection_id
          AND i.control_plan_id = cp.control_plan_id
    )
    THEN RAISE(ABORT, 'control point does not belong to inspection control plan')
    END;
END;

CREATE TRIGGER trg_inspection_result_plan_consistency_update
BEFORE UPDATE OF inspection_id, control_point_id ON inspection_results
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM inspections i
        JOIN control_points cp ON cp.id = NEW.control_point_id
        WHERE i.id = NEW.inspection_id
          AND i.control_plan_id = cp.control_plan_id
    )
    THEN RAISE(ABORT, 'control point does not belong to inspection control plan')
    END;
END;

-- Un résultat d'audit doit pointer vers un critère du modèle utilisé.
CREATE TRIGGER trg_audit_result_template_consistency
BEFORE INSERT ON audit_results
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM audits a
        JOIN audit_criteria ac ON ac.id = NEW.audit_criterion_id
        WHERE a.id = NEW.audit_id
          AND a.audit_template_id = ac.audit_template_id
          AND (NEW.score IS NULL OR NEW.score <= ac.maximum_score)
    )
    THEN RAISE(ABORT, 'audit criterion/template mismatch or score exceeds maximum')
    END;
END;

CREATE TRIGGER trg_audit_result_template_consistency_update
BEFORE UPDATE OF audit_id, audit_criterion_id, score ON audit_results
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM audits a
        JOIN audit_criteria ac ON ac.id = NEW.audit_criterion_id
        WHERE a.id = NEW.audit_id
          AND a.audit_template_id = ac.audit_template_id
          AND (NEW.score IS NULL OR NEW.score <= ac.maximum_score)
    )
    THEN RAISE(ABORT, 'audit criterion/template mismatch or score exceeds maximum')
    END;
END;

-- Une ressource affectée à une opération doit être située dans le même
-- îlot que le poste par défaut de l'opération lorsque celui-ci est défini.
CREATE TRIGGER trg_operation_resource_location_consistency
BEFORE INSERT ON operation_resources
FOR EACH ROW
WHEN (SELECT default_workstation_id FROM route_operations WHERE id = NEW.route_operation_id) IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM route_operations ro
        JOIN resources r ON r.id = NEW.resource_id
        JOIN workstations rw ON rw.id = r.workstation_id
        JOIN workstations dw ON dw.id = ro.default_workstation_id
        WHERE ro.id = NEW.route_operation_id
          AND rw.island_id = dw.island_id
    )
    THEN RAISE(ABORT, 'resource is outside default operation island')
    END;
END;

-- ============================================================
-- 14. VUES DE LECTURE
-- ============================================================

CREATE VIEW v_production_order_progress AS
SELECT
    po.id AS production_order_id,
    po.order_number,
    po.status AS order_status,
    po.planned_quantity,
    po.unit_code,
    COUNT(DISTINCT p.id) AS operation_count,
    SUM(CASE WHEN p.status = 'completed' THEN 1 ELSE 0 END) AS completed_operation_count,
    SUM(p.planned_setup_seconds + p.planned_run_seconds) AS total_planned_seconds
FROM production_orders po
LEFT JOIN planned_operations p ON p.production_order_id = po.id
GROUP BY po.id, po.order_number, po.status, po.planned_quantity, po.unit_code;

CREATE VIEW v_action_overdue AS
SELECT
    a.id AS action_item_id,
    a.case_id,
    a.title,
    a.owner_id,
    a.status,
    a.due_date
FROM action_items a
WHERE a.due_date IS NOT NULL
  AND a.due_date < strftime('%Y-%m-%dT%H:%M:%fZ','now')
  AND a.status NOT IN ('completed','cancelled');

-- ============================================================
-- 15. MIGRATION INITIALE
-- ============================================================

INSERT INTO schema_migrations(version, name, checksum)
VALUES (1, 'initial_physical_schema', 'nexus-srp-v1-initial');

COMMIT;

-- ============================================================
-- FIN DU SCHÉMA
-- ============================================================


-- NEXUS Industrial V1.1 hardening patch (SQLite)
-- Global role assignments: prevent duplicate global grants where scope_id is NULL.
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_roles_global
ON user_roles(user_id, role_id) WHERE scope_type='global' AND scope_id IS NULL;
CREATE INDEX IF NOT EXISTS ix_orders_start_status ON production_orders(planned_start_at,status);
CREATE INDEX IF NOT EXISTS ix_planned_ops_order_status ON planned_operations(production_order_id,status,sequence_number);
CREATE INDEX IF NOT EXISTS ix_exec_started ON operation_executions(started_at,resource_id);
CREATE INDEX IF NOT EXISTS ix_time_records_category ON time_records(execution_id,time_category);
CREATE INDEX IF NOT EXISTS ix_events_started_type ON production_events(started_at,event_type,impact_category);
CREATE INDEX IF NOT EXISTS ix_deviations_status_severity ON deviation_records(status,severity,detected_at);
CREATE INDEX IF NOT EXISTS ix_inspections_order_status ON inspections(production_order_id,status,started_at);
CREATE INDEX IF NOT EXISTS ix_ncs_status_severity ON nonconformities(status,severity,detected_at);
CREATE INDEX IF NOT EXISTS ix_benefit_measurements_period ON benefit_measurements(evaluation_start,evaluation_end,case_id);

-- An inspection's plan, operation and order must refer to the same product version.
CREATE TRIGGER IF NOT EXISTS trg_inspection_product_version_insert
BEFORE INSERT ON inspections
WHEN NEW.production_order_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM production_orders po JOIN control_plans cp ON cp.id=NEW.control_plan_id
 WHERE po.id=NEW.production_order_id AND po.product_version_id<>cp.product_version_id
)
BEGIN SELECT RAISE(ABORT,'inspection control plan product version does not match production order'); END;
CREATE TRIGGER IF NOT EXISTS trg_inspection_product_version_update
BEFORE UPDATE OF control_plan_id,production_order_id ON inspections
WHEN NEW.production_order_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM production_orders po JOIN control_plans cp ON cp.id=NEW.control_plan_id
 WHERE po.id=NEW.production_order_id AND po.product_version_id<>cp.product_version_id
)
BEGIN SELECT RAISE(ABORT,'inspection control plan product version does not match production order'); END;

-- When both are provided, an inspection's operation must belong to the selected order.
CREATE TRIGGER IF NOT EXISTS trg_inspection_operation_order_insert
BEFORE INSERT ON inspections
WHEN NEW.planned_operation_id IS NOT NULL AND NEW.production_order_id IS NOT NULL
 AND NOT EXISTS (SELECT 1 FROM planned_operations p WHERE p.id=NEW.planned_operation_id AND p.production_order_id=NEW.production_order_id)
BEGIN SELECT RAISE(ABORT,'inspection operation does not belong to production order'); END;
CREATE TRIGGER IF NOT EXISTS trg_inspection_operation_order_update
BEFORE UPDATE OF planned_operation_id,production_order_id ON inspections
WHEN NEW.planned_operation_id IS NOT NULL AND NEW.production_order_id IS NOT NULL
 AND NOT EXISTS (SELECT 1 FROM planned_operations p WHERE p.id=NEW.planned_operation_id AND p.production_order_id=NEW.production_order_id)
BEGIN SELECT RAISE(ABORT,'inspection operation does not belong to production order'); END;

-- A nonconformity linked to an inspection result may not point to another order/operation.
CREATE TRIGGER IF NOT EXISTS trg_nc_inspection_link_insert
BEFORE INSERT ON nonconformities
WHEN NEW.inspection_result_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM inspection_results ir JOIN inspections i ON i.id=ir.inspection_id
 WHERE ir.id=NEW.inspection_result_id AND (
  (NEW.production_order_id IS NOT NULL AND i.production_order_id IS NOT NULL AND NEW.production_order_id<>i.production_order_id)
  OR (NEW.planned_operation_id IS NOT NULL AND i.planned_operation_id IS NOT NULL AND NEW.planned_operation_id<>i.planned_operation_id)
 )
)
BEGIN SELECT RAISE(ABORT,'nonconformity order/operation does not match inspection'); END;
CREATE TRIGGER IF NOT EXISTS trg_nc_inspection_link_update
BEFORE UPDATE OF inspection_result_id,production_order_id,planned_operation_id ON nonconformities
WHEN NEW.inspection_result_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM inspection_results ir JOIN inspections i ON i.id=ir.inspection_id
 WHERE ir.id=NEW.inspection_result_id AND (
  (NEW.production_order_id IS NOT NULL AND i.production_order_id IS NOT NULL AND NEW.production_order_id<>i.production_order_id)
  OR (NEW.planned_operation_id IS NOT NULL AND i.planned_operation_id IS NOT NULL AND NEW.planned_operation_id<>i.planned_operation_id)
 )
)
BEGIN SELECT RAISE(ABORT,'nonconformity order/operation does not match inspection'); END;

INSERT INTO schema_migrations(version,name,checksum)
SELECT 2,'schema_v1_1_integrity_hardening','nexus-srp-v1.1-2026-10-11'
WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version=2);
