from app.hash_utils import compute_version_hash


def test_hash_is_deterministic() -> None:
    text = "COVERAGE CRITERIA\n1. Example policy"
    assert compute_version_hash(text) == compute_version_hash(text)


def test_hash_changes_when_text_changes() -> None:
    assert compute_version_hash("foo") != compute_version_hash("bar")

