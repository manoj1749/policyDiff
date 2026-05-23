# PolicyDiff — Engineer B README
## AI Classification + Revenue Impact + Senso Publishing + Datadog Service

**Owner:** Engineer B  
**Microservice name:** `classifier-service`  
**Primary responsibility:** Read pending policy diffs from ClickHouse, classify them using Gemini, compute revenue impact using CPT mappings and claims data, publish citeable markdown to Senso/cited.md, trace LLM calls in Datadog, and mark each diff candidate as processed.

---

## 1. Overall project context

PolicyDiff prevents healthcare denials by detecting payer policy changes before billing and prior authorization teams feel the impact.

The full system flow is:

```text
Engineer A: Nimble policy scrape + normalization + diff_candidates
        ↓
Engineer B: Gemini classification + revenue impact + Senso cited.md publishing + Datadog tracing
        ↓
Engineer C: API + dashboard + optional x402 export + optional Luminai routing
```

Your service turns raw diffs into **business-ready intelligence**.

Engineer A gives you this:

```text
“This payer policy changed.”
```

You produce this:

```text
“UnitedHealthcare tightened Cardiac MRI criteria, likely affecting CPT 75561 and creating $261K annualized revenue risk. Here is a cited.md markdown brief with source-grounded evidence.”
```

---

## 2. What you are building

You are building the classifier microservice that:

1. Polls ClickHouse for `diff_candidates.status = 'PENDING'`.
2. Sends the old and new policy text to Gemini.
3. Classifies the change as:
   - `TIGHTENING`
   - `LOOSENING`
   - `SCOPE_CHANGE`
   - `STYLISTIC`
4. Extracts the changed clause, clinical impact, and CPT codes.
5. Computes annualized revenue at risk.
6. Publishes a citeable markdown brief to Senso/cited.md.
7. Writes the final result to `change_events`.
8. Updates the source `diff_candidates` row to `PROCESSED`.
9. Sends all Gemini calls through Datadog LLM Observability.

Senso and Datadog are not optional for your service. They are part of the judged tool-use story.

---

## 3. Service boundary

### You own

```text
services/classifier-service/
├── app/
│   ├── main.py
│   ├── classifier.py
│   ├── gemini_client.py
│   ├── revenue_impact.py
│   ├── senso_publisher.py
│   ├── datadog_setup.py
│   ├── clickhouse_repo.py
│   └── config_loader.py
├── config/
│   └── policy_cpt_map.yaml
├── prompts/
│   └── classification_prompt.md
├── tests/
│   ├── test_classifier_schema.py
│   ├── test_revenue_impact.py
│   └── test_senso_payload.py
├── Dockerfile
├── requirements.txt
└── README.md
```

### You read from

- `diff_candidates`
- `claims_ref`
- `policy_cpt_map.yaml`

### You write to

- `change_events`
- update `diff_candidates.status`
- optionally `classification_errors`

### You do not own

- Nimble scraping
- text normalization
- frontend dashboard
- x402
- Luminai webhook

---

## 4. Required config file

Create:

```text
services/classifier-service/config/policy_cpt_map.yaml
```

Starter content:

```yaml
policies:
  UHC:cardiac-mri:
    service_line: Cardiology
    cpt_codes: [75557, 75559, 75561]
    keywords: [cardiac MRI, myocarditis, cardiomyopathy, echocardiogram, stress test]

  UHC:vagus-nerve-stim:
    service_line: Neurology
    cpt_codes: [64568, 64569, 64570]
    keywords: [vagus nerve stimulation, epilepsy, seizure]

  Aetna:cpb-0761:
    service_line: Radiology
    cpt_codes: [73221, 73721]
    keywords: [MRI extremity, joint, knee, shoulder]

  Aetna:cpb-0352:
    service_line: Radiology
    cpt_codes: [71046, 71250]
    keywords: [diagnostic imaging, chest x-ray, CT thorax]

  Cigna:cardiac-imaging:
    service_line: Cardiology
    cpt_codes: [93306, 93454, 75561]
    keywords: [cardiac imaging, echocardiography, catheterization, cardiac MRI]

  Humana:mri-spine:
    service_line: Orthopedics
    cpt_codes: [72141, 72148, 72156, 72158]
    keywords: [MRI spine, lumbar, cervical, radiculopathy, conservative therapy]
```

This is used as a fallback if Gemini misses CPT codes.

---

## 5. ClickHouse schema you need

Place this in:

```text
infra/clickhouse/002_classifier_schema.sql
```

