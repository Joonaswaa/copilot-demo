"""
email_sender.py
---------------
Emails the weekly supply chain package via SMTP:

  * HTML + plain-text body with KPI summary
  * PDF report attachment
  * EN + FI PowerPoint deck attachments

Configuration (see .env.example):

    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    REPORT_SENDER, REPORT_RECIPIENTS  (comma-separated)
    SMTP_USE_TLS=true   (default, port 587)
    SMTP_USE_SSL=false  (set true for port 465)

Nothing is sent unless the user clicks Send in the dashboard
and SMTP settings are present.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LABELS = {
    "en": {
        "subject": "Weekly Supply Chain Report — {date}",
        "greeting": "Hello,",
        "intro": (
            "Please find this week's supply chain summary below. "
            "The full report (PDF) and management decks (EN + FI) are attached."
        ),
        "kpi_heading": "Key figures this week",
        "kpi_inventory": "Inventory value",
        "kpi_skus": "SKUs",
        "kpi_stockout": "Stockout risk SKUs",
        "kpi_high_risk": "High-risk products",
        "kpi_delayed": "Delayed deliveries",
        "kpi_purchases": "Recommended purchases",
        "kpi_on_time": "Supplier on-time rate",
        "footer": "Telecom Supply Chain AI Copilot — automated weekly report",
        "not_configured": (
            "Email is not configured. Copy .env.example to .env and fill in "
            "the SMTP settings."
        ),
        "sent": "Report sent to {count} recipient(s): {recipients}.",
        "failed": "Sending failed: {error}",
        "no_recipients": "No recipients configured in REPORT_RECIPIENTS.",
    },
    "fi": {
        "subject": "Viikoittainen toimitusketjuraportti — {date}",
        "greeting": "Hei,",
        "intro": (
            "Alla viikon toimitusketjun yhteenveto. "
            "Liitteenä täysi raportti (PDF) sekä johdon esitykset (EN + FI)."
        ),
        "kpi_heading": "Viikon keskeiset luvut",
        "kpi_inventory": "Varaston arvo",
        "kpi_skus": "Nimikkeet",
        "kpi_stockout": "Loppumisriski",
        "kpi_high_risk": "Korkean riskin tuotteet",
        "kpi_delayed": "Myöhässä olevat toimitukset",
        "kpi_purchases": "Suositellut ostot",
        "kpi_on_time": "Toimitusvarmuus",
        "footer": "Telecom Supply Chain AI Copilot — automaattinen viikkoraportti",
        "not_configured": (
            "Sähköpostia ei ole määritetty. Kopioi .env.example → .env ja "
            "täytä SMTP-asetukset."
        ),
        "sent": "Raportti lähetetty {count} vastaanottajalle: {recipients}.",
        "failed": "Lähetys epäonnistui: {error}",
        "no_recipients": "Vastaanottajia ei ole määritetty (REPORT_RECIPIENTS).",
    },
}


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")


def is_configured() -> bool:
    """True if all required SMTP settings are present."""
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD",
                "REPORT_SENDER", "REPORT_RECIPIENTS"]
    return all(os.getenv(key) for key in required)


def get_recipients() -> list[str]:
    raw = os.getenv("REPORT_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def _fmt_eur(value: float) -> str:
    return f"€{value:,.0f}"


def _fmt_date(language: str) -> str:
    return date.today().strftime("%d.%m.%Y")


def _kpi_rows(kpis: dict, language: str) -> list[tuple[str, str]]:
    lbl = LABELS[language]
    return [
        (lbl["kpi_inventory"], _fmt_eur(kpis["total_inventory_value"])),
        (lbl["kpi_skus"], str(kpis["sku_count"])),
        (lbl["kpi_stockout"], str(kpis["stockout_count"])),
        (lbl["kpi_high_risk"], str(kpis["high_risk_count"])),
        (lbl["kpi_delayed"], str(kpis["delayed_deliveries"])),
        (lbl["kpi_purchases"], _fmt_eur(kpis["recommended_purchase_value"])),
        (lbl["kpi_on_time"], f"{kpis['avg_on_time_rate']:.1f} %"),
    ]


def build_email_bodies(kpis: dict, language: str = "en") -> tuple[str, str]:
    """Return (plain_text, html) email bodies."""
    if language not in LABELS:
        language = "en"
    lbl = LABELS[language]
    rows = _kpi_rows(kpis, language)

    plain_lines = [
        lbl["greeting"],
        "",
        lbl["intro"],
        "",
        lbl["kpi_heading"],
    ]
    for name, value in rows:
        plain_lines.append(f"  • {name}: {value}")
    plain_lines += ["", lbl["footer"]]
    plain = "\n".join(plain_lines)

    table_rows = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #e8eef8;"
        f"color:#4a4a4a'>{name}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #e8eef8;"
        f"font-weight:600;color:#002CAC;text-align:right'>{value}</td></tr>"
        for name, value in rows
    )
    html = f"""\
