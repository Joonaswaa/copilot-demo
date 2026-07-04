"""
rpa_workflow.py
---------------
Weekly supply chain RPA / workflow automation layer.

Simulates: ERP export → validation → analytics → purchase CSV →
reports → email draft → archive.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.data_cleaning import clean_data
from src.data_loader import load_file
from src.data_validation import validate_erp_dataframe
from src.demand_forecasting import add_forecasts
from src.pdf_exporter import export_report_pdf
from src.pptx_exporter import export_weekly_deck
from src.replenishment import recommend_purchases
from src.report_generator import (
    compute_kpis,
    copilot_recommendations,
    generate_report,
)
from src.risk_scoring import add_risk_scores
from src.slow_moving_analysis import find_slow_movers
from src.supplier_analysis import supplier_scorecard, supplier_warnings

ERP_EXTENSIONS = (".csv", ".xlsx", ".xls")

DEFAULT_CONFIG: dict[str, Any] = {
    "erp_exports_dir": "data/erp_exports",
    "processed_dir": "data/processed",
    "reports_weekly_dir": "reports/weekly",
    "reports_archive_dir": "reports/archive",
    "outbox_purchases_dir": "outbox/purchase_recommendations",
    "outbox_email_dir": "outbox/email_drafts",
    "logs_dir": "logs/workflow_runs",
    "forecast_method": "exponential",
}

STEP_ERP_FOUND = "ERP export found"
STEP_VALIDATED = "Data validated"
STEP_INVENTORY = "Inventory analysis completed"
STEP_FORECAST = "Demand forecast completed"
STEP_SUPPLIER = "Supplier analysis completed"
STEP_PURCHASES = "Purchase recommendations generated"
STEP_PDF = "PDF report generated"
STEP_PPTX = "PowerPoint generated"
STEP_EMAIL = "Email draft prepared"
STEP_ARCHIVE = "Files archived"


def _project_root(config: dict) -> Path:
    root = config.get("project_root")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent


def _resolve(config: dict, key: str) -> Path:
    return _project_root(config) / config[key]


def ensure_workflow_dirs(config: dict | None = None) -> None:
    """Create all workflow directories if missing."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    for key in (
        "erp_exports_dir", "processed_dir", "reports_weekly_dir",
        "reports_archive_dir", "outbox_purchases_dir", "outbox_email_dir",
        "logs_dir",
    ):
        _resolve(cfg, key).mkdir(parents=True, exist_ok=True)


