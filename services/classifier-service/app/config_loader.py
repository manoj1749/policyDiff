"""
config_loader.py — Loads environment variables and policy_cpt_map.yaml.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # ClickHouse
    clickhouse_host: str = field(default_factory=lambda: os.getenv("CLICKHOUSE_HOST", "localhost"))
    clickhouse_port: int = field(default_factory=lambda: int(os.getenv("CLICKHOUSE_PORT", "8123")))
    clickhouse_user: str = field(default_factory=lambda: os.getenv("CLICKHOUSE_USER", "default"))
    clickhouse_password: str = field(default_factory=lambda: os.getenv("CLICKHOUSE_PASSWORD", ""))
    clickhouse_db: str = field(default_factory=lambda: os.getenv("CLICKHOUSE_DB", "policydiff"))
    clickhouse_secure: bool = field(default_factory=lambda: os.getenv("CLICKHOUSE_SECURE", "false").lower() == "true")
    clickhouse_verify: bool = field(default_factory=lambda: os.getenv("CLICKHOUSE_VERIFY", "true").lower() == "true")

    # Gemini
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))

    # Senso
    senso_api_key: str = field(default_factory=lambda: os.getenv("SENSO_API_KEY", ""))
    senso_org_handle: str = field(default_factory=lambda: os.getenv("SENSO_ORG_HANDLE", "policydiff"))

    # Datadog
    dd_api_key: str = field(default_factory=lambda: os.getenv("DD_API_KEY", ""))
    dd_site: str = field(default_factory=lambda: os.getenv("DD_SITE", "datadoghq.com"))
    dd_llmobs_enabled: bool = field(
        default_factory=lambda: os.getenv("DD_LLMOBS_ENABLED", "1") == "1"
    )
    dd_llmobs_ml_app: str = field(default_factory=lambda: os.getenv("DD_LLMOBS_ML_APP", "policydiff"))

    # Classifier behaviour
    batch_size: int = field(default_factory=lambda: int(os.getenv("CLASSIFIER_BATCH_SIZE", "5")))
    poll_interval_seconds: int = field(
        default_factory=lambda: int(os.getenv("CLASSIFIER_POLL_INTERVAL_SECONDS", "60"))
    )

    # Paths
    policy_cpt_map_path: str = field(
        default_factory=lambda: os.getenv(
            "POLICY_CPT_MAP_PATH",
            str(Path(__file__).parent.parent / "config" / "policy_cpt_map.yaml"),
        )
    )
    prompt_path: str = field(
        default_factory=lambda: str(
            Path(__file__).parent.parent / "prompts" / "classification_prompt.md"
        )
    )

    # Loaded at runtime
    policy_cpt_map: dict = field(default_factory=dict)
    classification_prompt_template: str = ""

    def __post_init__(self) -> None:
        self._load_cpt_map()
        self._load_prompt_template()

    def _load_cpt_map(self) -> None:
        path = Path(self.policy_cpt_map_path)
        if path.exists():
            with open(path) as f:
                raw = yaml.safe_load(f)
            self.policy_cpt_map = raw.get("policies", {})
        else:
            self.policy_cpt_map = {}

    def _load_prompt_template(self) -> None:
        path = Path(self.prompt_path)
        if path.exists():
            self.classification_prompt_template = path.read_text()
        else:
            self.classification_prompt_template = ""

    def get_fallback_cpts(self, payer: str, policy_id: str) -> list[str]:
        """Return fallback CPT codes from the YAML map for a given payer+policy_id."""
        key = f"{payer}:{policy_id}"
        entry = self.policy_cpt_map.get(key, {})
        return [str(c) for c in entry.get("cpt_codes", [])]


# Singleton — import this everywhere
settings = Settings()