<!DOCTYPE html>
<html><body style="font-family:Calibri,Arial,sans-serif;color:#1d1d1f;
max-width:640px;margin:0 auto;padding:24px">
  <p>{lbl["greeting"]}</p>
  <p>{lbl["intro"]}</p>
  <h3 style="color:#002CAC;margin-top:24px">{lbl["kpi_heading"]}</h3>
  <table style="border-collapse:collapse;width:100%;margin:12px 0 24px">
    {table_rows}
  </table>
  <p style="font-size:12px;color:#6e6e73;margin-top:32px">{lbl["footer"]}</p>
</body></html>"""
    return plain, html


def _attach_file(msg: EmailMessage, path: Path) -> None:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        msg.add_attachment(data, maintype="application", subtype="pdf",
                           filename=path.name)
    elif suffix == ".pptx":
        msg.add_attachment(data, maintype="application",
                           subtype="vnd.openxmlformats-officedocument."
                           "presentationml.presentation",
                           filename=path.name)
    elif suffix == ".md":
        msg.add_attachment(data, maintype="text", subtype="markdown",
                           filename=path.name)


def _smtp_send(msg: EmailMessage, recipients: list[str]) -> None:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = _env_bool("SMTP_USE_SSL")
    use_tls = _env_bool("SMTP_USE_TLS", default=not use_ssl)

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
            server.login(user, password)
            server.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            if use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()
            server.login(user, password)
            server.send_message(msg, to_addrs=recipients)


def send_report_email(
    report_text: str,
    kpis: dict,
    pdf_path: str | Path | None = None,
    pptx_path_en: str | Path | None = None,
    pptx_path_fi: str | Path | None = None,
    language: str = "en",
    subject: str | None = None,
) -> tuple[bool, str]:
    """
    Send the weekly package by email. Returns (success, status_message).
    """
    if language not in LABELS:
        language = "en"
    lbl = LABELS[language]

    if not is_configured():
        return False, lbl["not_configured"]

    recipients = get_recipients()
    if not recipients:
        return False, lbl["no_recipients"]

    try:
        plain, html = build_email_bodies(kpis, language)
        msg = EmailMessage()
        msg["Subject"] = subject or lbl["subject"].format(date=_fmt_date(language))
        msg["From"] = os.getenv("REPORT_SENDER")
        msg["To"] = ", ".join(recipients)
        msg.set_content(plain)
        msg.add_alternative(html, subtype="html")

        for path in (pdf_path, pptx_path_en, pptx_path_fi):
            if path and Path(path).exists():
                _attach_file(msg, Path(path))

        _smtp_send(msg, recipients)

        return True, lbl["sent"].format(
            count=len(recipients),
            recipients=", ".join(recipients),
        )
    except Exception as exc:
        return False, lbl["failed"].format(error=exc)
