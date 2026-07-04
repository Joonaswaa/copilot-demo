# 📡 Telecom Supply Chain AI Copilot

An AI-assisted supply chain decision-support application for telecom logistics.
Upload an ERP inventory export, press one button, and get demand forecasts,
stockout risk detection, supplier scorecards, purchase recommendations and a
bilingual (EN/FI) weekly management report — all in an interactive dashboard.

> **Note:** All data in this project is synthetic. It is designed to *look*
> like the supply chain of a Nordic telecom operator (devices, network
> equipment, accessories, refurbished stock, installation parts), but no real
> company data is used.

---

## Business problem

A telecom operator's logistics team manages thousands of SKUs across very
different product worlds: flagship phones with volatile demand, fiber modems
that block customer installations when they run out, low-value accessories,
and a growing refurbished flow. In practice the weekly routine often looks
like this:

- someone exports inventory data from the ERP into Excel,
- analyses it manually with filters and pivot tables,
- and writes a status summary for management by hand.

This is slow, error-prone, and reactive: stockouts of installation-critical
items are noticed too late, capital quietly accumulates in slow movers, and
supplier performance problems only surface once deliveries are already late.

## Solution overview

This application automates that weekly routine end-to-end:

```
ERP export → CSV/Excel upload → automated analysis → AI insights
          → interactive dashboard → weekly management report → (email)
```

The analytics are intentionally **simple and explainable** — moving averages,
exponential smoothing, weighted risk scores with visible weights — because in
supply chain work a recommendation the buyer can't explain to a category
manager doesn't get acted on. An LLM integration point is included for
turning the numbers into fluent narrative reports.

## Key features

| # | Feature | What it does |
|---|---------|--------------|
| 1 | **Inventory analysis** | Cleans and validates the ERP export, computes value, cover and turnover per SKU |
| 2 | **Demand forecasting** | 4-week forecast per SKU (Holt exponential smoothing / moving average, ML placeholder) |
| 3 | **Stockout risk detection** | Compares weeks of cover against supplier lead time + safety stock |
| 4 | **Slow-mover detection** | Flags low-turnover, over-stocked, declining-demand SKUs and quantifies tied capital |
| 5 | **Supplier scorecard** | On-time rate, average delay, open delayed deliveries, risk level per supplier |
| 6 | **Purchase recommendations** | Order-up-to replenishment with priorities, costs and plain-language reasons |
| 7 | **Composite risk scoring** | 0–100 score from stockout, supplier, volatility, criticality, lead time, margin & returns |
| 8 | **AI weekly report** | Management report in **English and Finnish**, exportable as Markdown or PDF, optional email |
| 9 | **AI Copilot panel** | Top 5 ranked actions in plain language (orders to place, suppliers to review, stock to campaign) |

## Screenshots

*(placeholder — add screenshots after running the app locally)*

| Overview & AI Copilot | Demand forecast | Supplier performance |
|---|---|---|
| `docs/screenshot_overview.png` | `docs/screenshot_forecast.png` | `docs/screenshot_suppliers.png` |

## Tech stack

- **Python 3.10+**
- **pandas / numpy** — data processing and analytics
- **Streamlit** — dashboard UI
- **Plotly** — interactive charts
- **openpyxl** — Excel file support
- **fpdf2** — PDF report export
- **smtplib + python-dotenv** — optional email sending and configuration
- **scikit-learn** *(optional)* — placeholder slot for an ML forecaster
- **Anthropic / OpenAI SDK** *(optional)* — LLM-generated narrative reports

## Folder structure

