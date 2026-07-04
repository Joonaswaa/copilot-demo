"""
data_generator.py
-----------------
Generates a synthetic but realistic telecom supply chain dataset.

The data simulates an ERP export from a telecom operator's logistics system:
consumer devices, network equipment, accessories, refurbished stock and
installation/spare parts, sourced from a set of suppliers with different
reliability profiles.

No real company data is used. All values are randomly generated but tuned
to look plausible from a business perspective (realistic price points,
lead times, demand levels and supplier behaviour).

Run directly to (re)create data/sample_telecom_supply_chain_data.csv:

    python -m src.data_generator
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Reproducible output so the sample file in the repo stays stable.
RNG_SEED = 42

# Number of weeks of historical demand stored per SKU.
HISTORY_WEEKS = 12

# ---------------------------------------------------------------------------
# Product catalogue: (product name, category, brand, unit cost range EUR,
# margin range %, base weekly demand range, criticality)
#
# Criticality reflects business impact of a stockout:
#   "critical" - blocks installations or key sales (e.g. fiber modems)
#   "high"     - major revenue products (flagship phones)
#   "medium"   - standard portfolio
#   "low"      - nice-to-have accessories / refurb
# ---------------------------------------------------------------------------
PRODUCT_CATALOGUE = [
    # --- Consumer devices ---
    ("iPhone 16 128GB", "Consumer devices", "Apple", (650, 750), (8, 14), (60, 140), "high"),
    ("iPhone 16 Pro 256GB", "Consumer devices", "Apple", (950, 1100), (8, 14), (40, 100), "high"),
    ("Samsung Galaxy S25 256GB", "Consumer devices", "Samsung", (600, 720), (10, 16), (55, 130), "high"),
    ("Samsung Galaxy A56", "Consumer devices", "Samsung", (280, 340), (12, 18), (70, 160), "medium"),
    ("Google Pixel 10", "Consumer devices", "Google", (520, 620), (10, 16), (25, 70), "medium"),
    ("OnePlus 13", "Consumer devices", "OnePlus", (480, 580), (10, 16), (15, 50), "medium"),
    ("iPad 11th Gen", "Consumer devices", "Apple", (380, 450), (10, 15), (25, 60), "medium"),
    ("Samsung Galaxy Tab S10", "Consumer devices", "Samsung", (420, 520), (10, 16), (15, 45), "medium"),
    ("Lenovo ThinkPad E14", "Consumer devices", "Lenovo", (620, 750), (8, 14), (10, 30), "medium"),
    ("HP Pavilion 15", "Consumer devices", "HP", (520, 650), (8, 14), (10, 30), "medium"),
    ("Apple Watch Series 11", "Consumer devices", "Apple", (320, 400), (10, 16), (20, 55), "medium"),
    ("Samsung Galaxy Watch 8", "Consumer devices", "Samsung", (240, 300), (12, 18), (15, 45), "medium"),
    ("PlayStation 5 Slim", "Consumer devices", "Sony", (420, 470), (5, 9), (25, 80), "medium"),
    ("Xbox Series X", "Consumer devices", "Microsoft", (400, 450), (5, 9), (15, 50), "medium"),
    ("Nintendo Switch 2", "Consumer devices", "Nintendo", (330, 380), (6, 10), (20, 70), "medium"),
    # --- Accessories ---
    ("AirPods Pro 3", "Accessories", "Apple", (180, 220), (15, 25), (50, 120), "medium"),
    ("Samsung Galaxy Buds 4", "Accessories", "Samsung", (110, 140), (18, 28), (35, 90), "low"),
    ("Sony WH-1000XM6 Headphones", "Accessories", "Sony", (260, 320), (14, 22), (15, 45), "low"),
    ("JBL Tune 720BT Headphones", "Accessories", "JBL", (55, 75), (25, 40), (30, 80), "low"),
    ("Anker 65W USB-C Charger", "Accessories", "Anker", (22, 30), (35, 55), (60, 150), "low"),
    ("Belkin USB-C Cable 2m", "Accessories", "Belkin", (8, 12), (45, 70), (80, 200), "low"),
    ("Spigen Phone Case iPhone 16", "Accessories", "Spigen", (9, 14), (50, 80), (70, 180), "low"),
    ("PanzerGlass Screen Protector", "Accessories", "PanzerGlass", (7, 11), (50, 80), (60, 160), "low"),
    ("Samsung 25W Travel Charger", "Accessories", "Samsung", (14, 20), (35, 55), (40, 110), "low"),
    # --- Network equipment ---
    ("Fiber Modem XG-2000", "Network equipment", "Nokia", (85, 110), (20, 30), (90, 200), "critical"),
    ("Fiber Modem Lite F-100", "Network equipment", "ZTE", (55, 75), (22, 32), (60, 140), "critical"),
    ("WiFi 7 Router AX-9000", "Network equipment", "TP-Link", (140, 180), (18, 26), (45, 110), "critical"),
    ("WiFi 6 Mesh Kit (3-pack)", "Network equipment", "TP-Link", (190, 240), (16, 24), (25, 70), "high"),
    ("5G Home Router HR-500", "Network equipment", "Huawei", (160, 210), (16, 24), (50, 120), "critical"),
    ("5G Outdoor Antenna OA-45", "Network equipment", "Poynting", (110, 150), (20, 30), (15, 45), "high"),
    ("4G Backup Router BR-200", "Network equipment", "Teltonika", (95, 130), (18, 26), (10, 35), "medium"),
    ("Network Switch 8-port GS308", "Network equipment", "Netgear", (28, 40), (25, 40), (20, 60), "medium"),
    ("Network Switch 24-port Managed", "Network equipment", "Cisco", (240, 320), (14, 22), (5, 20), "high"),
    ("Set-top Box UHD-4K", "Network equipment", "Arris", (60, 85), (18, 28), (35, 90), "high"),
    # --- SIM & starter kits (counted under network equipment ops) ---
    ("SIM Card Triple-cut (100-pack)", "Network equipment", "Idemia", (45, 60), (40, 60), (30, 80), "critical"),
    ("eSIM Starter Kit", "Network equipment", "Idemia", (2, 4), (60, 90), (100, 250), "high"),
    # --- Installation and spare parts ---
    ("Fiber Splice Kit Pro", "Installation and spare parts", "Fibrain", (35, 50), (25, 40), (15, 45), "critical"),
    ("Fiber Optic Cable 500m Drum", "Installation and spare parts", "Prysmian", (180, 240), (18, 28), (8, 25), "critical"),
    ("Cat6 Cable Box 305m", "Installation and spare parts", "Draka", (75, 100), (22, 34), (10, 30), "high"),
    ("Wall Outlet RJ45 Duplex", "Installation and spare parts", "Schneider", (6, 10), (40, 65), (50, 130), "medium"),
    ("Router Power Adapter 12V", "Installation and spare parts", "MeanWell", (9, 14), (40, 60), (30, 90), "high"),
    ("Antenna Mounting Bracket", "Installation and spare parts", "Poynting", (14, 22), (30, 50), (10, 35), "medium"),
    ("Coaxial Connector Kit", "Installation and spare parts", "Hirschmann", (11, 17), (35, 55), (15, 45), "medium"),
    ("Technician Tool Set TS-40", "Installation and spare parts", "Jonard", (120, 160), (20, 32), (2, 10), "low"),
    # --- Returns and refurbished ---
    ("Refurbished iPhone 14 128GB", "Returns and refurbished", "Apple", (330, 400), (12, 20), (20, 60), "medium"),
    ("Refurbished Samsung Galaxy S23", "Returns and refurbished", "Samsung", (280, 350), (12, 20), (15, 50), "medium"),
    ("Refurbished iPad 9th Gen", "Returns and refurbished", "Apple", (200, 260), (12, 20), (10, 30), "low"),
    ("Returned Router Grade B", "Returns and refurbished", "TP-Link", (45, 65), (25, 40), (10, 35), "low"),
    ("Refurbished 5G Router HR-400", "Returns and refurbished", "Huawei", (80, 110), (20, 32), (8, 28), "low"),
    ("Returned Xbox Series S Grade A", "Returns and refurbished", "Microsoft", (170, 220), (10, 18), (5, 20), "low"),
]

# ---------------------------------------------------------------------------
# Suppliers: (name, on-time rate range, average delay days range)
# Some suppliers are deliberately weaker so the supplier analysis page
# has interesting findings to show.
# ---------------------------------------------------------------------------
SUPPLIERS = [
    ("Nordic Device Distribution Oy", (0.94, 0.99), (0.2, 1.0)),
    ("TechWave Logistics AB", (0.90, 0.96), (0.5, 1.5)),
    ("Baltic Components OÜ", (0.82, 0.90), (1.5, 3.5)),
    ("Global Telecom Supply Ltd", (0.75, 0.85), (2.5, 5.5)),
    ("Connect Parts Europe GmbH", (0.88, 0.94), (1.0, 2.5)),
    ("Scandi Network Wholesale AS", (0.92, 0.97), (0.3, 1.2)),
    ("EuroFiber Materials BV", (0.80, 0.88), (2.0, 4.5)),
    ("Asia Direct Electronics HK", (0.70, 0.82), (3.0, 7.0)),
    ("ReCircle Refurb Solutions Oy", (0.85, 0.92), (1.0, 3.0)),
    ("PrimeCell Accessories ApS", (0.89, 0.95), (0.8, 2.0)),
]

# Preferred supplier pools per category (a supplier specialises, as in reality).
CATEGORY_SUPPLIERS = {
    "Consumer devices": [0, 1, 3, 7],
    "Accessories": [1, 9, 7, 4],
    "Network equipment": [5, 4, 2, 3],
    "Installation and spare parts": [6, 2, 4, 5],
    "Returns and refurbished": [8, 3],
}


def _weekly_demand_series(base: float, rng: np.random.Generator) -> list[int]:
    """
    Build HISTORY_WEEKS weeks of demand with a random trend, mild
    seasonality and noise, so forecasting has real signal to work with.
    """
    trend = rng.uniform(-0.03, 0.04)            # weekly growth/decline
    season_amp = rng.uniform(0.0, 0.15)          # promo / payday waves
    noise_sd = rng.uniform(0.06, 0.18)

    series = []
    for week in range(HISTORY_WEEKS):
        seasonal = 1 + season_amp * np.sin(2 * np.pi * week / 4)  # ~monthly cycle
        level = base * (1 + trend) ** week * seasonal
        value = max(0, rng.normal(level, level * noise_sd))
        series.append(int(round(value)))
    return series


def generate_dataset(n_rows: int | None = None, seed: int = RNG_SEED) -> pd.DataFrame:
    """
    Generate the full synthetic dataset as a pandas DataFrame.

    Each catalogue product appears once (one SKU per product), plus a few
    products get a duplicate SKU from an alternate supplier to make the
    supplier comparison more realistic.
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)
    today = date(2026, 7, 3)  # fixed "export date" for reproducibility

    rows = []
    sku_counter = 1000

    catalogue = list(PRODUCT_CATALOGUE)
    # Duplicate ~20% of products with an alternate supplier (dual sourcing).
    for item in random.sample(catalogue, k=max(1, len(catalogue) // 5)):
        catalogue.append(item)

    for (name, category, brand, cost_rng, margin_rng, demand_rng, criticality) in catalogue:
        sku_counter += 1
        sku = f"TEL-{sku_counter}"

        supplier_idx = random.choice(CATEGORY_SUPPLIERS[category])
        supplier_name, otr_rng, delay_rng = SUPPLIERS[supplier_idx]
        supplier_on_time = round(rng.uniform(*otr_rng), 3)
        supplier_delay = round(rng.uniform(*delay_rng), 1)

        base_weekly = rng.uniform(*demand_rng)
        history = _weekly_demand_series(base_weekly, rng)
        recent_avg = float(np.mean(history[-4:]))
        monthly_demand = int(round(recent_avg * 4.33))

        unit_cost = round(rng.uniform(*cost_rng), 2)
        margin_pct = round(rng.uniform(*margin_rng), 1)
        selling_price = round(unit_cost / (1 - margin_pct / 100), 2)

        lead_time = int(rng.integers(3, 35))
        if supplier_idx == 7:  # overseas supplier ships slower
            lead_time = int(rng.integers(21, 45))

        safety_stock = int(round(recent_avg * rng.uniform(0.8, 1.6)))
        reorder_point = int(round(recent_avg * (lead_time / 7) + safety_stock))

        # Stock level scenarios: some healthy, some at risk, some overstocked.
        scenario = rng.uniform()
        if scenario < 0.18:        # stockout risk
            current_stock = int(round(reorder_point * rng.uniform(0.15, 0.75)))
        elif scenario < 0.75:      # healthy
            current_stock = int(round(reorder_point * rng.uniform(1.0, 2.2)))
        else:                      # overstock / slow mover candidate
            current_stock = int(round(reorder_point * rng.uniform(2.5, 6.0)))

        inventory_value = round(current_stock * unit_cost, 2)

        # Turnover: annualised demand value / current inventory value.
        annual_cogs = monthly_demand * 12 * unit_cost
        turnover = round(annual_cogs / inventory_value, 2) if inventory_value > 0 else 0.0

        # Open purchase order simulation.
        delivery_roll = rng.uniform()
        expected = today + timedelta(days=int(rng.integers(1, lead_time + 5)))
        if delivery_roll < 0.55:
            delivery_status = "In transit"
            actual = ""
        elif delivery_roll < 0.55 + (1 - supplier_on_time) * 1.3:
            delivery_status = "Delayed"
            actual = ""
            expected = today - timedelta(days=int(rng.integers(1, 8)))  # already overdue
        else:
            delivery_status = "Delivered"
            delay_realised = int(rng.uniform() > supplier_on_time) * int(rng.integers(1, 9))
            actual_dt = expected - timedelta(days=int(rng.integers(0, 3))) + timedelta(days=delay_realised)
            expected = today - timedelta(days=int(rng.integers(2, 20)))
            actual_dt = expected + timedelta(days=delay_realised)
            actual = actual_dt.isoformat()

        return_rate = round(float(rng.uniform(0.5, 4.0)), 1)
        if category == "Returns and refurbished":
            return_rate = round(float(rng.uniform(4.0, 12.0)), 1)
        refurb = "Refurbished" if "Refurbished" in name or "Returned" in name else "New"

        rows.append({
            "sku": sku,
            "product_name": name,
            "category": category,
            "brand": brand,
            "supplier": supplier_name,
            "current_stock": current_stock,
            "reorder_point": reorder_point,
            "safety_stock": safety_stock,
            "monthly_demand": monthly_demand,
            # Semicolon-separated so it survives CSV round-trips cleanly.
            "weekly_demand_history": ";".join(str(v) for v in history),
            # Left blank on purpose: the app computes this column itself.
            "forecasted_demand_next_4_weeks": "",
            "lead_time_days": lead_time,
            "unit_cost": unit_cost,
            "selling_price": selling_price,
            "inventory_value": inventory_value,
            "margin_percentage": margin_pct,
            "stock_turnover_rate": turnover,
            "delivery_status": delivery_status,
            "expected_delivery_date": expected.isoformat(),
            "actual_delivery_date": actual,
            "supplier_on_time_rate": supplier_on_time,
            "supplier_average_delay_days": supplier_delay,
            "return_rate": return_rate,
            "refurbished_status": refurb,
            # Left blank on purpose: computed by risk_scoring.py.
            "risk_score": "",
            "criticality_level": criticality,
        })

    df = pd.DataFrame(rows)
    if n_rows:
        df = df.head(n_rows)
    return df


def save_sample_csv(path: str | Path = "data/sample_telecom_supply_chain_data.csv") -> Path:
    """Generate the dataset and write it to CSV. Returns the file path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generate_dataset().to_csv(path, index=False)
    return path


if __name__ == "__main__":
    out = save_sample_csv()
    print(f"Sample dataset written to {out.resolve()}")
