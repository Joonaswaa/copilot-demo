"""
pdf_exporter.py
---------------
Turns the markdown-style weekly report into a simple, clean PDF using
fpdf2 (imported as `fpdf`). Kept intentionally lightweight: headings,
bullet lists and paragraphs — enough for a management report that gets
attached to an email.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

PAGE_MARGIN = 15


class ReportPDF(FPDF):
    """PDF with a small header/footer suitable for a weekly report."""

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, "Telecom Supply Chain AI Copilot", align="L")
        self.cell(0, 8, date.today().isoformat(), align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(PAGE_MARGIN, 22, 210 - PAGE_MARGIN, 22)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _mc(pdf: FPDF, h: float, text: str) -> None:
    """multi_cell that returns the cursor to the left margin.
    (Newer fpdf2 leaves x at the right edge by default, which makes
    the next multi_cell fail with zero width.)"""
    pdf.multi_cell(0, h, text, new_x="LMARGIN", new_y="NEXT")


def _sanitize(text: str) -> str:
    """Replace characters outside Latin-1 so core PDF fonts render them."""
    replacements = {"€": "EUR ", "—": "-", "–": "-", "’": "'", "“": '"', "”": '"'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def export_report_pdf(report_text: str,
                      output_path: str | Path = "outputs/reports/weekly_report.pdf") -> Path:
    """
    Render the markdown-ish report text (# / ## headings, - bullets)
    into a PDF file. Returns the path to the created file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(PAGE_MARGIN, PAGE_MARGIN)
    pdf.add_page()

    for raw_line in report_text.split("\n"):
        line = _sanitize(raw_line.rstrip())

        if not line:
            pdf.ln(3)
        elif line.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(20, 40, 80)
            _mc(pdf, 9, line[2:])
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(20, 40, 80)
            _mc(pdf, 7, line[3:])
            pdf.ln(1)
        elif line.startswith("- ") or line[:2].strip().isdigit():
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 30)
            text = line[2:] if line.startswith("- ") else line
            bullet = "-  " if line.startswith("- ") else ""
            _mc(pdf, 5.5, f"{bullet}{text}")
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 30)
            _mc(pdf, 5.5, line)

    pdf.output(str(output_path))
    return output_path
