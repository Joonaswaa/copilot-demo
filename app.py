"""
app.py
------
Telecom Supply Chain AI Copilot — Streamlit dashboard.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import shutil

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

from src.data_loader import DataValidationError, load_file, load_sample_data
from src.demand_forecasting import FORECAST_WEEKS
from src.kpi import stockout_mask
from src.report_generator import generate_report
from src.pdf_exporter import export_report_pdf
from src.pptx_exporter import export_weekly_deck
from src.email_sender import (
    get_recipients, is_configured as email_configured, send_report_email,
)
from src.rpa_workflow import (
    DEFAULT_CONFIG,
    ensure_workflow_dirs,
    find_latest_erp_export,
    load_recent_runs,
    run_analytics_pipeline,
    run_weekly_rpa_workflow,
)
from src.i18n import (
    PAGE_KEYS, PRIORITIES, RISK_LEVELS,
    kind_label, page_label, priority_label, risk_label, t, urgency_label,
)
from src.methodology_docs import get_methodology_sections

# ---------------------------------------------------------------------------
# Page setup & styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Supply Chain AI Copilot",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "lang" not in st.session_state:
    st.session_state.lang = "fi"

if "page" not in st.session_state:
    _init_page = st.query_params.get("page", PAGE_KEYS[0])
    st.session_state.page = _init_page if _init_page in PAGE_KEYS else PAGE_KEYS[0]

_query_page = st.query_params.get("page")
if _query_page in PAGE_KEYS:
    st.session_state.page = _query_page

_query_lang = st.query_params.get("lang")
if _query_lang in ("fi", "en"):
    st.session_state.lang = _query_lang

ELISA_BLUE = "#002CAC"
ELISA_BLUE_DARK = "#001F8C"
ELISA_BLUE_LIGHT = "#E8EEF8"
ACCENT = ELISA_BLUE
RISK_COLORS = {"Low": "#2E9E5B", "Medium": "#E3A008",
               "High": "#E8590C", "Critical": "#C92A2A"}
PRIORITY_COLORS = {"Urgent": "#C92A2A", "High": "#E8590C",
                   "Medium": "#E3A008", "Normal": "#2E9E5B"}


def txt(key: str, **kwargs) -> str:
    return t(key, st.session_state.lang, **kwargs)


st.markdown(
    f"""
    <style>
      div[data-testid="stMetricValue"] {{ font-size: 1.6rem; color: {ELISA_BLUE}; }}
      div[data-testid="stMetricLabel"] {{ color: #4A4A4A; }}
      h1, h2, h3 {{ color: {ELISA_BLUE}; }}
      .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
        color: {ELISA_BLUE};
        border-bottom-color: {ELISA_BLUE};
      }}
      .copilot-card {{
        border-left: 4px solid {ELISA_BLUE};
        background: {ELISA_BLUE_LIGHT};
        padding: 0.7rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.6rem;
      }}
      .copilot-urgent {{ border-left-color: #C92A2A; }}
      .copilot-high   {{ border-left-color: #E8590C; }}
      .copilot-medium {{ border-left-color: #E3A008; }}
      [data-testid="stSidebar"] [data-testid="stMarkdown"] p,
      [data-testid="stSidebar"] [data-testid="stMarkdown"] li {{
        color: #FFFFFF;
      }}
      [data-testid="stSidebar"] .stCaption {{
        color: rgba(255, 255, 255, 0.85);
      }}
      /* Desktop: sidebar always open, hide collapse controls */
      @media (min-width: 769px) {{
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="collapsedControl"] {{
          display: none !important;
        }}
        section[data-testid="stSidebar"] {{
          transform: none !important;
          visibility: visible !important;
        }}
      }}
      /* Hide Streamlit default header / toolbar (desktop) */
      @media (min-width: 769px) {{
        header[data-testid="stHeader"] {{
          display: none !important;
          height: 0 !important;
          visibility: hidden !important;
        }}
      }}
      [data-testid="stToolbar"] {{
        display: none !important;
      }}
      [data-testid="stDecoration"] {{
        display: none !important;
      }}
      #MainMenu {{
        visibility: hidden;
      }}
      footer {{
        visibility: hidden;
      }}
      .stApp [data-testid="stAppViewContainer"] > section.main {{
        padding-top: 0 !important;
      }}
      .stApp [data-testid="stAppViewContainer"] > section.main > div {{
        padding-top: 0 !important;
      }}
      .block-container {{
        padding-top: 0 !important;
        max-width: 100%;
      }}
      /* Apple-style top navigation bar */
      section.main div[data-testid="stVerticalBlockBorderWrapper"]:first-of-type,
      section.main div[data-testid="stVerticalBlock"]:first-of-type {{
        background: #fbfbfd;
        border-bottom: 1px solid #d2d2d7;
        margin: 0 -2rem 0.75rem -2rem;
        padding: 0.35rem 1.5rem 0.55rem;
        position: sticky;
        top: 0;
        z-index: 998;
      }}
      section.main div[data-testid="stVerticalBlock"]:first-of-type
        [data-testid="stHorizontalBlock"] {{
        align-items: center;
        flex-wrap: nowrap;
      }}
      section.main div[data-testid="stVerticalBlock"]:first-of-type
        [data-testid="stHorizontalBlock"] > div:first-child {{
        overflow-x: auto;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
      }}
      section.main div[data-testid="stVerticalBlock"]:first-of-type
        [data-testid="stHorizontalBlock"] > div:first-child
        [data-testid="stPills"] > div {{
        flex-wrap: nowrap !important;
        width: max-content;
        min-width: 100%;
      }}
      section.main div[data-testid="stVerticalBlock"]:first-of-type
        [data-testid="stBaseButton-pills"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #1d1d1f !important;
        font-size: 12px !important;
        font-weight: 400 !important;
        padding: 0.35rem 0.55rem !important;
        min-height: 0 !important;
        white-space: nowrap !important;
        flex-shrink: 0 !important;
      }}
      section.main div[data-testid="stVerticalBlock"]:first-of-type
        [data-testid="stBaseButton-pillsActive"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: {ELISA_BLUE} !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 0.35rem 0.55rem !important;
        min-height: 0 !important;
        white-space: nowrap !important;
      }}
      section.main div[data-testid="stVerticalBlock"]:first-of-type
        [data-testid="stBaseButton-pills"]:hover {{
        background: rgba(0, 0, 0, 0.04) !important;
      }}
      /* Mobile / narrow screens */
      @media (max-width: 768px) {{
        /* Header: no white bar — only host the sidebar toggle control */
        header[data-testid="stHeader"] {{
          position: fixed !important;
          top: 0 !important;
          left: 0 !important;
          width: 3.25rem !important;
          height: 3.25rem !important;
          min-height: 0 !important;
          visibility: visible !important;
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          pointer-events: none !important;
          overflow: visible !important;
          z-index: 9999 !important;
        }}
        header[data-testid="stHeader"] > div {{
          background: transparent !important;
          pointer-events: none !important;
        }}
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="collapsedControl"] {{
          display: flex !important;
          visibility: visible !important;
          opacity: 1 !important;
          pointer-events: auto !important;
          z-index: 10000 !important;
        }}
        [data-testid="collapsedControl"] {{
          position: fixed !important;
          top: 0.55rem !important;
          left: 0.55rem !important;
          background: {ELISA_BLUE} !important;
          color: #ffffff !important;
          border-radius: 8px !important;
          padding: 0.35rem 0.5rem !important;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18) !important;
        }}
        section[data-testid="stSidebar"] {{
          min-width: 0 !important;
        }}
        .stApp [data-testid="stAppViewContainer"] > section.main {{
          padding-top: 0 !important;
        }}
        .block-container {{
          padding-left: 0.75rem !important;
          padding-right: 0.75rem !important;
        }}
        section.main div[data-testid="stVerticalBlock"]:first-of-type {{
          margin: 0 -0.75rem 0.5rem -0.75rem;
          padding: 0.35rem 0.65rem 0.45rem 2.85rem;
          top: 0;
          z-index: 997;
        }}
        section.main div[data-testid="stVerticalBlock"]:first-of-type
          [data-testid="stHorizontalBlock"] {{
          flex-wrap: wrap !important;
          gap: 0.25rem;
        }}
        section.main div[data-testid="stVerticalBlock"]:first-of-type
          [data-testid="stHorizontalBlock"] > div:last-child {{
          flex: 0 0 auto !important;
          margin-left: auto;
        }}
        section.main div[data-testid="stVerticalBlock"]:first-of-type
          [data-testid="stHorizontalBlock"] > div:first-child {{
          flex: 1 1 100% !important;
          max-width: 100%;
        }}
        section.main div[data-testid="stVerticalBlock"]:first-of-type
          [data-testid="stBaseButton-pills"] {{
          font-size: 11px !important;
          padding: 0.3rem 0.45rem !important;
        }}
        section.main div[data-testid="stVerticalBlock"]:first-of-type
          [data-testid="stBaseButton-pillsActive"] {{
          font-size: 11px !important;
          padding: 0.3rem 0.45rem !important;
        }}
        div[data-testid="stMetricValue"] {{
          font-size: 1.25rem !important;
        }}
        h1 {{
          font-size: 1.45rem !important;
        }}
        h2, h3 {{
          font-size: 1.05rem !important;
        }}
        section.main [data-testid="stHorizontalBlock"]:not(
          div[data-testid="stVerticalBlock"]:first-of-type [data-testid="stHorizontalBlock"]
        ) {{
          flex-wrap: wrap !important;
        }}
        section.main [data-testid="column"] {{
          min-width: 100% !important;
          flex: 1 1 100% !important;
        }}
        section.main iframe {{
          max-height: 320px !important;
        }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Analysis pipeline
# ---------------------------------------------------------------------------

_PIPELINE_VERSION = 2
_REQUIRED_KPI_KEYS = frozenset({
    "stockout_count", "high_risk_count", "total_inventory_value",
    "sku_count", "delayed_deliveries", "avg_on_time_rate",
    "recommended_purchase_value",
})


@st.cache_data
def run_pipeline(raw: pd.DataFrame, forecast_method: str,
                 _pipeline_version: int = _PIPELINE_VERSION) -> dict:
    """Full analytics pipeline: clean -> forecast -> risk -> outputs."""
    return run_analytics_pipeline(raw, forecast_method)


def _nav_pills_key() -> str:
    return f"nav_pills_v3_{st.session_state.lang}"


def _apply_pending_nav() -> None:
    """Apply sidebar / programmatic navigation without blocking pill clicks."""
    pending = st.session_state.pop("_pending_page", None)
    if pending in PAGE_KEYS:
        st.session_state.page = pending
        st.session_state[_nav_pills_key()] = pending


def _ensure_nav_pills_init() -> None:
    """Seed pill widget once per language — do not overwrite user selections."""
    key = _nav_pills_key()
    if key not in st.session_state and st.session_state.page in PAGE_KEYS:
        st.session_state[key] = st.session_state.page


def _save_erp_export_for_automation(*, uploaded, use_sample: bool) -> str:
    """Persist the active dashboard dataset for the RPA workflow."""
    ensure_workflow_dirs()
    erp_dir = Path(DEFAULT_CONFIG["erp_exports_dir"])
    if uploaded is not None and not use_sample:
        export_path = erp_dir / uploaded.name
        export_path.write_bytes(uploaded.getvalue())
    else:
        sample_src = Path("data/sample_telecom_supply_chain_data.csv")
        export_path = erp_dir / sample_src.name
        shutil.copy2(sample_src, export_path)
    return str(export_path.resolve())


def _mark_data_source_changed(export_path: str) -> None:
    path = Path(export_path)
    stat = path.stat()
    fingerprint = f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
    if st.session_state.get("data_source_key") != fingerprint:
        st.session_state.pop("last_rpa_result", None)
    st.session_state["data_source_key"] = fingerprint
    st.session_state["erp_export_path"] = str(path.resolve())


# ---------------------------------------------------------------------------
# Top bar: Apple-style navigation (main area, first element)
# ---------------------------------------------------------------------------

def render_top_bar() -> str:
    """Apple-style pills nav + FI/EN language toggle (lang updates before nav labels)."""
    nav_col, lang_col = st.columns([11, 1.2], vertical_alignment="center")

    # Render language first so navigation labels use the new language immediately.
    with lang_col:
        selected_lang = st.pills(
            "language",
            ["fi", "en"],
            default=st.session_state.lang,
            format_func=lambda code: code.upper(),
            label_visibility="collapsed",
            key="topbar_lang",
        )
        if selected_lang in ("fi", "en") and selected_lang != st.session_state.lang:
            st.session_state.lang = selected_lang
            st.rerun()
        elif selected_lang in ("fi", "en"):
            st.session_state.lang = selected_lang

    with nav_col:
        _apply_pending_nav()
        _ensure_nav_pills_init()
        selected_page = st.pills(
            "navigation",
            PAGE_KEYS,
            format_func=lambda k: page_label(k, st.session_state.lang),
            label_visibility="collapsed",
            key=_nav_pills_key(),
        )
        if selected_page and selected_page in PAGE_KEYS:
            st.session_state.page = selected_page

    return st.session_state.page


page = render_top_bar()


# ---------------------------------------------------------------------------
# Sidebar: data input
# ---------------------------------------------------------------------------

st.sidebar.title(txt("app_title"))
st.sidebar.caption(txt("app_caption"))

uploaded = st.sidebar.file_uploader(txt("upload_erp"), type=["csv", "xlsx", "xls"])
use_sample = st.sidebar.checkbox(txt("use_sample"), value=uploaded is None)

forecast_method = st.sidebar.selectbox(
    txt("forecast_method"),
    options=["exponential", "moving_average", "ml"],
    format_func=lambda m: {
        "exponential": txt("forecast_exponential"),
        "moving_average": txt("forecast_moving_average"),
        "ml": txt("forecast_ml"),
    }[m],
)

run_clicked = st.sidebar.button(txt("run_analysis"), type="primary", width="stretch")

if st.sidebar.button(txt("page_automation"), width="stretch"):
    st.session_state._pending_page = "automation"
    st.rerun()

if st.sidebar.button(page_label("info"), width="stretch"):
    st.session_state._pending_page = "info"
    st.rerun()

_stale_results = (
    "results" in st.session_state
    and not _REQUIRED_KPI_KEYS.issubset(
        st.session_state["results"].get("kpis", {})
    )
)

if run_clicked or "results" not in st.session_state or _stale_results:
    try:
        with st.spinner(txt("analysis_running")):
            if uploaded is not None and not use_sample:
                export_path = _save_erp_export_for_automation(
                    uploaded=uploaded, use_sample=False,
                )
                raw = load_file(export_path)
                source_label = uploaded.name
            else:
                export_path = _save_erp_export_for_automation(
                    uploaded=None, use_sample=True,
                )
                raw = load_sample_data()
                source_label = "sample_telecom_supply_chain_data.csv"
            _mark_data_source_changed(export_path)
            st.session_state["results"] = run_pipeline(raw, forecast_method)
            st.session_state["source"] = source_label
    except DataValidationError as err:
        st.sidebar.error(str(err))
        st.stop()

results = st.session_state["results"]
df, orders, slow = results["df"], results["orders"], results["slow"]
scorecard, warnings = results["scorecard"], results["warnings"]
kpis, recs = results["kpis"], results["recs"]

st.sidebar.success(txt("data_source", source=st.session_state["source"]))


# ---------------------------------------------------------------------------
# Shared: AI Copilot panel
# ---------------------------------------------------------------------------

def render_copilot_panel():
    st.subheader(txt("copilot_title"))
    st.caption(txt("copilot_caption"))
    lang = st.session_state.lang
    for rec in recs:
        css = {"Urgent": "copilot-urgent", "High": "copilot-high",
               "Medium": "copilot-medium"}.get(rec["urgency"], "")
        urg = urgency_label(rec["urgency"], lang)
        kind = kind_label(rec["kind"], lang)
        st.markdown(
            f"""<div class="copilot-card {css}">
                <strong>[{urg} · {kind}]</strong> {rec['action']}<br>
                <span style="color:#444">{rec['detail']}</span>
                </div>""",
            unsafe_allow_html=True,
        )
    if warnings:
        with st.expander(txt("supplier_warnings", count=len(warnings))):
            for w in warnings:
                st.markdown(f"- {w}")


def _risk_labels(series: pd.Series) -> pd.Series:
    lang = st.session_state.lang
    return series.map(lambda lvl: risk_label(lvl, lang))


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_overview():
    st.title(txt("overview_title"))

    c1, c2, c3 = st.columns(3)
    c1.metric(txt("metric_inventory_value"), f"€{kpis['total_inventory_value']:,.0f}")
    c2.metric(txt("metric_skus"), kpis["sku_count"])
    c3.metric(txt("metric_stockout"), kpis["stockout_count"],
              help=txt("metric_stockout_help"))

    c4, c5, c6 = st.columns(3)
    c4.metric(txt("metric_high_risk"), kpis["high_risk_count"],
              help=txt("metric_high_risk_help"))
    c5.metric(txt("metric_delayed"), kpis["delayed_deliveries"])
    c6.metric(txt("metric_on_time"), f"{kpis['avg_on_time_rate']:.1f}%")

    c7, _, _ = st.columns(3)
    c7.metric(txt("metric_purchase_value"),
              f"€{kpis['recommended_purchase_value']:,.0f}")

    with st.expander(txt("debug_risk_table"), expanded=False):
        debug_cols = [
            "sku", "product_name", "current_stock", "reorder_point",
            "safety_stock", "monthly_demand", "criticality_level",
            "delivery_status",
        ]
        risk_rows = df.loc[stockout_mask(df), debug_cols].sort_values(
            ["criticality_level", "current_stock"]
        )
        st.dataframe(risk_rows, width="stretch", hide_index=True)
        st.caption(
            f"{txt('metric_stockout')}: {kpis['stockout_count']} · "
            f"{txt('metric_high_risk')}: {kpis['high_risk_count']}"
        )

    st.divider()
    render_copilot_panel()
    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        by_cat = df.groupby("category", as_index=False)["inventory_value"].sum()
        fig = px.bar(by_cat, x="inventory_value", y="category", orientation="h",
                     title=txt("chart_inventory_by_category"),
                     labels={"inventory_value": txt("chart_inventory_value_eur"),
                             "category": ""},
                     color_discrete_sequence=[ACCENT])
        st.plotly_chart(fig, width="stretch")
    with col_b:
        risk_counts = df["risk_level"].value_counts().reindex(RISK_LEVELS).fillna(0)
        risk_counts = risk_counts.reset_index()
        risk_counts.columns = ["risk_level", "count"]
        risk_counts["label"] = _risk_labels(risk_counts["risk_level"])
        fig = px.pie(risk_counts, values="count", names="label", hole=0.55,
                     title=txt("chart_risk_distribution"),
                     color="risk_level", color_discrete_map=RISK_COLORS)
        st.plotly_chart(fig, width="stretch")


def page_inventory_risk():
    st.title(txt("inventory_risk_title"))
    st.caption(txt("inventory_risk_caption"))

    min_score = st.slider(txt("min_risk_score"), 0, 100, 50)
    risky = df[df["risk_score"] >= min_score].sort_values(
        "risk_score", ascending=False)

    fig = px.scatter(
        risky, x="weeks_of_cover", y="risk_score", color="risk_level",
        size="inventory_value", hover_name="product_name",
        color_discrete_map=RISK_COLORS,
        labels={"weeks_of_cover": txt("weeks_of_cover"),
                "risk_score": txt("risk_score")},
        title=txt("chart_risk_vs_cover"),
    )
    fig.update_xaxes(range=[0, min(30, risky["weeks_of_cover"].max() + 2)])
    st.plotly_chart(fig, width="stretch")

    st.subheader(txt("critical_list", count=len(risky)))
    table = risky[[
        "sku", "product_name", "category", "current_stock", "reorder_point",
        "weeks_of_cover", "lead_time_days", "risk_score", "risk_level",
        "stockout_flag",
    ]].rename(columns={"stockout_flag": txt("col_stockout_risk")})
    st.dataframe(
        table, width="stretch", hide_index=True,
        column_config={
            "risk_score": st.column_config.ProgressColumn(
                txt("risk_score"), min_value=0, max_value=100, format="%.0f"),
        },
    )

    flagged = df[df["stockout_flag"]]
    if not flagged.empty:
        st.subheader(txt("reorder_flagged"))
        merged = flagged.merge(
            orders[["sku", "recommended_qty", "estimated_cost", "priority"]],
            on="sku", how="left",
        )
        st.dataframe(
            merged[["product_name", "current_stock", "safety_stock",
                    "recommended_qty", "estimated_cost", "priority"]],
            width="stretch", hide_index=True,
        )


def page_demand_forecast():
    method_label = {
        "exponential": txt("forecast_exponential"),
        "moving_average": txt("forecast_moving_average"),
        "ml": txt("forecast_ml"),
    }[forecast_method]
    st.title(txt("demand_forecast_title"))
    st.caption(txt("demand_forecast_caption",
                   weeks=len(df["demand_history_list"].iloc[0]),
                   forecast=FORECAST_WEEKS,
                   method=method_label))

    col1, col2 = st.columns(2)
    categories = [txt("all_categories")] + sorted(df["category"].unique())
    category = col1.selectbox(txt("category"), categories)
    pool = df if category == txt("all_categories") else df[df["category"] == category]
    product = col2.selectbox(txt("product"), pool["product_name"].unique())

    row = pool[pool["product_name"] == product].iloc[0]
    history = row["demand_history_list"]
    forecast = row["forecast_list"]

    weeks_hist = list(range(-len(history) + 1, 1))
    weeks_fc = list(range(1, len(forecast) + 1))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=weeks_hist, y=history, mode="lines+markers",
                             name=txt("historical_demand"),
                             line=dict(color=ACCENT)))
    fig.add_trace(go.Scatter(x=[0] + weeks_fc, y=[history[-1]] + forecast,
                             mode="lines+markers", name=txt("forecast"),
                             line=dict(color="#4D7FEE", dash="dash")))
    fig.add_hline(y=row["safety_stock"] / max(row["lead_time_days"] / 7, 1),
                  line_dash="dot", line_color="#999",
                  annotation_text=txt("weekly_safety"))
    fig.update_layout(title=txt("chart_demand_title", product=product),
                      xaxis_title=txt("week_axis"), yaxis_title=txt("units"))
    st.plotly_chart(fig, width="stretch")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(txt("forecast_4wk"), f"{row['forecast_4wk_total']:.0f}")
    m2.metric(txt("demand_trend"), f"{row['demand_trend_pct']:+.1f}%")
    m3.metric(txt("volatility"), f"{row['demand_volatility']:.2f}")
    m4.metric(txt("weeks_cover"), f"{row['weeks_of_cover']:.1f}")

    st.subheader(txt("forecast_table"))
    fc_table = pool[["sku", "product_name", "monthly_demand",
                     "forecasted_demand_next_4_weeks", "forecast_4wk_total",
                     "demand_trend_pct"]].sort_values(
        "forecast_4wk_total", ascending=False)
    st.dataframe(fc_table, width="stretch", hide_index=True)