```sql
CREATE TABLE IF NOT EXISTS policydiff.claims_ref (
    cpt String,
    service_line String,
    avg_reimbursement_usd Float64,
    claim_count_90d UInt32,
    payer String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (cpt, payer);

CREATE TABLE IF NOT EXISTS policydiff.change_events (
    event_id UUID DEFAULT generateUUIDv4(),
    created_at DateTime DEFAULT now(),
    diff_id UUID,
    payer String,
    policy_id String,
    policy_title String,
    url String,
    service_line String,
    change_type String,
    confidence Float32,
    changed_clause String,
    change_summary String,
    clinical_impact String,
    cpt_codes_affected Array(String),
    revenue_at_risk_usd Float64,
    cited_md_url String,
    cited_markdown String,
    datadog_trace_id String DEFAULT '',
    status String DEFAULT 'PUBLISHED'
) ENGINE = MergeTree()
ORDER BY (created_at, payer, policy_id, change_type);

CREATE TABLE IF NOT EXISTS policydiff.classification_errors (
    error_id UUID DEFAULT generateUUIDv4(),
    created_at DateTime DEFAULT now(),
    diff_id UUID,
    payer String,
    policy_id String,
    error_stage String,
    error_message String
) ENGINE = MergeTree()
ORDER BY (created_at, error_stage);
```

---

## 6. Required status update

This is mandatory.

After successfully writing a `change_events` row, mark the source candidate as processed:

```sql
ALTER TABLE policydiff.diff_candidates
UPDATE status = 'PROCESSED', processed_at = now(), error_message = ''
WHERE diff_id = {diff_id:String};
```

If classification fails permanently:

```sql
ALTER TABLE policydiff.diff_candidates
UPDATE status = 'ERROR', error_message = {error_message:String}
WHERE diff_id = {diff_id:String};
```

Without this update, the same diff will be reprocessed on every run.

---

## 7. Gemini classification contract

Implement:

```python
def classify_diff(candidate: dict) -> dict:
    ...
```

Return exactly:

```json
{
  "change_type": "TIGHTENING",
  "confidence": 0.92,
  "changed_clause": "Member must have completed a cardiac stress test within the past 6 months.",
  "summary": "The payer added a new prerequisite before cardiac MRI authorization.",
  "clinical_impact": "Prior authorization teams must collect recent stress test documentation before submission.",
  "cpt_codes_affected": ["75561"],
  "recommended_action": "Update cardiology prior authorization checklist.",
  "markdown_title": "UHC Cardiac MRI Policy Tightened — New Stress Test Requirement Added"
}
```

### Classification rules

```text
TIGHTENING:
  New medical necessity requirement, documentation rule, exclusion, age/frequency restriction, prior auth requirement, or step therapy requirement added.

LOOSENING:
  Requirement removed, exception added, coverage expanded, documentation burden reduced.

SCOPE_CHANGE:
  CPT/HCPCS/ICD codes added or removed, policy now applies to a new service category.

STYLISTIC:
  Formatting, grammar, renumbering, disclaimers, contact information, or layout-only changes.
```

---

## 8. Gemini prompt requirements

Store the prompt in:

```text
services/classifier-service/prompts/classification_prompt.md
```

Prompt must instruct Gemini to:

- return JSON only,
- include one of the four allowed change types,
- include a `changed_clause` copied from the new policy text,
- avoid inventing CPT codes,
- use fallback CPT metadata if uncertain,
- distinguish wording edits from operational coverage changes.

Add this guardrail:

```text
If the new policy text does not contain enough evidence to support the changed_clause, return changed_clause = "UNSUPPORTED" and confidence below 0.50.
```

If `changed_clause == "UNSUPPORTED"`, do not publish to Senso. Mark the diff as `ERROR` or `NEEDS_REVIEW`.

---

## 9. Datadog LLM Observability requirement

Datadog tracing must be enabled for this service.

Install:

```bash
pip install ddtrace google-generativeai
```

Environment:

```bash
DD_API_KEY=your_key
DD_SITE=datadoghq.com
DD_LLMOBS_ENABLED=1
DD_LLMOBS_ML_APP=policydiff
```

Run service with:

```bash
ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8002
```

In code:

```python
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm, workflow

LLMObs.enable(ml_app="policydiff")

@workflow(name="process_pending_diffs", ml_app="policydiff")
def process_pending_diffs():
    ...

@llm(model_name="gemini-2.0-flash", model_provider="google", ml_app="policydiff")
def call_gemini(prompt: str):
    ...
```

Minimum demo requirement:

- one visible LLM trace in Datadog,
- latency and token usage visible if available,
- classifier service started with `ddtrace-run`.

---

## 10. Senso/cited.md publishing requirement

Senso is required because the dashboard should display generated markdowns from cited.md.

Implement:

```python
def publish_to_senso(event: dict) -> str:
    ...
```

The generated markdown should include:

```markdown
# UHC Cardiac MRI Policy Tightened — New Stress Test Requirement Added

## Summary
...

## What Changed
...

## Changed Clause
> Member must have completed a cardiac stress test within the past 6 months.

## Affected Codes
- 75561

## Revenue Impact
Estimated annualized revenue at risk: $261,000

## Recommended Action
Update the cardiology prior authorization checklist.

## Source
Policy URL: ...
```

### Senso publish flow

Try CLI first:

```bash
senso engine publish --data '<json payload>'
```

Fallback to API:

```http
POST https://apiv2.senso.ai/api/v1/org/{SENSO_ORG_HANDLE}/content-engine/publish
```

Expected return:

```json
{
  "cited_md_url": "https://cited.md/policydiff/uhc-cardiac-mri-tightening"
}
```

Store both the URL and markdown in `change_events`:

- `cited_md_url`
- `cited_markdown`