```
telecom_supply_chain_ai_copilot/
├── app.py                     # Streamlit dashboard (7 pages + Copilot panel)
├── requirements.txt
├── README.md
├── .env.example               # config template (LLM keys, SMTP) — optional
├── data/
│   └── sample_telecom_supply_chain_data.csv
├── outputs/
│   └── reports/               # generated PDF reports land here
└── src/
    ├── data_generator.py      # synthetic ERP export generator
    ├── data_loader.py         # CSV/Excel loading + column validation
    ├── data_cleaning.py       # type coercion, defaults, normalisation
    ├── demand_forecasting.py  # moving average / Holt smoothing / ML slot
    ├── risk_scoring.py        # weighted 0–100 composite risk score
    ├── replenishment.py       # order-up-to purchase recommendations
    ├── supplier_analysis.py   # supplier scorecard and warnings
    ├── slow_moving_analysis.py# tied-capital / slow-mover detection
    ├── report_generator.py    # EN/FI weekly report (rule-based + LLM hook)
    ├── pdf_exporter.py        # markdown report -> PDF
    └── email_sender.py        # optional SMTP sending
```

## How to run locally

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd telecom_supply_chain_ai_copilot

# 2. (Recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`, loads the bundled sample data
automatically, and everything works **without any API keys**. To regenerate
the sample dataset: `python -m src.data_generator`.

Optional configuration: copy `.env.example` to `.env` and fill in an LLM API
key (nicer report language) and/or SMTP settings (email sending).

## Example use case

Monday morning, logistics trainee at a telecom operator:

1. Export current inventory and open-PO data from the ERP to Excel.
2. Upload the file in the sidebar and click **Run analysis**.
3. The **AI Copilot** immediately shows: *"Order 320 units of Fiber Modem
   XG-2000 within 7 days — stock covers 1.4 weeks but lead time is 18 days;
   product is installation-critical."*
4. Check the **Supplier performance** page: one supplier's on-time rate has
   dropped below 85% with three deliveries currently delayed — flag it for
   the sourcing team.
5. Open the **AI weekly report** page, export the Finnish version as PDF and
   email it to the logistics manager. Total time: minutes, not hours.

## What this project demonstrates

- **Supply chain analytics** — coverage, turnover, safety stock, reorder
  points, order-up-to replenishment, ABC-style prioritisation by criticality
- **Telecom logistics understanding** — realistic product portfolio, the
  special role of installation-critical items (modems, SIMs, fiber parts),
  refurbished/returns flows
- **AI-assisted decision support** — explainable analytics feeding a
  natural-language Copilot and report layer, with a grounded LLM hook
- **ERP export automation** — turning a manual Excel routine into a
  one-click pipeline with validation and cleaning
- **Inventory optimization** — stockout prevention and tied-capital release
  treated as two sides of the same balance
- **Supplier performance analysis** — measurable service levels tied to
  business impact
- **Management reporting automation** — bilingual report generation, PDF
  export and email distribution

## Packaging as a Windows .exe

Streamlit apps are servers, so packaging needs a small launcher. One proven
approach with **PyInstaller**:

1. Create `run_app.py`:

   ```python
   import sys
   from streamlit.web import cli as stcli

   if __name__ == "__main__":
       sys.argv = ["streamlit", "run", "app.py",
                   "--global.developmentMode=false"]
       sys.exit(stcli.main())
   ```

2. Build:

   ```bash
   pip install pyinstaller
   pyinstaller --onefile --additional-hooks-dir=./hooks \
       --add-data "app.py;." --add-data "src;src" --add-data "data;data" \
       run_app.py
   ```

   (Streamlit needs a small PyInstaller hook to collect its metadata; see the
   Streamlit community guide on PyInstaller packaging.)

3. Distribute `dist/run_app.exe` — double-clicking it starts the local server
   and opens the dashboard in the browser.

Alternatives worth considering: **Nuitka** (faster binaries), a **Docker**
image for internal server deployment, or **Streamlit Community Cloud** for a
zero-install shared demo.

## Future improvements

- Connect a real LLM (Claude / GPT) for narrative report generation — the
  hook and grounded prompt already exist in `report_generator.py`
- Replace the ML placeholder with a trained gradient-boosting or SARIMAX
  forecaster and backtest it against the simple methods
- Read open purchase-order lines instead of assuming inbound quantities
- Multi-warehouse support (central DC vs retail stores vs field technicians)
- Service-level driven safety stocks (target fill rate per criticality class)
- Scheduled runs (e.g. GitHub Actions or cron) that email the report every
  Monday without opening the app
- User authentication and role-based views (buyer vs management)
