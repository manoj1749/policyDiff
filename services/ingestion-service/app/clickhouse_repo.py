from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.settings import get_settings


class ClickHouseRepo:
    def __init__(
        self,
        client: Any | None = None,
        database: str | None = None,
    ) -> None:
        settings = get_settings()
        self.database = database or settings.clickhouse_db
        self.client = client or self._build_client()

    def _build_client(self) -> Any:
        import clickhouse_connect

        settings = get_settings()

        return clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=self.database,
            secure=settings.clickhouse_secure,
            verify=settings.clickhouse_verify,
        )

    def ping(self) -> bool:
        result = self.client.query("SELECT 1")
        return bool(getattr(result, "result_rows", []))

    def sync_policy_sources(self, policies: list[dict[str, Any]]) -> None:
        if not policies:
            return
        columns = [
            "payer",
            "policy_id",
            "policy_title",
            "url",
            "source_type",
            "service_line",
            "default_cpt_codes",
            "active",
            "updated_at",
        ]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            [
                policy["payer"],
                policy["policy_id"],
                policy["policy_title"],
                policy["url"],
                policy["source_type"],
                policy["service_line"],
                policy["default_cpt_codes"],
                policy["active"],
                now,
            ]
            for policy in policies
        ]
        self.client.insert(
            table="policy_sources",
            data=rows,
            column_names=columns,
            database=self.database,
        )

    def get_latest_policy_version(self, payer: str, policy_id: str) -> dict[str, Any] | None:
        query = f"""
        SELECT payer, policy_id, policy_title, url, source_type, version_hash,
               normalized_text, raw_extract, fetched_at, extraction_status, extraction_error
        FROM {self.database}.policy_versions FINAL
        WHERE payer = %(payer)s AND policy_id = %(policy_id)s
        ORDER BY fetched_at DESC
        LIMIT 1
        """
        result = self.client.query(query, parameters={"payer": payer, "policy_id": policy_id})
        if not getattr(result, "result_rows", None):
            return None
        row = result.result_rows[0]
        columns = list(result.column_names)
        return dict(zip(columns, row))

    def insert_policy_version(self, version: dict[str, Any]) -> None:
        columns = [
            "payer",
            "policy_id",
            "policy_title",
            "url",
            "source_type",
            "version_hash",
            "normalized_text",
            "raw_extract",
            "extraction_status",
            "extraction_error",
        ]
        row = [[version[column] for column in columns]]
        self.client.insert(
            table="policy_versions",
            data=row,
            column_names=columns,
            database=self.database,
        )

    def insert_diff_candidate(self, candidate: dict[str, Any]) -> str:
        diff_id = candidate.get("diff_id") or str(uuid.uuid4())
        columns = [
            "diff_id",
            "payer",
            "policy_id",
            "policy_title",
            "url",
            "source_type",
            "service_line",
            "old_hash",
            "new_hash",
            "old_text",
            "new_text",
            "default_cpt_codes",
            "status",
            "error_message",
        ]
        data = [
            [
                diff_id,
                candidate["payer"],
                candidate["policy_id"],
                candidate["policy_title"],
                candidate["url"],
                candidate["source_type"],
                candidate["service_line"],
                candidate["old_hash"],
                candidate["new_hash"],
                candidate["old_text"],
                candidate["new_text"],
                candidate["default_cpt_codes"],
                candidate.get("status", "PENDING"),
                candidate.get("error_message", ""),
            ]
        ]
        self.client.insert(
            table="diff_candidates",
            data=data,
            column_names=columns,
            database=self.database,
        )
        return diff_id

    def create_ingestion_run(self) -> dict[str, Any]:
        return {
            "run_id": str(uuid.uuid4()),
            "started_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

    def finish_ingestion_run(
        self,
        run_id: str,
        started_at: datetime,
        policies_attempted: int,
        policies_succeeded: int,
        policies_failed: int,
        diffs_created: int,
        status: str,
        error_message: str = "",
    ) -> None:
        columns = [
            "run_id",
            "started_at",
            "finished_at",
            "policies_attempted",
            "policies_succeeded",
            "policies_failed",
            "diffs_created",
            "status",
            "error_message",
        ]
        finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        data = [[
            run_id,
            started_at,
            finished_at,
            policies_attempted,
            policies_succeeded,
            policies_failed,
            diffs_created,
            status,
            error_message,
        ]]
        self.client.insert(
            table="ingestion_runs",
            data=data,
            column_names=columns,
            database=self.database,
        )

    def list_pending_diffs(self, limit: int = 20) -> list[dict[str, Any]]:
        query = f"""
        SELECT diff_id, payer, policy_id, status, created_at
        FROM {self.database}.diff_candidates
        WHERE status = 'PENDING'
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """
        result = self.client.query(query, parameters={"limit": limit})
        rows = getattr(result, "result_rows", [])
        columns = list(getattr(result, "column_names", []))
        return [dict(zip(columns, row)) for row in rows]
