from app.normalizer import normalize_policy_text


def test_html_normalizer_removes_cookie_banners_and_collapses_whitespace() -> None:
    raw = """
    Skip to content
    Accept All Cookies
    COVERAGE CRITERIA

    1.   MRI is covered for heart failure.
    Cookie Preferences
    CPT   75557
    """
    normalized = normalize_policy_text(raw, "html")
    assert "Accept All Cookies" not in normalized
    assert "Cookie Preferences" not in normalized
    assert "COVERAGE CRITERIA" in normalized
    assert "1. MRI is covered for heart failure." in normalized
    assert "CPT 75557" in normalized


def test_pdf_normalizer_preserves_clinical_content_and_removes_repeated_footer() -> None:
    raw = """
    CARDIAC IMAGING GUIDELINES
    1. Stress imaging is indicated after abnormal ECG.
    Page 1 of 3

    EXCLUSIONS
    2. Screening without symptoms is not covered.
    Page 1 of 3

    CPT 93306 93454 75561
    Page 1 of 3
    """
    normalized = normalize_policy_text(raw, "pdf")
    assert "CARDIAC IMAGING GUIDELINES" in normalized
    assert "EXCLUSIONS" in normalized
    assert "2. Screening without symptoms is not covered." in normalized
    assert "CPT 93306 93454 75561" in normalized
    assert "Page 1 of 3" not in normalized

