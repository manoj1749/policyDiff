# PolicyDiff — Engineer A README
## Ingestion + Normalization + Diff Detection Service

**Owner:** Engineer A  
**Microservice name:** `ingestion-service`  
**Primary responsibility:** Fetch payer policy documents with Nimble, normalize HTML/PDF text, store versioned snapshots in ClickHouse, detect changed policies, and create `diff_candidates` for downstream AI classification.

---

## 1. Overall project context

PolicyDiff is an AI payer-policy change detection system for denial prevention.

Healthcare payers such as UnitedHealthcare, Aetna, Cigna, and Humana frequently update Clinical Policy Bulletins, coverage guidelines, imaging criteria, and medical-necessity rules. Hospitals often discover those changes weeks later, after prior authorizations and claims begin getting denied.

PolicyDiff solves this by building an automated pipeline:

```text
Nimble fetches payer policies
        ↓
Engineer A normalizes text + detects version changes
        ↓
ClickHouse stores policy versions + diff candidates
        ↓
Engineer B classifies changes with Gemini + publishes cited.md markdown via Senso
        ↓
Engineer C shows results in dashboard + exposes optional x402 export flow
```

Your service is the **data foundation**. If your service writes stable, clean `diff_candidates`, the rest of the system can integrate easily.

---

## 2. What you are building

You are building the ingestion microservice that:

1. Reads `config/watchlist.yaml`.
2. Fetches each payer policy using Nimble.
3. Handles both HTML pages and PDF documents.
4. Normalizes the extracted text into a stable canonical format.
5. Computes a deterministic content hash.
6. Stores every new policy version in ClickHouse.
7. Compares the newest version against the previous version.
8. Creates one row in `diff_candidates` when a meaningful content hash change is detected.
9. Exposes a small FastAPI interface so the team can trigger and test ingestion.

You do **not** classify the change. You do **not** call Gemini. You do **not** publish to Senso. You only produce reliable policy snapshots and diff candidates.

---

## 3. Service boundary

### You own

```text
services/ingestion-service/
├── app/
│   ├── main.py
│   ├── nimble_client.py
│   ├── normalizer.py
│   ├── hash_utils.py
│   ├── clickhouse_repo.py
│   ├── scheduler.py
│   └── config_loader.py
├── config/
│   └── watchlist.yaml
├── tests/
│   ├── test_normalizer.py
│   ├── test_hash_utils.py
│   └── test_clickhouse_repo.py
├── Dockerfile
├── requirements.txt
└── README.md
```

### You write to

- `policy_sources`
- `policy_versions`
- `diff_candidates`
- `ingestion_runs`

### You read from

- `policy_sources`
- latest rows from `policy_versions`

### You must not directly depend on

- `classifier-service`
- `dashboard-service`
- frontend code
- Senso
- x402
- Datadog

The services communicate through ClickHouse tables and API calls, not direct Python imports across services.

---

## 4. Important architecture rule

Do **not** make `ingestion-service` depend on `classifier-service` in Docker Compose.

Correct dependency pattern:

```yaml
ingestion-service:
  depends_on:
    - clickhouse

classifier-service:
  depends_on:
    - clickhouse

api-service:
  depends_on:
    - clickhouse
```

The ingestion service writes rows. The classifier service independently polls pending rows. Neither service should import or start the other.

---

## 5. Configuration file you must provide

Create this file before coding:

```text
services/ingestion-service/config/watchlist.yaml
```

Use this exact starter content:

```yaml
policies:
  - payer: UHC
    policy_id: cardiac-mri
    policy_title: Cardiac MRI Coverage Policy
    url: https://www.uhcprovider.com/en/policies-protocols/b-d/cardiac-mri.html
    source_type: html
    service_line: Cardiology
    default_cpt_codes: [75557, 75559, 75561]
    active: true

  - payer: UHC
    policy_id: vagus-nerve-stim
    policy_title: Vagus Nerve Stimulation Coverage Policy
    url: https://www.uhcprovider.com/en/policies-protocols/t-z/vagus-nerve-stimulation.html
    source_type: html
    service_line: Neurology
    default_cpt_codes: [64568, 64569, 64570]
    active: true

  - payer: Aetna
    policy_id: cpb-0761
    policy_title: Magnetic Resonance Imaging of the Extremities
    url: https://www.aetna.com/cpb/medical/data/700_799/0761.html
    source_type: html
    service_line: Radiology
    default_cpt_codes: [73221, 73721]
    active: true

  - payer: Aetna
    policy_id: cpb-0352
    policy_title: Diagnostic Imaging Policy
    url: https://www.aetna.com/cpb/medical/data/300_399/0352.html
    source_type: html
    service_line: Radiology
    default_cpt_codes: [71046, 71250]
    active: true

  - payer: Cigna
    policy_id: cardiac-imaging
    policy_title: Cardiac Imaging Guidelines
    url: https://www.cigna.com/static/www-cigna-com/docs/health-care-providers/resources/cardiac-imaging-criteria.pdf
    source_type: pdf
    service_line: Cardiology
    default_cpt_codes: [93306, 93454, 75561]
    active: true

  - payer: Humana
    policy_id: mri-spine
    policy_title: MRI Spine Clinical Criteria
    url: https://apps.availity.com/public-resources/assets/humana/clinical-criteria/HUM-MRI-SPINE.pdf
    source_type: pdf
    service_line: Orthopedics
    default_cpt_codes: [72141, 72148, 72156, 72158]
    active: true
```