Engineer C will show the generated markdown link in the dashboard.

---

## 11. Revenue impact calculation

Implement:

```python
def compute_revenue_at_risk(cpt_codes: list[str], change_type: str) -> float:
    ...
```

Simple MVP formula:

```text
annualized_risk = sum(avg_reimbursement_usd * claim_count_90d * 4)
```

Only calculate revenue risk for:

- `TIGHTENING`
- `SCOPE_CHANGE`

For `LOOSENING`, return `0` or a separate opportunity metric. For `STYLISTIC`, return `0`.

Query:

```sql
SELECT sum(avg_reimbursement_usd * claim_count_90d * 4)
FROM policydiff.claims_ref
WHERE cpt IN ('75561', '93306');
```

Seed data:

```sql
INSERT INTO policydiff.claims_ref VALUES
('75557', 'Cardiology', 1800, 75, 'UHC'),
('75559', 'Cardiology', 2100, 65, 'UHC'),
('75561', 'Cardiology', 2200, 90, 'UHC'),
('93306', 'Cardiology', 700, 220, 'UHC'),
('93454', 'Cardiology', 4200, 40, 'Cigna'),
('73221', 'Radiology', 1240, 120, 'Aetna'),
('73721', 'Radiology', 1840, 180, 'Aetna'),
('72141', 'Orthopedics', 1580, 210, 'Humana'),
('72148', 'Orthopedics', 1650, 240, 'Humana'),
('71046', 'Radiology', 285, 300, 'Aetna');
```

---

## 12. API contract

### `GET /health`

```json
{
  "service": "classifier-service",
  "status": "ok"
}
```

### `POST /classify/run-once`

Processes up to `CLASSIFIER_BATCH_SIZE` pending candidates.

Response:

```json
{
  "processed": 2,
  "published": 2,
  "errors": 0
}
```

### `POST /classify/diff/{diff_id}`

Processes one candidate.

Response:

```json
{
  "diff_id": "uuid",
  "event_id": "uuid",
  "change_type": "TIGHTENING",
  "revenue_at_risk_usd": 261000,
  "cited_md_url": "https://cited.md/policydiff/uhc-cardiac-mri-tightening",
  "status": "PROCESSED"
}
```

### `GET /classify/pending`

Debug endpoint.

```json
[
  {
    "diff_id": "uuid",
    "payer": "UHC",
    "policy_id": "cardiac-mri",
    "created_at": "2026-05-23 11:30:00"
  }
]
```

---

## 13. Scheduler interval

Use a small polling loop or APScheduler.

Default:

```text
CLASSIFIER_POLL_INTERVAL_SECONDS=60
```

For demo:

```text
CLASSIFIER_POLL_INTERVAL_SECONDS=10
```

The classifier should process pending candidates independently of the ingestion service.

---

## 14. Environment variables

```bash
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DB=policydiff

GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.0-flash

SENSO_API_KEY=your_key
SENSO_ORG_HANDLE=policydiff

DD_API_KEY=your_key
DD_SITE=datadoghq.com
DD_LLMOBS_ENABLED=1
DD_LLMOBS_ML_APP=policydiff

CLASSIFIER_BATCH_SIZE=5
CLASSIFIER_POLL_INTERVAL_SECONDS=60
POLICY_CPT_MAP_PATH=./config/policy_cpt_map.yaml
```

---

## 15. Local run commands

```bash
cd services/classifier-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Process pending:

```bash
curl -X POST http://localhost:8002/classify/run-once
```

---

## 16. Error handling

### Gemini JSON parsing fails

Retry once with a stricter prompt. If it fails again:

- insert into `classification_errors`,
- update `diff_candidates.status = 'ERROR'`.

### Senso publish fails

Do not lose the classification. Store the event with:

```text
cited_md_url = ''
status = 'CLASSIFIED_NOT_PUBLISHED'
```

But for the final demo, at least one event should have a real `cited_md_url`.

### STYLISTIC changes

If change type is `STYLISTIC`, write the event but set revenue risk to `0`. The dashboard can show it in gray.

---

## 17. Integration checklist

- [ ] Can read `PENDING` rows from `diff_candidates`.
- [ ] Gemini returns valid JSON.
- [ ] `changed_clause` is present and not hallucinated.
- [ ] Revenue impact is computed from `claims_ref`.
- [ ] Senso publishes markdown to cited.md.
- [ ] `change_events` row contains `cited_md_url` and `cited_markdown`.
- [ ] `diff_candidates` row is updated to `PROCESSED`.
- [ ] Datadog LLM trace appears after one classification.
- [ ] Engineer C can fetch the change event from ClickHouse and display it.

---

## 18. Definition of done

Engineer B is done when:

1. `POST /classify/run-once` processes a pending diff.
2. `change_events` receives a complete event row.
3. The original `diff_candidates` row becomes `PROCESSED`.
4. Senso returns a cited.md URL and the markdown is visible.
5. Datadog records at least one Gemini LLM trace.
6. Engineer C can show the event and cited.md link in the dashboard.

Your success metric is simple: **the dashboard should display a classified policy change with revenue impact and a working cited.md markdown link.**