def page_suppliers():
    st.title(txt("supplier_title"))

    fig = px.bar(
        scorecard.sort_values("on_time_rate"),
        x="on_time_rate", y="supplier", orientation="h",
        color="risk_level", color_discrete_map=RISK_COLORS,
        labels={"on_time_rate": txt("on_time_pct"), "supplier": ""},
        title=txt("chart_supplier_on_time"),
    )
    fig.add_vline(x=90, line_dash="dot", line_color="#999",
                  annotation_text=txt("target_90"))
    st.plotly_chart(fig, width="stretch")

    st.subheader(txt("supplier_scorecard"))
    st.dataframe(
        scorecard.rename(columns={
            "on_time_rate": txt("col_on_time"),
            "avg_delay_days": txt("col_avg_delay"),
            "delayed_deliveries": txt("col_delayed_now"),
            "inventory_value": txt("col_inventory_eur"),
            "supplier_risk_score": txt("col_risk_score"),
        }),
        width="stretch", hide_index=True,
        column_config={
            txt("col_risk_score"): st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.0f"),
        },
    )

    if warnings:
        st.subheader(txt("active_warnings"))
        for w in warnings:
            st.warning(w)


def page_slow_movers():
    st.title(txt("slow_movers_title"))

    if slow.empty:
        st.success(txt("no_slow_movers"))
        return

    total_capital = slow["tied_capital"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric(txt("slow_sku_count"), len(slow))
    c2.metric(txt("tied_capital"), f"€{total_capital:,.0f}")
    c3.metric(txt("largest_item"), f"€{slow['tied_capital'].max():,.0f}")

    fig = px.bar(slow.head(12), x="tied_capital", y="product_name",
                 orientation="h", color="weeks_of_cover",
                 color_continuous_scale="Blues",
                 labels={"tied_capital": txt("tied_capital_eur"),
                         "product_name": "",
                         "weeks_of_cover": txt("weeks_cover_short")},
                 title=txt("chart_slow_capital"))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    st.subheader(txt("slow_actions"))
    st.dataframe(slow, width="stretch", hide_index=True)


def page_purchases():
    st.title(txt("purchases_title"))

    if orders.empty:
        st.success(txt("no_replenishment"))
        return

    c1, c2, c3 = st.columns(3)
    c1.metric(txt("order_lines"), len(orders))
    c2.metric(txt("total_cost"), f"€{orders['estimated_cost'].sum():,.0f}")
    c3.metric(txt("urgent_lines"), int((orders["priority"] == "Urgent").sum()))

    fig = px.bar(
        orders.groupby("priority", as_index=False)["estimated_cost"].sum(),
        x="priority", y="estimated_cost", color="priority",
        color_discrete_map=PRIORITY_COLORS,
        category_orders={"priority": PRIORITIES},
        labels={"estimated_cost": txt("estimated_cost_eur")},
        title=txt("chart_purchase_by_priority"),
    )
    st.plotly_chart(fig, width="stretch")

    priority_filter = st.multiselect(
        txt("filter_priority"), PRIORITIES,
        default=["Urgent", "High"],
        format_func=lambda p: priority_label(p, st.session_state.lang),
    )
    view = orders[orders["priority"].isin(priority_filter)] if priority_filter else orders
    st.dataframe(view, width="stretch", hide_index=True)

    st.download_button(
        txt("download_purchase_csv"),
        orders.to_csv(index=False).encode("utf-8"),
        file_name="purchase_proposal.csv", mime="text/csv",
    )


def page_report():
    st.title(txt("report_title"))
    st.caption(txt("report_caption"))

    report_en = generate_report(df, orders, slow, scorecard, warnings, kpis, "en")
    report_fi = generate_report(df, orders, slow, scorecard, warnings, kpis, "fi")

    if st.session_state.lang == "fi":
        tab_primary, tab_secondary = st.tabs([txt("tab_finnish"), txt("tab_english")])
        with tab_primary:
            st.markdown(report_fi)
        with tab_secondary:
            st.markdown(report_en)
        primary_report = report_fi
    else:
        tab_primary, tab_secondary = st.tabs([txt("tab_english"), txt("tab_finnish")])
        with tab_primary:
            st.markdown(report_en)
        with tab_secondary:
            st.markdown(report_fi)
        primary_report = report_en

    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.download_button(txt("download_report_en"), report_en,
                         file_name="weekly_report_en.md")
    col2.download_button(txt("download_report_fi"), report_fi,
                         file_name="weekly_report_fi.md")

    if col3.button(txt("create_pdf")):
        path = export_report_pdf(primary_report)
        st.session_state["pdf_path"] = str(path)
        st.success(txt("pdf_created", path=path))
    if "pdf_path" in st.session_state:
        with open(st.session_state["pdf_path"], "rb") as fh:
            col3.download_button(txt("download_pdf"), fh.read(),
                                 file_name="weekly_report.pdf",
                                 mime="application/pdf")

    if col4.button(txt("create_pptx")):
        with st.spinner(txt("analysis_running")):
            path_en = export_weekly_deck(
                df, orders, slow, scorecard, kpis, language="en",
            )
            path_fi = export_weekly_deck(
                df, orders, slow, scorecard, kpis, language="fi",
            )
        st.session_state["pptx_path_en"] = str(path_en)
        st.session_state["pptx_path_fi"] = str(path_fi)
        st.success(txt("pptx_created", path=path_en))

    if "pptx_path_en" in st.session_state:
        with open(st.session_state["pptx_path_en"], "rb") as fh:
            col4.download_button(txt("download_pptx_en"), fh.read(),
                                 file_name="weekly_deck_en.pptx",
                                 mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    if "pptx_path_fi" in st.session_state:
        with open(st.session_state["pptx_path_fi"], "rb") as fh:
            col5.download_button(txt("download_pptx_fi"), fh.read(),
                                 file_name="weekly_deck_fi.pptx",
                                 mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")

    st.divider()
    st.subheader(txt("email_section"))

    if email_configured():
        st.caption(txt("email_recipients", recipients=", ".join(get_recipients())))
        st.caption(txt("email_attachments"))

    mail_col, _ = st.columns([1, 3])
    if mail_col.button(txt("send_email"), type="primary", disabled=not email_configured()):
        with st.spinner(txt("email_sending")):
            lang = st.session_state.lang
            pdf_path = st.session_state.get("pdf_path")
            if not pdf_path:
                pdf_path = str(export_report_pdf(primary_report))
                st.session_state["pdf_path"] = pdf_path

            pptx_en = st.session_state.get("pptx_path_en")
            pptx_fi = st.session_state.get("pptx_path_fi")
            if not pptx_en or not pptx_fi:
                pptx_en = str(export_weekly_deck(
                    df, orders, slow, scorecard, kpis, language="en",
                ))
                pptx_fi = str(export_weekly_deck(
                    df, orders, slow, scorecard, kpis, language="fi",
                ))
                st.session_state["pptx_path_en"] = pptx_en
                st.session_state["pptx_path_fi"] = pptx_fi

            ok, status = send_report_email(
                primary_report, kpis,
                pdf_path=pdf_path,
                pptx_path_en=pptx_en,
                pptx_path_fi=pptx_fi,
                language=lang,
            )
        (st.success if ok else st.error)(status)

    if not email_configured():
        st.info(txt("email_not_configured"))


def _step_icon(status: str) -> str:
    return {"success": "[OK]", "warning": "[!]", "error": "[X]"}.get(status, "[?]")


def page_automation():
    st.title(txt("automation_title"))
    st.caption(txt("automation_caption"))
    st.markdown(txt("automation_erp_folder"))

    ensure_workflow_dirs()
    active_path = st.session_state.get("erp_export_path")
    if active_path and Path(active_path).exists():
        active_name = Path(active_path).name
        st.success(txt("automation_active_source", source=active_name))
    elif uploaded is not None and not use_sample:
        st.info(txt("automation_run_analysis_hint"))
        active_path = None
    else:
        erp_dir = Path(DEFAULT_CONFIG["erp_exports_dir"])
        try:
            latest = find_latest_erp_export(erp_dir)
            active_path = str(latest.resolve())
            st.info(f"{latest.name} ({latest.stat().st_size // 1024} KB)")
        except FileNotFoundError as exc:
            st.warning(str(exc))
            active_path = None

    workflow_cfg = {
        "forecast_method": forecast_method,
        "email_language": st.session_state.lang,
    }
    if active_path:
        workflow_cfg["erp_path"] = active_path

    if st.button(txt("automation_run"), type="primary"):
        with st.status(txt("automation_running"), expanded=True) as status_box:
            result = run_weekly_rpa_workflow(workflow_cfg)
            for step in result["steps"]:
                icon = _step_icon(step["status"])
                st.write(f"{icon} **{step['name']}** — {step['message']}")
            if result["success"]:
                status_box.update(label=txt("automation_status_success"), state="complete")
            elif result["errors"]:
                status_box.update(label=txt("automation_status_error"), state="error")
            else:
                status_box.update(label=txt("automation_status_warning"), state="error")
        st.session_state["last_rpa_result"] = result

    result = st.session_state.get("last_rpa_result")
    current_fingerprint = st.session_state.get("data_source_key")
    if (
        result
        and current_fingerprint
        and result.get("data_source_fingerprint")
        and result["data_source_fingerprint"] != current_fingerprint
    ):
        st.warning(txt("automation_stale_warning"))
        result = None

    recent = load_recent_runs(limit=5)

    if recent:
        last = recent[0]
        when = last.get("completed_at", last.get("started_at", ""))[:19].replace("T", " ")
        st.caption(txt("automation_last_run", when=when))

    if result:
        st.subheader(txt("automation_steps"))
        for step in result["steps"]:
            label = txt(f"automation_status_{step['status']}")
            st.markdown(
                f"**{_step_icon(step['status'])} {step['name']}** ({label})  \n"
                f"{step.get('message', '')}"
            )

        outputs = result.get("outputs", {})
        email_path = outputs.get("email_draft")
        if email_path and Path(email_path).exists():
            st.subheader(txt("automation_email_preview"))
            st.caption(Path(email_path).name)
            draft_html = Path(email_path).read_text(encoding="utf-8")
            st.components.v1.html(draft_html, height=420, scrolling=True)
            with open(email_path, "rb") as fh:
                st.download_button(
                    txt("automation_email_download"),
                    fh.read(),
                    file_name=Path(email_path).name,
                    mime="text/html",
                    key=f"dl_email_{result['run_id']}",
                )

        st.subheader(txt("automation_forward"))
        forward_keys = {
            "pdf_report": txt("automation_fwd_pdf"),
            "pptx_report_en": txt("automation_fwd_pptx_en"),
            "pptx_report_fi": txt("automation_fwd_pptx_fi"),
        }
        cols = st.columns(3)
        for i, (key, label) in enumerate(forward_keys.items()):
            path = outputs.get(key)
            if path and Path(path).exists():
                with cols[i]:
                    st.markdown(f"**{label}**")
                    st.caption(Path(path).name)
                    with open(path, "rb") as fh:
                        st.download_button(
                            txt("automation_download"),
                            fh.read(),
                            file_name=Path(path).name,
                            key=f"dl_fwd_{key}_{result['run_id']}",
                        )

        with st.expander(txt("automation_internal")):
            internal_labels = {
                "erp_source": "ERP source",
                "purchase_recommendations": "Purchase CSV",
                "workflow_log": "Workflow log (JSON)",
            }
            for key, label in internal_labels.items():
                path = outputs.get(key)
                if path and Path(path).exists():
                    col_a, col_b = st.columns([3, 1])
                    col_a.text(str(path))
                    with open(path, "rb") as fh:
                        col_b.download_button(
                            txt("automation_download"),
                            fh.read(),
                            file_name=Path(path).name,
                            key=f"dl_int_{key}_{result['run_id']}",
                        )

        with st.expander(txt("automation_debug")):
            st.json(result)

    st.subheader(txt("automation_recent"))
    if not recent:
        st.write(txt("automation_no_runs"))
    else:
        for run in recent:
            status = txt("automation_status_success") if run.get("success") else txt("automation_status_error")
            st.markdown(
                f"**{run['run_id']}** — {status} — "
                f"{run.get('completed_at', '')[:19].replace('T', ' ')}"
            )


def page_info():
    st.title(txt("info_title"))
    st.caption(txt("info_caption"))

    sections = get_methodology_sections(st.session_state.lang)
    tab_labels = [label for label, _ in sections]
    tabs = st.tabs(tab_labels)
    for tab, (_, content) in zip(tabs, sections):
        with tab:
            st.markdown(content)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

PAGES = {
    "overview": page_overview,
    "inventory_risk": page_inventory_risk,
    "demand_forecast": page_demand_forecast,
    "suppliers": page_suppliers,
    "slow_movers": page_slow_movers,
    "purchases": page_purchases,
    "report": page_report,
    "automation": page_automation,
    "info": page_info,
}
PAGES[page]()
