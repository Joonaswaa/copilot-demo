"""
report_generator.py
-------------------
Generates the weekly supply chain management report in English and
Finnish, plus the "AI Copilot" recommendations shown on the dashboard.

Two generation paths:

  1. LLM path (optional): if an API key is configured in .env, the
     analysis results are summarised into a prompt and sent to an LLM
     (Anthropic Claude or OpenAI). See generate_report_llm() for the
     exact integration points.

  2. Rule-based fallback (default): a template-driven generator that
     produces a genuinely useful report from the computed analytics.
     The app is fully functional without any API key.

The rule-based report is not a dummy placeholder — it is the reference
output. The LLM path only improves fluency and adds narrative reasoning.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from src.kpi import high_risk_product_mask, stockout_mask
from src.llm_client import complete, is_llm_configured

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KPI computation shared by report + dashboard overview
# ---------------------------------------------------------------------------

def compute_kpis(df: pd.DataFrame, orders: pd.DataFrame,
                 slow: pd.DataFrame) -> dict:
    """Headline numbers used on the Overview page and in the report."""
    stockout_count = int(stockout_mask(df).sum())
    high_risk_count = int(high_risk_product_mask(df).sum())
    return {
        "total_inventory_value": float(
            (df["current_stock"] * df["unit_cost"]).sum()
        ),
        "sku_count": int(len(df)),
        "stockout_count": stockout_count,
        "high_risk_count": high_risk_count,
        # Backward-compatible aliases used in report templates.
        "stockout_flag_count": stockout_count,
        "delayed_deliveries": int((df["delivery_status"] == "Delayed").sum()),
        "recommended_purchase_value": float(orders["estimated_cost"].sum()) if not orders.empty else 0.0,
        "avg_on_time_rate": float(df["supplier_on_time_rate"].mean() * 100),
        "slow_mover_count": int(len(slow)),
        "slow_mover_capital": float(slow["tied_capital"].sum()) if not slow.empty else 0.0,
    }


# ---------------------------------------------------------------------------
# Copilot recommendations (top actions for the dashboard panel)
# ---------------------------------------------------------------------------

def copilot_recommendations(df: pd.DataFrame, orders: pd.DataFrame,
                            slow: pd.DataFrame, scorecard: pd.DataFrame,
                            warnings: list[str], top_n: int = 5) -> list[dict]:
    """
    Build the top recommended actions as a ranked list of dicts:
    {action, detail, kind, urgency}. Rule-based, fully explainable.
    """
    recs = []

    # 1. Urgent purchase orders.
    for _, row in orders[orders["priority"] == "Urgent"].head(3).iterrows():
        recs.append({
            "kind": "Purchase",
            "urgency": "Urgent",
            "action": (f"Order {int(row['recommended_qty'])} units of "
                       f"{row['product_name']} within "
                       f"{max(3, int(row['lead_time_days'] // 3))} days"),
            "detail": row["reason"] + f" Estimated cost €{row['estimated_cost']:,.0f}.",
        })

    # 2. Worst supplier warning.
    if not scorecard.empty and scorecard.iloc[0]["risk_level"] == "High":
        worst = scorecard.iloc[0]
        recs.append({
            "kind": "Supplier",
            "urgency": "High",
            "action": f"Review supplier {worst['supplier']}",
            "detail": (f"On-time rate {worst['on_time_rate']:.0f}%, average delay "
                       f"{worst['avg_delay_days']:.1f} days, "
                       f"{int(worst['delayed_deliveries'])} deliveries currently delayed. "
                       f"Affected: {worst['categories']}."),
        })

    # 3. Biggest slow mover.
    if not slow.empty:
        top_slow = slow.iloc[0]
        recs.append({
            "kind": "Inventory",
            "urgency": "Medium",
            "action": f"Move {top_slow['product_name']} to campaign planning",
            "detail": (f"€{top_slow['tied_capital']:,.0f} tied in excess stock, "
                       f"turnover {top_slow['stock_turnover_rate']:.1f}, "
                       f"cover {top_slow['weeks_of_cover']:.0f} weeks. "
                       + top_slow["suggested_action"]),
        })

    # 4. Critical products below safety level.
    below_safety = df[(df["current_stock"] < df["safety_stock"])
                      & (df["criticality_level"] == "critical")]
    for _, row in below_safety.head(2).iterrows():
        recs.append({
            "kind": "Stock",
            "urgency": "Urgent",
            "action": f"Prioritise {row['product_name']} — below safety stock",
            "detail": (f"Stock {int(row['current_stock'])} vs safety level "
                       f"{int(row['safety_stock'])}. Installation-critical item; "
                       "expedite the open order or use an alternate supplier."),
        })

    # 5. Demand surge heads-up.
    surging = df[(df["demand_trend_pct"] > 20) & (~df["stockout_flag"])]
    if not surging.empty:
        row = surging.sort_values("demand_trend_pct", ascending=False).iloc[0]
        recs.append({
            "kind": "Demand",
            "urgency": "Medium",
            "action": f"Watch {row['product_name']} — demand up {row['demand_trend_pct']:.0f}%",
            "detail": ("Four-week demand trend is rising sharply; verify the next "
                       "forecast cycle and supplier capacity before it becomes a stockout risk."),
        })

    urgency_rank = {"Urgent": 0, "High": 1, "Medium": 2}
    recs.sort(key=lambda r: urgency_rank.get(r["urgency"], 3))
    return recs[:top_n]


# ---------------------------------------------------------------------------
# Rule-based weekly report (default path)
# ---------------------------------------------------------------------------

def _fmt_eur(value: float) -> str:
    return f"€{value:,.0f}"


def generate_report_rule_based(df, orders, slow, scorecard, warnings,
                               kpis, language: str = "en") -> str:
    """Template-driven weekly report. `language` is 'en' or 'fi'."""
    stockouts = df[df["stockout_flag"]].sort_values("risk_score", ascending=False)
    top_risks = df.sort_values("risk_score", ascending=False).head(5)
    urgent_orders = orders[orders["priority"].isin(["Urgent", "High"])]
    today = date.today().isoformat()

    if language == "fi":
        return _report_fi(today, kpis, stockouts, top_risks, slow, warnings,
                          urgent_orders, orders)
    return _report_en(today, kpis, stockouts, top_risks, slow, warnings,
                      urgent_orders, orders)


def _report_en(today, k, stockouts, top_risks, slow, warnings,
               urgent_orders, orders) -> str:
    lines = [
        f"# Weekly Supply Chain Report — {today}",
        "",
        "## Executive summary",
        (f"Total inventory value is {_fmt_eur(k['total_inventory_value'])} across "
         f"{k['sku_count']} SKUs. {k['stockout_flag_count']} SKUs are below their "
         f"reorder point; {k['high_risk_count']} of those are high- or critical-impact "
         f"products. {k['delayed_deliveries']} inbound deliveries are currently delayed. "
         f"Recommended purchase orders total {_fmt_eur(k['recommended_purchase_value'])}. "
         f"Average supplier on-time delivery rate is {k['avg_on_time_rate']:.1f}%. "
         f"{k['slow_mover_count']} slow-moving products tie up approximately "
         f"{_fmt_eur(k['slow_mover_capital'])} of working capital."),
        "",
        "## Top supply chain risks",
    ]
    for _, r in top_risks.iterrows():
        lines.append(f"- {r['product_name']} ({r['sku']}): risk score "
                     f"{r['risk_score']:.0f}/100 ({r['risk_level']}), "
                     f"{r['weeks_of_cover']:.1f} weeks of cover, supplier "
                     f"on-time rate {r['supplier_on_time_rate']*100:.0f}%.")

    lines += ["", "## Products likely to run out"]
    if stockouts.empty:
        lines.append("No products are forecast to stock out within their lead time.")
    for _, r in stockouts.head(8).iterrows():
        lines.append(f"- {r['product_name']}: {int(r['current_stock'])} units on hand, "
                     f"~{r['weeks_of_cover']:.1f} weeks of cover vs "
                     f"{int(r['lead_time_days'])}-day lead time.")

    lines += ["", "## Slow-moving products"]
    if slow.empty:
        lines.append("No significant slow-moving inventory identified this week.")
    for _, r in slow.head(5).iterrows():
        lines.append(f"- {r['product_name']}: {_fmt_eur(r['tied_capital'])} tied in "
                     f"excess stock ({r['weeks_of_cover']:.0f} weeks of cover). "
                     f"{r['suggested_action']}")

    lines += ["", "## Supplier issues"]
    if not warnings:
        lines.append("All suppliers are performing within agreed service levels.")
    lines += [f"- {w}" for w in warnings[:5]]

    lines += ["", "## Recommended purchase orders"]
    if urgent_orders.empty:
        lines.append("No urgent purchase orders this week.")
    for _, r in urgent_orders.head(8).iterrows():
        lines.append(f"- [{r['priority']}] {r['product_name']}: order "
                     f"{int(r['recommended_qty'])} units from {r['supplier']} "
                     f"(~{_fmt_eur(r['estimated_cost'])}). {r['reason']}")

    lines += [
        "",
        "## Key KPIs",
        f"- Inventory value: {_fmt_eur(k['total_inventory_value'])}",
        f"- SKUs: {k['sku_count']} | Stockout risk: {k['stockout_flag_count']} | "
        f"High-risk (stockout + high/critical): {k['high_risk_count']}",
        f"- Delayed deliveries: {k['delayed_deliveries']}",
        f"- Avg supplier on-time rate: {k['avg_on_time_rate']:.1f}%",
        f"- Recommended purchases: {_fmt_eur(k['recommended_purchase_value'])} "
        f"({len(orders)} lines)",
        f"- Capital in slow movers: {_fmt_eur(k['slow_mover_capital'])}",
        "",
        "## Recommended management actions",
        "1. Approve the urgent purchase orders above to prevent stockouts of "
        "installation-critical items.",
        "2. Review the highest-risk supplier and agree a corrective action plan "
        "or activate an alternate source.",
        "3. Hand the top slow movers to campaign planning to release tied capital.",
        "4. Re-check safety stock levels for products with demand growth above 20%.",
    ]
    return "\n".join(lines)


def _report_fi(today, k, stockouts, top_risks, slow, warnings,
               urgent_orders, orders) -> str:
    lines = [
        f"# Viikoittainen toimitusketjuraportti — {today}",
        "",
        "## Tiivistelmä johdolle",
        (f"Varaston kokonaisarvo on {_fmt_eur(k['total_inventory_value'])} ja "
         f"nimikkeitä on {k['sku_count']}. {k['stockout_flag_count']} SKU:ta on "
         f"tilauspisteen alapuolella; {k['high_risk_count']} niistä on "
         f"korkean tai kriittisen vaikutuksen tuotteita. Myöhässä olevia saapuvia "
         f"toimituksia on {k['delayed_deliveries']}. Suositeltujen ostotilausten "
         f"arvo on yhteensä {_fmt_eur(k['recommended_purchase_value'])}. "
         f"Toimittajien keskimääräinen toimitusvarmuus on "
         f"{k['avg_on_time_rate']:.1f} %. Hitaasti kiertäviä tuotteita on "
         f"{k['slow_mover_count']}, ja niihin sitoutuu noin "
         f"{_fmt_eur(k['slow_mover_capital'])} käyttöpääomaa."),
        "",
        "## Suurimmat toimitusketjuriskit",
    ]
    for _, r in top_risks.iterrows():
        lines.append(f"- {r['product_name']} ({r['sku']}): riskipisteet "
                     f"{r['risk_score']:.0f}/100 ({r['risk_level']}), varasto riittää "
                     f"{r['weeks_of_cover']:.1f} viikoksi, toimittajan "
                     f"toimitusvarmuus {r['supplier_on_time_rate']*100:.0f} %.")

    lines += ["", "## Tuotteet, jotka uhkaavat loppua"]
    if stockouts.empty:
        lines.append("Yksikään tuote ei ennusteen mukaan lopu toimitusajan sisällä.")
    for _, r in stockouts.head(8).iterrows():
        lines.append(f"- {r['product_name']}: varastossa {int(r['current_stock'])} kpl, "
                     f"riittää n. {r['weeks_of_cover']:.1f} viikoksi, toimitusaika "
                     f"{int(r['lead_time_days'])} päivää.")

    lines += ["", "## Hitaasti kiertävät tuotteet"]
    if slow.empty:
        lines.append("Merkittävää hitaasti kiertävää varastoa ei tunnistettu tällä viikolla.")
    for _, r in slow.head(5).iterrows():
        lines.append(f"- {r['product_name']}: ylivarastoon sitoutunut "
                     f"{_fmt_eur(r['tied_capital'])} ({r['weeks_of_cover']:.0f} viikon "
                     f"riitto). Suositus: {r['suggested_action']}")

    lines += ["", "## Toimittajahavainnot"]
    if not warnings:
        lines.append("Kaikki toimittajat toimivat sovitulla palvelutasolla.")
    lines += [f"- {w}" for w in warnings[:5]]

    lines += ["", "## Suositellut ostotilaukset"]
    if urgent_orders.empty:
        lines.append("Kiireellisiä ostotilauksia ei ole tällä viikolla.")
    for _, r in urgent_orders.head(8).iterrows():
        lines.append(f"- [{r['priority']}] {r['product_name']}: tilaa "
                     f"{int(r['recommended_qty'])} kpl toimittajalta {r['supplier']} "
                     f"(n. {_fmt_eur(r['estimated_cost'])}).")

    lines += [
        "",
        "## Keskeiset tunnusluvut",
        f"- Varaston arvo: {_fmt_eur(k['total_inventory_value'])}",
        f"- Nimikkeet: {k['sku_count']} | Loppumisriski: {k['stockout_flag_count']} | "
        f"Korkea riski (loppumis + high/critical): {k['high_risk_count']}",
        f"- Myöhässä olevat toimitukset: {k['delayed_deliveries']}",
        f"- Toimittajien toimitusvarmuus keskimäärin: {k['avg_on_time_rate']:.1f} %",
        f"- Suositellut ostot: {_fmt_eur(k['recommended_purchase_value'])} "
        f"({len(orders)} riviä)",
        f"- Hitaasti kiertäviin sitoutunut pääoma: {_fmt_eur(k['slow_mover_capital'])}",
        "",
        "## Toimenpidesuositukset johdolle",
        "1. Hyväksy yllä listatut kiireelliset ostotilaukset asennuskriittisten "
        "tuotteiden saatavuuden turvaamiseksi.",
        "2. Käy korkeimman riskin toimittajan tilanne läpi ja sovi korjaavista "
        "toimenpiteistä tai aktivoi vaihtoehtoinen toimittaja.",
        "3. Siirrä suurimmat hitaasti kiertävät tuotteet kampanjasuunnitteluun "
        "sitoutuneen pääoman vapauttamiseksi.",
        "4. Tarkista varmuusvarastotasot tuotteille, joiden kysyntä on kasvanut "
        "yli 20 %.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM path (optional)
# ---------------------------------------------------------------------------

def generate_report_llm(df, orders, slow, scorecard, warnings, kpis,
                        language: str = "en") -> str | None:
    """
    Generate the report with an LLM if an API key is configured.
    Returns None if no key is set or the call fails, so the caller can
    fall back to the rule-based report.
    """
    if not is_llm_configured():
        return None

    base = generate_report_rule_based(df, orders, slow, scorecard, warnings,
                                      kpis, language)
    lang_name = "Finnish" if language == "fi" else "English"
    prompt = (
        f"You are a supply chain analyst at a telecom operator. Rewrite the "
        f"following weekly report in fluent, executive-ready {lang_name}. "
        f"Keep every number, currency amount, SKU code, and percentage exactly "
        f"as given. Keep the markdown section headings and bullet structure. "
        f"Add one short interpretive paragraph to the executive summary. "
        f"Do not invent products, suppliers, or metrics that are not in the "
        f"source text.\n\n{base}"
    )

    try:
        return complete(prompt)
    except Exception as exc:
        logger.warning("LLM report generation failed: %s", exc)
        return None


def generate_report(df, orders, slow, scorecard, warnings, kpis,
                    language: str = "en") -> tuple[str, str]:
    """
    Public entry point: try the LLM path, fall back to rule-based.

    Returns (report_text, generation_mode) where mode is 'llm' or 'rule_based'.
    """
    llm_report = generate_report_llm(df, orders, slow, scorecard, warnings,
                                     kpis, language)
    if llm_report:
        return llm_report, "llm"
    return generate_report_rule_based(
        df, orders, slow, scorecard, warnings, kpis, language
    ), "rule_based"
