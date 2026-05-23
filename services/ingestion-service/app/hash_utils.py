from __future__ import annotations

import hashlib


def compute_version_hash(normalized_text: str) -> int:
    try:
        import xxhash  # type: ignore

        return xxhash.xxh64(normalized_text).intdigest()
    except ImportError:
        return int(hashlib.md5(normalized_text.encode("utf-8")).hexdigest()[:16], 16)