This file is required because the classifier and dashboard depend on stable `payer`, `policy_id`, `policy_title`, `service_line`, and default CPT metadata.

---

## 6. ClickHouse schema you must create

Place the schema in:

```text
infra/clickhouse/001_ingestion_schema.sql
```

```sql
CREATE DATABASE IF NOT EXISTS policydiff;

CREATE TABLE IF NOT EXISTS policydiff.policy_sources (
    payer String,
    policy_id String,
    policy_title String,
    url String,
    source_type String,
    service_line String,
    default_cpt_codes Array(String),
    active UInt8 DEFAULT 1,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (payer, policy_id);

CREATE TABLE IF NOT EXISTS policydiff.policy_versions (
    payer String,
    policy_id String,
    policy_title String,
    url String,
    source_type String,
    version_hash UInt64,
    normalized_text String,
    raw_extract String,
    fetched_at DateTime DEFAULT now(),
    extraction_status String,
    extraction_error String DEFAULT ''
) ENGINE = ReplacingMergeTree(fetched_at)
ORDER BY (payer, policy_id, version_hash);

CREATE TABLE IF NOT EXISTS policydiff.diff_candidates (
    diff_id UUID DEFAULT generateUUIDv4(),
    created_at DateTime DEFAULT now(),
    payer String,
    policy_id String,
    policy_title String,
    url String,
    source_type String,
    service_line String,
    old_hash UInt64,
    new_hash UInt64,
    old_text String,
    new_text String,
    default_cpt_codes Array(String),
    status String DEFAULT 'PENDING',
    processed_at Nullable(DateTime),
    error_message String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (status, created_at, payer, policy_id);

CREATE TABLE IF NOT EXISTS policydiff.ingestion_runs (
    run_id UUID DEFAULT generateUUIDv4(),
    started_at DateTime DEFAULT now(),
    finished_at Nullable(DateTime),
    policies_attempted UInt32,
    policies_succeeded UInt32,
    policies_failed UInt32,
    diffs_created UInt32,
    status String,
    error_message String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (started_at, status);
```

### Important ClickHouse note

Because `policy_versions` uses `ReplacingMergeTree`, queries that require deduped latest rows should use `FINAL` when correctness matters:

```sql
SELECT version_hash, normalized_text, fetched_at
FROM policydiff.policy_versions FINAL
WHERE payer = 'UHC' AND policy_id = 'cardiac-mri'
ORDER BY fetched_at DESC
LIMIT 1;
```

For a hackathon demo, this is acceptable. In production, we would avoid excessive `FINAL` on very large tables and instead maintain a latest-version materialized view.

---

## 7. Nimble fetching requirements

Implement:

```python
def fetch_policy(url: str, source_type: str) -> dict:
    ...
```

Return shape:

```json
{
  "raw_extract": "string",
  "status": "SUCCESS",
  "error": "",
  "source_type": "html"
}
```

For both HTML and PDF, call Nimble with text extraction enabled.

Pseudo-code:

```python
payload = {
    "url": url,
    "render_js": source_type == "html",
    "ai_stealth": True,
    "extract_type": "text",
    "timeout": 30
}
```

### PDF handling rule

Cigna and Humana policies are PDFs. They must not go through the same HTML cleanup assumptions.

For `source_type: pdf`:

- do not remove lines just because they look like navigation text,
- preserve section headings,
- normalize page-break artifacts,
- remove repeated page footers only if obviously repetitive,
- keep CPT codes, bullet points, and numbered criteria.

For `source_type: html`:

- remove navigation text,
- remove cookie banners,
- remove header/footer boilerplate,
- collapse whitespace,
- preserve policy headings and numbered criteria.

---

## 8. Text normalization contract

Implement:

```python
def normalize_policy_text(raw_text: str, source_type: str) -> str:
    ...
```

Normalization must be deterministic. The same policy text should produce the same hash every time.

Minimum rules:

```text
- Convert Windows newlines to \n
- Strip leading/trailing whitespace
- Collapse 3+ blank lines into 2 blank lines
- Collapse repeated spaces inside a line
- Remove obvious cookie/privacy boilerplate for HTML
- Preserve numbered clinical criteria
- Preserve CPT/HCPCS codes
- Preserve headings like COVERAGE CRITERIA, EXCLUSIONS, PRIOR AUTHORIZATION
```

Do not over-normalize. If you remove too much, the classifier loses context.

---

## 9. Hashing contract

Implement:

```python
def compute_version_hash(normalized_text: str) -> int:
    ...
```