def find_latest_erp_export(folder_path: str | Path) -> Path:
    """
    Find the newest ERP export (.csv / .xlsx / .xls) by modification time.
    Raises FileNotFoundError with a clear message if none exist.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(
            f"ERP export folder does not exist: {folder}. "
            f"Create it and add a CSV or Excel export."
        )

    candidates = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in ERP_EXTENSIONS
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No ERP export found in {folder}. "
            f"Add a .csv, .xlsx or .xls file and run the workflow again."
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _step(name: str, status: str, message: str = "") -> dict:
    return {"name": name, "status": status, "message": message}


def _run_step(
    steps: list[dict],
    name: str,
    fn: Callable[[], str],
    *,
    warning_ok: bool = False,
) -> bool:
    """Run a workflow step. Returns False if step failed fatally."""
    try:
        message = fn()
        steps.append(_step(name, "success", message))
        return True
    except Exception as exc:
        status = "warning" if warning_ok else "error"
        steps.append(_step(name, status, str(exc)))
        return warning_ok


def build_rpa_purchase_export(df: pd.DataFrame) -> pd.DataFrame:
    """
    RPA-style purchase recommendation table (simpler order-up-to rule).
    """
    rows = []
    for _, row in df.iterrows():
        stock = float(row["current_stock"])
        rp = float(row["reorder_point"])
        ss = float(row["safety_stock"])
        qty = max(0, int(rp + ss - stock))

        if stock < ss:
            priority = "Urgent"
        elif stock < rp:
            priority = "High"
        elif stock < rp + ss:
            priority = "Medium"
        else:
            priority = "Low"

        if qty <= 0 and priority == "Low":
            continue

        cost = round(qty * float(row["unit_cost"]), 2)
        reason = (
            f"Order-up-to target {int(rp + ss)} units; "
            f"current stock {int(stock)}."
        )
        rows.append({
            "sku": row["sku"],
            "product_name": row["product_name"],
            "supplier": row["supplier"],
            "current_stock": int(stock),
            "reorder_point": int(rp),
            "safety_stock": int(ss),
            "monthly_demand": int(row["monthly_demand"]),
            "lead_time_days": int(row["lead_time_days"]),
            "recommended_order_qty": qty,
            "estimated_purchase_cost": cost,
            "priority": priority,
            "reason": reason,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    rank = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
    return out.sort_values("priority", key=lambda s: s.map(rank)).reset_index(drop=True)


def _write_purchase_csv(orders: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    orders.to_csv(path, index=False)


def _write_email_draft(
    path: Path,
    *,
    run_id: str,
    kpis: dict,
    recs: list[dict],
    attachments: list[str],
    language: str = "en",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%d.%m.%Y")

    if language == "fi":
        subject = f"Viikoittainen toimitusketjuraportti — {today}"
        greeting = "Hei,"
        intro = (
            "Liitteenä viikon johdon paketti: PDF-raportti ja PowerPoint-esitykset (EN + FI). "
            "Demo / synteettinen data."
        )
        kpi_title = "Keskeiset luvut"
        actions_title = "Top 5 toimenpidettä"
        attach_title = "Liitteet"
        disclaimer = (
            "Tämä on portfolio-demon automaattinen luonnos. "
            "Data on synteettistä — ei lähetetä oikeaa sähköpostia."
        )
    else:
        subject = f"Weekly Supply Chain Report — {today}"
        greeting = "Hello,"
        intro = (
            "Attached: weekly management package — PDF report and PowerPoint decks (EN + FI). "
            "Demo / synthetic data."
        )
        kpi_title = "Key figures"
        actions_title = "Top 5 recommended actions"
        attach_title = "Attachments"
        disclaimer = (
            "This is an automated draft from the portfolio demo. "
            "Data is synthetic — no real email is sent."
        )

    kpi_rows = [
        ("Inventory value", f"€{kpis['total_inventory_value']:,.0f}"),
        ("SKUs", str(kpis["sku_count"])),
        ("Stockout risk", str(kpis["stockout_count"])),
        ("High-risk products", str(kpis["high_risk_count"])),
        ("Delayed deliveries", str(kpis["delayed_deliveries"])),
        ("Recommended purchases", f"€{kpis['recommended_purchase_value']:,.0f}"),
        ("Supplier on-time rate", f"{kpis['avg_on_time_rate']:.1f}%"),
    ]

    kpi_html = "".join(
        f"<tr><td>{k}</td><td><strong>{v}</strong></td></tr>" for k, v in kpi_rows
    )
    actions_html = "".join(
        f"<li><strong>{r['action']}</strong><br><span style='color:#666'>"
        f"{r['detail']}</span></li>"
        for r in recs[:5]
    )
    attach_html = "".join(f"<li>{Path(a).name}</li>" for a in attachments if a)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family:Calibri,Arial,sans-serif;max-width:640px;margin:24px auto">
  <p><strong>Subject:</strong> {subject}</p>
  <p>{greeting}</p>
  <p>{intro}</p>
  <h3 style="color:#002CAC">{kpi_title}</h3>
  <table style="border-collapse:collapse;width:100%">{kpi_html}</table>
  <h3 style="color:#002CAC">{actions_title}</h3>
  <ol>{actions_html or '<li>No urgent actions this week.</li>'}</ol>
  <h3 style="color:#002CAC">{attach_title}</h3>
  <ul>{attach_html or '<li>(none)</li>'}</ul>
  <p style="font-size:12px;color:#888;margin-top:32px">{disclaimer}</p>
  <p style="font-size:11px;color:#aaa">Run ID: {run_id}</p>
</body></html>"""
    path.write_text(html, encoding="utf-8")


def _save_run_log(result: dict, config: dict) -> Path:
    log_dir = _resolve(config, "logs_dir")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{result['run_id']}.json"
    log_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return log_path


