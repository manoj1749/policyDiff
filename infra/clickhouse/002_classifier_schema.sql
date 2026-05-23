-- ============================================================
-- PolicyDiff — Schema 002: Classifier Service Tables
-- Owner: Engineer B
-- ============================================================

-- Reference claims data used for revenue-at-risk calculation.
CREATE TABLE IF NOT EXISTS policydiff.claims_ref
(
    cpt                     String,
    service_line            String,
    avg_reimbursement_usd   Float64,
    claim_count_90d         UInt32,
    payer                   String DEFAULT ''
)
ENGINE = MergeTree()
ORDER BY (cpt, payer);

-- Final classified change events consumed by Engineer C's dashboard.
CREATE TABLE IF NOT EXISTS policydiff.change_events
(
    event_id            UUID     DEFAULT generateUUIDv4(),
    created_at          DateTime DEFAULT now(),
    diff_id             UUID,
    payer               String,
    policy_id           String,
    policy_title        String,
    url                 String,
    service_line        String,
    change_type         String,
    confidence          Float32,
    changed_clause      String,
    change_summary      String,
    clinical_impact     String,
    cpt_codes_affected  Array(String),
    revenue_at_risk_usd Float64,
    cited_md_url        String,
    cited_markdown      String,
    recommended_action  String DEFAULT '',
    datadog_trace_id    String DEFAULT '',
    status              String DEFAULT 'PUBLISHED'
)
ENGINE = MergeTree()
ORDER BY (created_at, payer, policy_id, change_type);

-- Error log for classification failures.
CREATE TABLE IF NOT EXISTS policydiff.classification_errors
(
    error_id      UUID     DEFAULT generateUUIDv4(),
    created_at    DateTime DEFAULT now(),
    diff_id       UUID,
    payer         String,
    policy_id     String,
    error_stage   String,
    error_message String
)
ENGINE = MergeTree()
ORDER BY (created_at, error_stage);
