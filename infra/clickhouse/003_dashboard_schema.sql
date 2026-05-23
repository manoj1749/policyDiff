-- ============================================================
-- 003_dashboard_schema.sql
-- api-dashboard-service read schema
--
-- This service is read-only from change_events.
-- workflow_alerts is only written if Luminai routing is enabled.
-- ============================================================

CREATE DATABASE IF NOT EXISTS policydiff;

-- Optional: workflow alerts written by Luminai routing
CREATE TABLE IF NOT EXISTS policydiff.workflow_alerts (
    alert_id UUID DEFAULT generateUUIDv4(),
    created_at DateTime DEFAULT now(),
    event_id UUID,
    payer String,
    policy_id String,
    route_to String,
    webhook_url String,
    status String,
    response_body String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (created_at, payer, policy_id);