def load_recent_runs(config: dict | None = None, limit: int = 5) -> list[dict]:
    """Load the most recent workflow run logs (newest first)."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    log_dir = _resolve(cfg, "logs_dir")
    if not log_dir.is_dir():
        return []
    files = sorted(log_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    runs = []
    for path in files[:limit]:
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def run_analytics_pipeline(
    raw: pd.DataFrame,
    forecast_method: str = "exponential",
) -> dict:
    """Shared analytics pipeline used by dashboard and RPA workflow."""
    df = clean_data(raw)
    df = add_forecasts(df, method=forecast_method)
    df = add_risk_scores(df)
    orders = recommend_purchases(df)
    slow = find_slow_movers(df)
    scorecard = supplier_scorecard(df)
    warnings = supplier_warnings(scorecard)
    kpis = compute_kpis(df, orders, slow)
    recs = copilot_recommendations(df, orders, slow, scorecard, warnings)
    return {
        "df": df, "orders": orders, "slow": slow,
        "scorecard": scorecard, "warnings": warnings,
        "kpis": kpis, "recs": recs,
    }


def run_weekly_rpa_workflow(config: dict | None = None) -> dict:
    """
    Run the full weekly supply chain automation workflow.

    Returns a result dict with success, run_id, steps, outputs, errors.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    ensure_workflow_dirs(cfg)

    run_id = _new_run_id()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: list[dict] = []
    errors: list[str] = []
    outputs: dict[str, str | None] = {
        "erp_source": None,
        "pdf_report": None,
        "pptx_report_en": None,
        "pptx_report_fi": None,
        "purchase_recommendations": None,
        "email_draft": None,
        "workflow_log": None,
    }

    erp_path: Path | None = None
    analytics: dict | None = None

    # --- 1. ERP export ---------------------------------------------------
    try:
        override = cfg.get("erp_path")
        if override:
            erp_path = Path(override)
            if not erp_path.is_file():
                raise FileNotFoundError(f"Configured ERP export not found: {erp_path}")
        else:
            erp_path = find_latest_erp_export(_resolve(cfg, "erp_exports_dir"))
        outputs["erp_source"] = str(erp_path)
        steps.append(_step(
            STEP_ERP_FOUND, "success",
            f"Using {erp_path.name} (modified {datetime.fromtimestamp(erp_path.stat().st_mtime):%Y-%m-%d %H:%M})",
        ))
    except FileNotFoundError as exc:
        msg = str(exc)
        steps.append(_step(STEP_ERP_FOUND, "error", msg))
        errors.append(msg)
        result = _finalize(run_id, started_at, False, steps, outputs, errors, cfg)
        return result

    # --- 2. Validation ---------------------------------------------------
    try:
        raw = load_file(erp_path)
        val_errors = validate_erp_dataframe(raw)
        if val_errors:
            raise ValueError(
                "Validation failed:\n" + "\n".join(val_errors[:10])
                + (f"\n(+{len(val_errors) - 10} more)" if len(val_errors) > 10 else "")
            )
        steps.append(_step(STEP_VALIDATED, "success", f"{len(raw)} SKUs validated"))
    except Exception as exc:
        msg = str(exc)
        steps.append(_step(STEP_VALIDATED, "error", msg))
        errors.append(msg)
        result = _finalize(run_id, started_at, False, steps, outputs, errors, cfg)
        return result

    # --- 3–6. Analytics pipeline -----------------------------------------
    try:
        analytics = run_analytics_pipeline(raw, cfg["forecast_method"])
        df = analytics["df"]
        steps.append(_step(
            STEP_INVENTORY, "success",
            f"{len(df)} SKUs · inventory €{analytics['kpis']['total_inventory_value']:,.0f} · "
            f"{analytics['kpis']['stockout_count']} stockout risks",
        ))
        steps.append(_step(
            STEP_FORECAST, "success",
            f"4-week forecast applied ({cfg['forecast_method']})",
        ))
        steps.append(_step(
            STEP_SUPPLIER, "success",
            f"{len(analytics['scorecard'])} suppliers scored · "
            f"{len(analytics['warnings'])} warnings",
        ))
    except Exception as exc:
        msg = str(exc)
        for name in (STEP_INVENTORY, STEP_FORECAST, STEP_SUPPLIER):
            if not any(s["name"] == name for s in steps):
                steps.append(_step(name, "error", msg))
        errors.append(msg)
        result = _finalize(run_id, started_at, False, steps, outputs, errors, cfg)
        return result

    # --- 7. Purchase CSV -------------------------------------------------
    try:
        rpa_orders = build_rpa_purchase_export(df)
        purchase_path = _resolve(cfg, "outbox_purchases_dir") / f"purchase_recommendations_{run_id}.csv"
        _write_purchase_csv(rpa_orders, purchase_path)
        outputs["purchase_recommendations"] = str(purchase_path)
        steps.append(_step(
            STEP_PURCHASES, "success",
            f"{len(rpa_orders)} lines → {purchase_path.name}",
        ))
    except Exception as exc:
        msg = str(exc)
        steps.append(_step(STEP_PURCHASES, "error", msg))
        errors.append(msg)

    # --- 8. Reports ------------------------------------------------------
    weekly_dir = _resolve(cfg, "reports_weekly_dir")
    weekly_dir.mkdir(parents=True, exist_ok=True)
    orders = analytics["orders"]
    slow = analytics["slow"]
    scorecard = analytics["scorecard"]
    warnings = analytics["warnings"]
    kpis = analytics["kpis"]
    recs = analytics["recs"]

    report_fi = generate_report(df, orders, slow, scorecard, warnings, kpis, "fi")

    pdf_path = weekly_dir / f"weekly_supply_chain_report_{run_id}.pdf"
    try:
        export_report_pdf(report_fi, pdf_path)
        outputs["pdf_report"] = str(pdf_path)
        steps.append(_step(STEP_PDF, "success", pdf_path.name))
    except Exception as exc:
        steps.append(_step(STEP_PDF, "warning", f"PDF failed: {exc}"))

    pptx_en_path = weekly_dir / f"weekly_supply_chain_report_EN_{run_id}.pptx"
    pptx_fi_path = weekly_dir / f"weekly_supply_chain_report_FI_{run_id}.pptx"
    pptx_ok = True
    try:
        export_weekly_deck(df, orders, slow, scorecard, kpis, language="en", output_path=pptx_en_path)
        outputs["pptx_report_en"] = str(pptx_en_path)
    except Exception as exc:
        pptx_ok = False
        steps.append(_step(STEP_PPTX, "warning", f"EN deck failed: {exc}"))
    try:
        export_weekly_deck(df, orders, slow, scorecard, kpis, language="fi", output_path=pptx_fi_path)
        outputs["pptx_report_fi"] = str(pptx_fi_path)
    except Exception as exc:
        pptx_ok = False
        if not any(s["name"] == STEP_PPTX for s in steps):
            steps.append(_step(STEP_PPTX, "warning", f"FI deck failed: {exc}"))
        else:
            steps[-1]["message"] += f"; FI deck failed: {exc}"
    if pptx_ok:
        steps.append(_step(STEP_PPTX, "success", f"{pptx_en_path.name}, {pptx_fi_path.name}"))

    # --- 9. Email draft (PDF + PowerPoint only) --------------------------
    attach_list = [
        outputs.get("pdf_report"),
        outputs.get("pptx_report_en"),
        outputs.get("pptx_report_fi"),
    ]
    email_path = _resolve(cfg, "outbox_email_dir") / f"weekly_supply_chain_email_{run_id}.html"
    try:
        _write_email_draft(
            email_path, run_id=run_id, kpis=kpis, recs=recs,
            attachments=[a for a in attach_list if a],
            language=cfg.get("email_language", "fi"),
        )
        outputs["email_draft"] = str(email_path)
        steps.append(_step(STEP_EMAIL, "success", email_path.name))
    except Exception as exc:
        steps.append(_step(STEP_EMAIL, "warning", str(exc)))

    # --- 10. Archive -----------------------------------------------------
    fatal = bool(errors)
    if not fatal and erp_path:
        try:
            archive_dir = _resolve(cfg, "reports_archive_dir") / run_id
            archive_dir.mkdir(parents=True, exist_ok=True)

            processed_name = f"{run_id}_{erp_path.name}"
            processed_dest = _resolve(cfg, "processed_dir") / processed_name
            shutil.copy2(erp_path, processed_dest)

            for key in (
                "pdf_report", "pptx_report_en", "pptx_report_fi",
                "purchase_recommendations", "email_draft",
            ):
                src = outputs.get(key)
                if src and Path(src).exists():
                    shutil.copy2(src, archive_dir / Path(src).name)

            steps.append(_step(
                STEP_ARCHIVE, "success",
                f"ERP -> processed/, {archive_dir.name}/ ({len(list(archive_dir.iterdir()))} files)",
            ))
        except Exception as exc:
            steps.append(_step(STEP_ARCHIVE, "warning", str(exc)))

    success = not fatal and any(s["status"] == "success" for s in steps)
    return _finalize(run_id, started_at, success, steps, outputs, errors, cfg)


def _finalize(
    run_id: str,
    started_at: str,
    success: bool,
    steps: list[dict],
    outputs: dict,
    errors: list[str],
    config: dict,
) -> dict:
    completed_at = datetime.now(timezone.utc).isoformat()
    result = {
        "success": success,
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "steps": steps,
        "outputs": outputs,
        "errors": errors,
    }
    erp_src = outputs.get("erp_source")
    if erp_src:
        p = Path(erp_src)
        if p.is_file():
            stat = p.stat()
            result["data_source_fingerprint"] = (
                f"{p.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
            )
    log_path = _save_run_log(result, config)
    result["outputs"]["workflow_log"] = str(log_path)
    return result