Use deterministic 64-bit hash. For speed, use `xxhash` if installed. Fallback to MD5 first 16 hex chars.

```python
try:
    import xxhash
    return xxhash.xxh64(normalized_text).intdigest()
except ImportError:
    import hashlib
    return int(hashlib.md5(normalized_text.encode("utf-8")).hexdigest()[:16], 16)
```

---

## 10. Diff creation logic

Implement:

```python
def process_policy(policy: dict) -> dict:
    ...
```

Behavior:

1. Fetch policy through Nimble.
2. Normalize extracted text.
3. Compute hash.
4. Query latest previous version using `FINAL`.
5. If no previous version exists:
   - insert into `policy_versions`,
   - do not create diff candidate,
   - return `FIRST_VERSION_STORED`.
6. If previous hash equals new hash:
   - insert nothing or optionally insert heartbeat only,
   - do not create diff candidate,
   - return `NO_CHANGE`.
7. If hash changed:
   - insert new version into `policy_versions`,
   - insert one row into `diff_candidates` with `status='PENDING'`,
   - return `DIFF_CREATED`.

---

## 11. API contract

Your service exposes these endpoints.

### `GET /health`

Response:

```json
{
  "service": "ingestion-service",
  "status": "ok"
}
```

### `POST /ingest/run-once`

Runs ingestion across all active watchlist policies.

Response:

```json
{
  "run_id": "uuid",
  "policies_attempted": 6,
  "policies_succeeded": 6,
  "policies_failed": 0,
  "diffs_created": 2,
  "status": "SUCCESS"
}
```

### `POST /ingest/policy/{payer}/{policy_id}`

Runs ingestion for one policy.

Response:

```json
{
  "payer": "UHC",
  "policy_id": "cardiac-mri",
  "result": "DIFF_CREATED",
  "old_hash": 123,
  "new_hash": 456
}
```

### `GET /ingest/pending-diffs`

Debug endpoint. Returns latest pending diff candidates.

Response:

```json
[
  {
    "diff_id": "uuid",
    "payer": "UHC",
    "policy_id": "cardiac-mri",
    "status": "PENDING",
    "created_at": "2026-05-23 11:30:00"
  }
]
```

---

## 12. Scheduler interval

Use APScheduler with this default:

```text
POLL_INTERVAL_MINUTES=30
```

Allow override through environment variable:

```python
interval = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))
```

For live demo, allow:

```text
POLL_INTERVAL_MINUTES=2
```

But do not hammer payer sites during development. Use seeded data and debug endpoints for most tests.

---

## 13. Seed data requirement

Create:

```text
services/ingestion-service/scripts/seed_demo_versions.py
```

It should insert one previous version for each watchlist policy so demo diffs can be created.

At minimum, create a known old version for:

- `UHC / cardiac-mri`
- `Aetna / cpb-0761`
- `Cigna / cardiac-imaging`
- `Humana / mri-spine`

Then provide a debug endpoint or script to insert a changed new version for `UHC / cardiac-mri`.

This protects the demo if live scraping is slow.

---

## 14. Environment variables

```bash
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DB=policydiff
NIMBLE_API_KEY=your_key
POLL_INTERVAL_MINUTES=30
WATCHLIST_PATH=./config/watchlist.yaml
```

---

## 15. Local run commands

```bash
cd services/ingestion-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Trigger once:

```bash
curl -X POST http://localhost:8001/ingest/run-once
```

Check pending diffs:

```bash
curl http://localhost:8001/ingest/pending-diffs
```

---

## 16. Error handling

If Nimble fails for one policy, do not fail the entire run. Mark that policy failed in `ingestion_runs` and continue.

If normalized text is empty, do not insert a version. Return:

```json
{
  "result": "EXTRACTION_EMPTY",
  "error": "Nimble returned no extractable policy text"
}
```

If ClickHouse insert fails, raise the error and mark the run as `FAILED`.

---

## 17. Integration checklist

Before saying your service is done, verify:

- [ ] `watchlist.yaml` exists and loads correctly.
- [ ] HTML policies normalize correctly.
- [ ] PDF policies normalize correctly.
- [ ] First fetch inserts `policy_versions` but no `diff_candidates`.
- [ ] Changed fetch inserts `policy_versions` and one `diff_candidates` row.
- [ ] `diff_candidates.status` starts as `PENDING`.
- [ ] Queries use `FINAL` where needed.
- [ ] Scheduler interval defaults to 30 minutes.
- [ ] `/ingest/run-once` works.
- [ ] Classifier service can read your `PENDING` candidate.

---

## 18. Definition of done

Engineer A is done when:

1. ClickHouse schema is created.
2. `watchlist.yaml` is committed.
3. Ingestion service can fetch at least one HTML and one PDF policy.
4. Normalization produces stable hashes.
5. A policy change creates a `PENDING` row in `diff_candidates`.
6. The rest of the team can run one command and see pending diffs in ClickHouse.

Your success metric is simple: **Engineer B should be able to start classification using only the `diff_candidates` table without asking you for extra context.**
