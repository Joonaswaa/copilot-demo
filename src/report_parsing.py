"""
report_parsing.py
-----------------
Extract narrative sections from the weekly markdown report for reuse
in PowerPoint (executive summary + management actions).
"""

from __future__ import annotations

import re

EXEC_SUMMARY_HEADERS = {
    "fi": ("## tiivistelmä johdolle", "## tiivistelma johdolle"),
    "en": ("## executive summary",),
}

ACTIONS_HEADERS = {
    "fi": ("## toimenpidesuositukset johdolle",),
    "en": ("## recommended management actions",),
}


def _split_sections(report_text: str) -> list[tuple[str, list[str]]]:
    """Return [(heading_lower, body_lines), ...] from markdown report."""
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []

    for raw_line in report_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            if current_heading or current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.lower().strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading or current_lines:
        sections.append((current_heading, current_lines))
    return sections


def _section_body(sections: list[tuple[str, list[str]]], headers: tuple[str, ...]) -> str:
    for heading, lines in sections:
        if heading in headers:
            paragraphs: list[str] = []
            chunk: list[str] = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if chunk:
                        paragraphs.append(" ".join(chunk))
                        chunk = []
                    continue
                if stripped.startswith("- "):
                    continue
                chunk.append(stripped)
            if chunk:
                paragraphs.append(" ".join(chunk))
            return "\n\n".join(paragraphs).strip()
    return ""


def _section_numbered_actions(sections: list[tuple[str, list[str]]],
                              headers: tuple[str, ...]) -> list[str]:
    for heading, lines in sections:
        if heading in headers:
            actions: list[str] = []
            for line in lines:
                stripped = line.strip()
                match = re.match(r"^\d+\.\s+(.+)$", stripped)
                if match:
                    actions.append(match.group(1).strip())
            return actions
    return []


def parse_executive_summary(report_text: str, language: str = "en") -> str:
    """Return the executive-summary narrative block (may include LLM interpretation)."""
    if not report_text:
        return ""
    lang = language if language in EXEC_SUMMARY_HEADERS else "en"
    sections = _split_sections(report_text)
    return _section_body(sections, EXEC_SUMMARY_HEADERS[lang])


def parse_management_actions(report_text: str, language: str = "en") -> list[str]:
    """Return numbered management action lines from the report."""
    if not report_text:
        return []
    lang = language if language in ACTIONS_HEADERS else "en"
    sections = _split_sections(report_text)
    return _section_numbered_actions(sections, ACTIONS_HEADERS[lang])
