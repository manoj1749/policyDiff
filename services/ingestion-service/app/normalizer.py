from __future__ import annotations

import html
import re
from collections import Counter

HTML_DROP_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^skip to (main )?content$",
        r"^cookie(s| policy| preferences)?$",
        r"^privacy( policy)?$",
        r"^terms( of use| and conditions)?$",
        r"^copyright\b",
        r"^site map$",
        r"^contact us$",
        r"^back to top$",
        r"^print($| this page)",
        r"^share($| this page)",
        r"^accept( all)? cookies$",
        r"^manage preferences$",
        r"^close$",
    )
]

HTML_INLINE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"cookie preferences",
        r"we (use|and our partners use) cookies",
        r"privacy choices",
        r"javascript is required",
    )
]

REPEATED_SPACE_RE = re.compile(r"[ \t]{2,}")
THREE_PLUS_BLANKS_RE = re.compile(r"\n{3,}")


def normalize_policy_text(raw_text: str, source_type: str) -> str:
    text = html.unescape(raw_text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")

    if source_type == "html":
        text = _normalize_html(text)
    elif source_type == "pdf":
        text = _normalize_pdf(text)
    else:
        text = _normalize_lines(text.split("\n"))

    text = THREE_PLUS_BLANKS_RE.sub("\n\n", text)
    return text.strip()


def _normalize_html(text: str) -> str:
    for pattern in HTML_INLINE_PATTERNS:
        text = pattern.sub("", text)
    lines = []
    for raw_line in text.split("\n"):
        cleaned = _clean_line(raw_line)
        if not cleaned:
            lines.append("")
            continue
        if any(pattern.search(cleaned) for pattern in HTML_DROP_PATTERNS):
            continue
        lines.append(cleaned)
    return _normalize_lines(lines)


def _normalize_pdf(text: str) -> str:
    lines = [_clean_line(line) for line in text.split("\n")]
    footer_candidates = _find_repeated_footer_lines(lines)
    filtered = [line for line in lines if line not in footer_candidates]
    return _normalize_lines(filtered)


def _normalize_lines(lines: list[str]) -> str:
    normalized: list[str] = []
    previous_blank = False
    for line in lines:
        compact = _clean_line(line)
        if not compact:
            if not previous_blank:
                normalized.append("")
            previous_blank = True
            continue
        normalized.append(compact)
        previous_blank = False
    return "\n".join(normalized)


def _clean_line(line: str) -> str:
    compact = REPEATED_SPACE_RE.sub(" ", (line or "").strip())
    compact = re.sub(r"\s+([:;,.])", r"\1", compact)
    return compact


def _find_repeated_footer_lines(lines: list[str]) -> set[str]:
    candidates = [
        line
        for line in lines
        if line
        and len(line) <= 120
        and (
            "page " in line.lower()
            or "copyright" in line.lower()
            or line.lower().startswith("https://")
            or line.lower().startswith("http://")
        )
    ]
    counts = Counter(candidates)
    return {line for line, count in counts.items() if count >= 3}

