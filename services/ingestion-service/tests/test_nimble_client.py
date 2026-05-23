from types import SimpleNamespace

import requests

from app.nimble_client import fetch_policy


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, reason: str = "OK", url: str = "https://example.com"):
        self.status_code = status_code
        self._payload = payload
        self.reason = reason
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"{self.status_code} Server Error: {self.reason} for url: {self.url}",
                response=self,
            )

    def json(self) -> dict:
        return self._payload


def _settings():
    return SimpleNamespace(
        nimble_api_key="test-key",
        nimble_api_url="https://api.nimbleway.com/v1/extract",
        nimble_request_timeout_seconds=30,
        nimble_html_extract_timeout_seconds=45,
        nimble_pdf_extract_timeout_seconds=90,
        nimble_max_retries=3,
        nimble_retry_backoff_seconds=0,
    )


def test_fetch_policy_retries_on_gateway_timeout_then_succeeds(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(504, {}, reason="Gateway Time-out")
        return FakeResponse(200, {"text": "COVERAGE CRITERIA\n1. Test content"})

    monkeypatch.setattr("app.nimble_client.get_settings", _settings)
    monkeypatch.setattr("app.nimble_client.requests.post", fake_post)
    monkeypatch.setattr("app.nimble_client.time.sleep", lambda *_args, **_kwargs: None)

    result = fetch_policy("https://example.com/policy", "html")

    assert calls["count"] == 2
    assert result["status"] == "SUCCESS"
    assert result["attempts"] == 2
    assert "COVERAGE CRITERIA" in result["raw_extract"]


def test_fetch_policy_does_not_retry_client_error(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return FakeResponse(400, {}, reason="Bad Request")

    monkeypatch.setattr("app.nimble_client.get_settings", _settings)
    monkeypatch.setattr("app.nimble_client.requests.post", fake_post)
    monkeypatch.setattr("app.nimble_client.time.sleep", lambda *_args, **_kwargs: None)

    result = fetch_policy("https://example.com/policy", "html")

    assert calls["count"] == 1
    assert result["status"] == "FAILED"
    assert result["attempts"] == 1
    assert result["error"] == "400 Server Error: Bad Request for url: https://example.com"


def test_fetch_policy_extracts_text_from_data_html(monkeypatch) -> None:
    def fake_post(*args, **kwargs):
        return FakeResponse(200, {"data": {"html": "<html><body><h1>COVERAGE CRITERIA</h1><p>1. Test policy</p></body></html>"}})

    monkeypatch.setattr("app.nimble_client.get_settings", _settings)
    monkeypatch.setattr("app.nimble_client.requests.post", fake_post)
    monkeypatch.setattr("app.nimble_client.time.sleep", lambda *_args, **_kwargs: None)

    result = fetch_policy("https://example.com/policy", "html")

    assert result["status"] == "SUCCESS"
    assert "COVERAGE CRITERIA" in result["raw_extract"]
    assert "1. Test policy" in result["raw_extract"]


def test_fetch_policy_rejects_upstream_error_page(monkeypatch) -> None:
    def fake_post(*args, **kwargs):
        return FakeResponse(
            200,
            {
                "url": "https://example.com/error-page.html",
                "status_code": 200,
                "data": {"html": "<html><body><h1>404</h1><p>Page not found</p></body></html>"},
            },
        )

    monkeypatch.setattr("app.nimble_client.get_settings", _settings)
    monkeypatch.setattr("app.nimble_client.requests.post", fake_post)
    monkeypatch.setattr("app.nimble_client.time.sleep", lambda *_args, **_kwargs: None)

    result = fetch_policy("https://example.com/policy", "html")

    assert result["status"] == "FAILED"
    assert "error page" in result["error"].lower() or "page-not-found" in result["error"].lower() or "page not found" in result["error"].lower()
