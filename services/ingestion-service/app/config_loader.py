from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PolicyConfig:
    payer: str
    policy_id: str
    policy_title: str
    url: str
    source_type: str
    service_line: str
    default_cpt_codes: list[str]
    active: bool = True

    def to_source_row(self) -> dict[str, Any]:
        return {
            "payer": self.payer,
            "policy_id": self.policy_id,
            "policy_title": self.policy_title,
            "url": self.url,
            "source_type": self.source_type,
            "service_line": self.service_line,
            "default_cpt_codes": self.default_cpt_codes,
            "active": 1 if self.active else 0,
        }


def load_watchlist(path: str | Path) -> list[PolicyConfig]:
    watchlist_path = Path(path)
    payload = yaml.safe_load(watchlist_path.read_text(encoding="utf-8")) or {}
    items = payload.get("policies", [])
    policies: list[PolicyConfig] = []
    for item in items:
        policies.append(
            PolicyConfig(
                payer=item["payer"],
                policy_id=item["policy_id"],
                policy_title=item["policy_title"],
                url=item["url"],
                source_type=item["source_type"],
                service_line=item["service_line"],
                default_cpt_codes=[str(code) for code in item.get("default_cpt_codes", [])],
                active=bool(item.get("active", True)),
            )
        )
    return policies

