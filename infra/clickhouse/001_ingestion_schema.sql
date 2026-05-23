-- ============================================================
-- PolicyDiff - Schema 001: Ingestion Service Tables
-- Owner: Engineer A
-- ============================================================

CREATE DATABASE IF NOT EXISTS policydiff;

CREATE TABLE IF NOT EXISTS policydiff.policy_sources
(
    payer              String,
    policy_id          String,
    policy_title       String,
    url                String,
    source_type        String,
    service_line       String,
    default_cpt_codes  Array(String),
    active             UInt8 DEFAULT 1,
    created_at         DateTime DEFAULT now(),
    updated_at         DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (payer, policy_id);

CREATE TABLE IF NOT EXISTS policydiff.policy_versions
(
    payer              String,
    policy_id          String,
    policy_title       String,
    url                String,
    source_type        String,
    version_hash       UInt64,
    normalized_text    String,
    raw_extract        String,
    fetched_at         DateTime DEFAULT now(),
    extraction_status  String,
    extraction_error   String DEFAULT ''
)
ENGINE = ReplacingMergeTree(fetched_at)
ORDER BY (payer, policy_id, version_hash);

CREATE TABLE IF NOT EXISTS policydiff.diff_candidates
(
    diff_id           UUID DEFAULT generateUUIDv4(),
    created_at        DateTime DEFAULT now(),
    payer             String,
    policy_id         String,
    policy_title      String,
    url               String,
    source_type       String,
    service_line      String,
    old_hash          UInt64,
    new_hash          UInt64,
    old_text          String,
    new_text          String,
    default_cpt_codes Array(String),
    status            String DEFAULT 'PENDING',
    processed_at      Nullable(DateTime),
    error_message     String DEFAULT ''
)
ENGINE = MergeTree()
ORDER BY (status, created_at, payer, policy_id);

CREATE TABLE IF NOT EXISTS policydiff.ingestion_runs
(
    run_id              UUID DEFAULT generateUUIDv4(),
    started_at          DateTime DEFAULT now(),
    finished_at         Nullable(DateTime),
    policies_attempted  UInt32,
    policies_succeeded  UInt32,
    policies_failed     UInt32,
    diffs_created       UInt32,
    status              String,
    error_message       String DEFAULT ''
)
ENGINE = MergeTree()
ORDER BY (started_at, status);
