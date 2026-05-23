from types import SimpleNamespace

from app.clickhouse_repo import ClickHouseRepo


class FakeClient:
    def __init__(self) -> None:
        self.inserts = []
        self.queries = []

    def insert(self, **kwargs):
        self.inserts.append(kwargs)

    def query(self, query, parameters=None):
        self.queries.append({"query": query, "parameters": parameters})
        if "policy_versions FINAL" in query:
            return SimpleNamespace(
                column_names=["payer", "policy_id", "version_hash", "normalized_text"],
                result_rows=[["UHC", "cardiac-mri", 123, "old text"]],
            )
        return SimpleNamespace(
            column_names=["diff_id", "payer", "policy_id", "status", "created_at"],
            result_rows=[["diff-1", "UHC", "cardiac-mri", "PENDING", "2026-05-23 11:30:00"]],
        )


def test_get_latest_policy_version_uses_final() -> None:
    client = FakeClient()
    repo = ClickHouseRepo(client=client)
    latest = repo.get_latest_policy_version("UHC", "cardiac-mri")
    assert client.queries
    assert "FINAL" in client.queries[0]["query"]
    assert latest is not None
    assert latest["version_hash"] == 123


def test_insert_diff_candidate_targets_expected_table() -> None:
    client = FakeClient()
    repo = ClickHouseRepo(client=client)
    diff_id = repo.insert_diff_candidate(
        {
            "payer": "UHC",
            "policy_id": "cardiac-mri",
            "policy_title": "Cardiac MRI Coverage Policy",
            "url": "https://example.com/policy",
            "source_type": "html",
            "service_line": "Cardiology",
            "old_hash": 1,
            "new_hash": 2,
            "old_text": "before",
            "new_text": "after",
            "default_cpt_codes": ["75557"],
            "status": "PENDING",
        }
    )
    assert diff_id
    assert client.inserts[0]["table"] == "diff_candidates"
    assert client.inserts[0]["database"] == "policydiff"
