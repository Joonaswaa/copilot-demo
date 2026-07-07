"""Methodology and formula documentation for the info page (FI / EN)."""

from __future__ import annotations

SECTION_LABELS: dict[str, dict[str, str]] = {
    "fi": {
        "pipeline": "Analyysiputki",
        "overview": "Yleiskatsaus",
        "inventory_risk": "Varastoriski",
        "demand_forecast": "Kysyntäennuste",
        "suppliers": "Toimittajat",
        "slow_movers": "Hidas varasto",
        "purchases": "Ostosuositukset",
        "report": "AI-viikkoraportti",
        "automation": "Automaatio",
    },
    "en": {
        "pipeline": "Analysis pipeline",
        "overview": "Overview",
        "inventory_risk": "Inventory risk",
        "demand_forecast": "Demand forecast",
        "suppliers": "Suppliers",
        "slow_movers": "Slow-moving inventory",
        "purchases": "Purchase recommendations",
        "report": "AI weekly report",
        "automation": "Automation",
    },
}

CONTENT: dict[str, dict[str, str]] = {
    "fi": {
        "pipeline": """
### Analyysiputki

Kun painat **Suorita analyysi**, data kulkee seuraavassa järjestyksessä:

1. **Datan puhdistus** (`clean_data`) — tyypit, puuttuvat arvot, johdetut kentät
2. **Kysyntäennuste** (`add_forecasts`) — 4 viikon ennuste per SKU
3. **Riskipisteet** (`add_risk_scores`) — yhdistelmäpisteet 0–100
4. **Ostosuositukset** (`recommend_purchases`) — order-up-to -logiikka
5. **Hidas varasto** (`find_slow_movers`) — sidotun pääoman tunnistus
6. **Toimittajapisteet** (`supplier_scorecard`) — aggregoitu toimittajariski
7. **KPI:t ja Copilot** (`compute_kpis`, `copilot_recommendations`)

---

### Datan puhdistus ja johdetut kentät

| Kenttä | Kaava / sääntö |
|--------|----------------|
| `inventory_value` | `current_stock × unit_cost` |
| `margin_percentage` | `(selling_price − unit_cost) / selling_price × 100` |
| `stock_turnover_rate` | `(monthly_demand × 12 × unit_cost) / inventory_value` |
| `reorder_point` | puuttuva → `safety_stock × 2` |
| `supplier_on_time_rate` | jos arvo > 1,5 → jaetaan 100:lla; rajataan välille [0, 1] |
| `demand_history_list` | 12 viikon historia pilkulla/puolipisteellä eroteltuna |

Kysyntähistoria on syöte kaikille ennuste- ja trendilaskelmille.
""",
        "overview": """
### Yleiskatsaus — KPI:t

| Mittari | Kaava |
|---------|-------|
| **Varaston kokonaisarvo** | `Σ (current_stock × unit_cost)` |
| **SKU-määrä** | rivien lukumäärä |
| **Varaston loppumisriskit** | `current_stock < reorder_point` |
| **Korkean riskin tuotteet** | loppumisriski **JA** `criticality_level ∈ {high, critical}` |
| **Myöhässä olevat toimitukset** | `delivery_status = "Delayed"` |
| **Keskim. toimittajan oikea-aikaisuus** | `mean(supplier_on_time_rate) × 100` |
| **Suositeltu ostojen arvo** | `Σ orders.estimated_cost` |

**Huom:** Loppumisriski perustuu **täydennys pisteeseen** (`reorder_point`), ei suoraan ennusteeseen. Ennuste vaikuttaa riskipisteisiin ja ostomääriin.

---

### AI Copilot — priorisointi

Copilot näyttää enintään **5 toimenpidettä**, järjestettynä kiireellisyyden mukaan:

1. Enintään 3 **Kiireellistä** ostosuositusta
2. Huonoin toimittaja, jos `risk_level = High`
3. Suurin hidas erä (`tied_capital`)
4. Enintään 2 **kriittistä** tuotetta turvavaraston alapuolella
5. Kysyntäpiikki: `demand_trend_pct > 20 %` ilman loppumisriskiä

**Kiireellisyysjärjestys:** Kiireellinen → Korkea → Keskitaso.
""",
        "inventory_risk": """
### Yhdistelmäriskipisteet (0–100)

Riskipisteet ovat painotettu summa kuudesta osapistemäärästä:

| Komponentti | Paino | Kuvaus |
|-------------|-------|--------|
| Varaston riittävyys | **35 %** | Kuinka kauan varasto riittää vs. toimitusaika |
| Toimittajariski | **20 %** | Oikea-aikaisuus ja viive |
| Kysynnän volatiliteetti | **15 %** | Ennustettavuus (CV) |
| Kriittisyys | **15 %** | Liiketoimintavaikutus |
| Toimitusaika | **10 %** | Pitkä putki = hitaampi reagointi |
| Marginaali ja palautukset | **5 %** | Tuotteen arvo |

**Yhdistelmäkaava:**

```
risk_score = 0,35×stockout + 0,20×supplier + 0,15×volatility
           + 0,15×criticality + 0,10×lead_time + 0,05×margin_returns
```

---

### Osapistemäärät

**Varaston riittävyys (viikkoina):**
```
weekly_demand = forecast_4wk_total / 4
weeks_of_cover = current_stock / weekly_demand    (99 jos kysyntä = 0)
```

**Loppumisriski-alapiste (stockout subscore):**
```
lead_weeks = lead_time_days / 7 + 1
jos cover ≥ 2 × lead_weeks  → 0 pistettä
jos cover ≤ 0               → 100 pistettä
muuten                      → 100 × (1 − cover / (2 × lead_weeks))
```

**Toimittaja-alapiste:**
```
otr_component   = (1 − supplier_on_time_rate) × 100
delay_component = min(supplier_average_delay_days, 10) × 10
→ 0,7 × otr + 0,3 × delay
```

**Volatiliteetti-alapiste:**
```
demand_volatility = std(historia) / mean(historia)
→ min(volatility / 0,5, 1,0) × 100
```

**Kriittisyys (suora kartta):**

| Taso | Pisteet |
|------|---------|
| low | 15 |
| medium | 40 |
| high | 70 |
| critical | 100 |

**Toimitusaika-alapiste:**
```
min(lead_time_days / 35, 1,0) × 100
```

**Marginaali ja palautukset:**
```
margin_component  = max(0, (25 − margin_%) / 25) × 100
returns_component = min(return_rate / 10, 1,0) × 100
→ 0,5 × margin + 0,5 × returns
```

---

### Riskitasot

| Pisteet | Taso |
|---------|------|
| 0–30 | Matala |
| 31–50 | Keskitaso |
| 51–70 | Korkea |
| 71–100 | Kriittinen |

**Loppumisriskilippu:** `stockout_flag = current_stock < reorder_point`
""",
        "demand_forecast": """
### Ennustehorisontti

Kaikki menetelmät tuottavat **4 viikon** ennusteen (`FORECAST_WEEKS = 4`).

Valinta tehdään sivupalkista: **Eksponentiaalinen tasoitus (Holt)**, **Liukuva keskiarvo** tai **ML-malli**.

---

### 1. Liukuva keskiarvo (4 viikkoa)

Yksinkertaisin menetelmä — tasainen ennuste viimeisten havaintojen keskiarvosta:

```
level = mean(viimeiset 4 viikkoa historiasta)
ennuste[1..4] = level
```

Jos historiaa on alle 4 viikkoa, käytetään kaikkia saatavilla olevia viikkoja.

**Sopii:** vakaa, hitaasti muuttuva kysyntä. **Heikkous:** ei reagoi trendiin.

---

### 2. Holtin eksponentiaalinen tasoitus (oletus)

Kaksinkertainen eksponentiaalinen tasoitus (taso + trendi). Parametrit:

| Parametri | Arvo | Merkitys |
|-----------|------|----------|
| α (alpha) | 0,4 | Kuinka nopeasti taso reagoi uuteen dataan |
| β (beta) | 0,2 | Kuinka nopeasti trendi päivittyy |
| vaimennus | 0,9 | Estää trendin räjähtämisen eteenpäin |

**Alustus:** `level = historia[0]`, `trend = historia[1] − historia[0]`

**Päivitys jokaiselle havainnolle:**
```
level = α × arvo + (1−α) × (level + trend)
trend = β × (level − edellinen_level) + (1−β) × trend
```

**Ennuste askelille s (1…4):**
```
projected = level + trend × Σ(damping^i, i=1..s)
ennuste[s] = max(0, projected)
```

Jos historiaa on alle 4 viikkoa → palataan liukuvaan keskiarvoon.

**Sopii:** trendiä sisältävä kysyntä. Trendi vaimennetaan, jotta muutama vahva viikko ei paisuta ennustetta liikaa.

---

### 3. ML-malli (placeholder)

Tällä hetkellä kutsuu samaa Holt-menetelmää. Tuotannossa voisi olla esim.:

- Gradient boosting lag-ominaisuuksilla (t−1…t−8)
- SARIMAX / Prophet kausittaiselle kysynnälle
- Yhteinen malli kaikille SKU:ille tuoteominaisuuksilla

---

### Johdetut mittarit

| Kenttä | Kaava |
|--------|-------|
| `forecast_4wk_total` | `sum(ennuste_lista)` |
| `demand_volatility` (CV) | `std(historia) / mean(historia)` |
| `demand_trend_pct` | `(mean(viimeiset 4 vk) − mean(edelliset 4 vk)) / edellinen × 100` |

Trendi lasketaan vain, jos historiassa on vähintään 8 viikkoa.

**Viikoittainen turvataso (kaaviossa):** `safety_stock / max(lead_time_days / 7, 1)`
""",
        "suppliers": """
### Toimittajapisteet — aggregointi

Jokainen toimittaja aggregoidaan SKU-tasolta:

| Kenttä | Laskenta |
|--------|----------|
| `skus` | SKU-määrä |
| `on_time_rate` | keskiarvo × 100 (%) |
| `avg_delay_days` | keskiarvo (päivää) |
| `delayed_deliveries` | `delivery_status = "Delayed"` -rivien määrä |
| `inventory_value` | varaston arvon summa |
| `categories` | uniikit kategoriat |

---

### Toimittajariskipisteet (0–100)

```
otr_risk        = (1 − on_time_rate) × 100
delay_risk      = min(avg_delay_days, 10) × 10
open_delay_risk = min(delayed_deliveries, 5) × 20
stake           = (max_criticality_rank / 3) × 100

supplier_risk_score = 0,45×otr + 0,20×delay + 0,20×open_delay + 0,15×stake
```

Kriittisyysrankki: low=0, medium=1, high=2, critical=3.

**Riskitasot:**

| Pisteet | Taso |
|---------|------|
| 0–25 | Matala |
| 26–50 | Keskitaso |
| > 50 | Korkea |

Järjestetään huonoimmasta parimpaan (`supplier_risk_score` laskevasti).

---

### Hälytysrajat

Hälytys syntyy, jos **jokin** ehdoista täyttyy:

- `on_time_rate < 88 %`
- `avg_delay_days > 3 päivää`
- `delayed_deliveries ≥ 2`

Kaaviossa näkyy **90 % tavoiteviiva** oikea-aikaisuudelle.
""",
        "slow_movers": """
### Hitaan varaston tunnistus

Tuote merkitään hitaaksi, kun **vähintään 2 kolmesta** ehdosta täyttyy:

| Ehto | Raja |
|------|------|
| Matala kierto | `stock_turnover_rate < 4,0` (vuosikierto) |
| Liikaa varastoa | `weeks_of_cover > 12` viikkoa |
| Laskeva kysyntä | `demand_trend_pct < −5 %` |

Kaksi signaalia vähentää vääriä positiivisia (esim. strateginen puskuri).

---

### Sidottu pääoma

```
weekly_demand = forecast_4wk_total / 4
excess_units  = max(0, current_stock − weekly_demand × 8)
tied_capital  = excess_units × unit_cost
```

**8 viikon puskuri** = tavoitetaso; ylimääräinen varasto on kampanjakohde.

Järjestetään `tied_capital` laskevasti.

---

### Ehdotetut toimenpiteet (sääntöketju)

1. `margin ≥ 25 %` **JA** `trend < −10 %` → hintakampanja
2. Kategoria *Returns and refurbished* → outlet/refurb-kanava
3. Kategoria *Accessories* → bundlaus myydyimpien laitteiden kanssa
4. `weeks_of_cover > 26` → täydennys pysäytetään, selvityskampanja
5. Muuten → kampanjasuunnittelu, täydennys tauolle
""",
        "purchases": """
### Order-up-to -logiikka (dashboard)

Ostosuositukset perustuvat ennusteeseen ja toimitusaikaan:

```
REVIEW_PERIOD = 7 päivää (viikkoraportin rytmi)

weekly_demand  = forecast_4wk_total / 4
horizon_weeks  = (lead_time_days + 7) / 7

Kriittisyyslisä turvavarastoon:
  low=0 %, medium=5 %, high=10 %, critical=20 %

target_level = weekly_demand × horizon_weeks + safety_stock × (1 + uplift)

inbound (jos delivery_status = "In transit"):
  weekly_demand × 4    ← oletus: matkalla ~4 vk kysyntää

recommended_qty = ceil(max(0, target_level − current_stock − inbound))
```

Vain rivit, joissa `recommended_qty > 0`, näytetään.

**Arvioitu kustannus:** `recommended_qty × unit_cost`

---

### Prioriteetit

| Ehto | Prioriteetti |
|------|--------------|
| `stockout_flag` **JA** kriittisyys high/critical | **Kiireellinen** |
| `stockout_flag` | **Korkea** |
| `risk_score ≥ 50` | **Keskitaso** |
| muuten | **Normaali** |

Järjestys: prioriteetti → riskipisteet (laskeva).

---

### Suosituksen perustelu

Teksti koostuu täsmäävistä lauseista:

- Loppumisriski → viikkojen riittävyys vs. toimitusaika
- `current_stock ≤ reorder_point`
- `demand_trend_pct > 10 %`
- `criticality_level = critical`
- Muuten: "alle order-up-to -tason"
""",
        "report": """
### Raportin generointi

Kaksi polkua:

1. **LLM-polku** — jos `ANTHROPIC_API_KEY` tai `OPENAI_API_KEY` on `.env`-tiedostossa (tällä hetkellä kommentoitu pois → aina fallback)
2. **Sääntöpohjainen** (oletus) — sama data, strukturoitu markdown EN + FI

Raportti koostuu lasketuista analytiikoista — ei erillistä laskentaa.

---

### Raportin osiot

- Johtoryhmän yhteenveto (kaikki KPI:t)
- Top 5 riskiä (`risk_score`)
- Loppumisriskillä merkityt tuotteet (max 8)
- Hitaat erät (max 5) + ehdotetut toimenpiteet
- Toimittajahälytykset (max 5)
- Kiireelliset/korkean prioriteetin ostot (max 8)
- KPI-yhteenveto
- 4 kiinteää johtoryhmätoimenpidettä

---

### Vientimuodot

- **Markdown** — molemmilla kielillä
- **PDF** — `fpdf2`
- **PowerPoint** — EN + FI -deckit
- **Sähköposti** — valinnainen SMTP (`.env`)
""",
        "automation": """
### RPA-workflow (10 vaihetta)

1. ERP-vienti löytyy (`data/erp_exports/`)
2. Datan validointi (12 vk historia, ei-negatiiviset varastot, lead time ≥ 1)
3.–5. Analyysiputki (sama kuin dashboard)
6. **Ostosuositukset** — erillinen RPA-kaava (ks. alla)
7. PDF-raportti (suomeksi)
8. PowerPoint (EN + FI)
9. Sähköpostiluonnos (`outbox/email_drafts/`)
10. Arkistointi (`reports/archive/<run_id>/`)

---

### RPA vs. dashboard — ostokaava

**Dashboard** käyttää ennustepohjaista order-up-to -logiikkaa.

**RPA-vienti** käyttää yksinkertaisempaa sääntöä:

```
qty = max(0, reorder_point + safety_stock − current_stock)

Prioriteetti:
  stock < safety_stock              → Kiireellinen
  stock < reorder_point             → Korkea
  stock < reorder_point + safety    → Keskitaso
  muuten (qty > 0)                  → Matala
```

RPA-taulukko on tarkoitettu ERP/RPA-integraation simulointiin; dashboard on tarkempi ostopäätöksiin.

---

### Vanhentunut data

Jos datalähde vaihtuu analyysin jälkeen (tiedoston `mtime` + koko), näytetään varoitus: aja workflow uudelleen.
""",
    },
    "en": {
        "pipeline": """
### Analysis pipeline

When you click **Run analysis**, data flows through:

1. **Data cleaning** (`clean_data`) — types, missing values, derived fields
2. **Demand forecast** (`add_forecasts`) — 4-week forecast per SKU
3. **Risk scores** (`add_risk_scores`) — composite 0–100 score
4. **Purchase recommendations** (`recommend_purchases`) — order-up-to logic
5. **Slow movers** (`find_slow_movers`) — tied capital detection
6. **Supplier scorecard** (`supplier_scorecard`) — aggregated supplier risk
7. **KPIs & Copilot** (`compute_kpis`, `copilot_recommendations`)

---

### Data cleaning and derived fields

| Field | Formula / rule |
|-------|----------------|
| `inventory_value` | `current_stock × unit_cost` |
| `margin_percentage` | `(selling_price − unit_cost) / selling_price × 100` |
| `stock_turnover_rate` | `(monthly_demand × 12 × unit_cost) / inventory_value` |
| `reorder_point` | if missing → `safety_stock × 2` |
| `supplier_on_time_rate` | if value > 1.5 → divide by 100; clip to [0, 1] |
| `demand_history_list` | 12 weeks of history, semicolon/comma-separated |

Demand history feeds all forecast and trend calculations.
""",
        "overview": """
### Overview — KPIs

| Metric | Formula |
|--------|---------|
| **Total inventory value** | `Σ (current_stock × unit_cost)` |
| **SKU count** | row count |
| **Stockout risk SKUs** | `current_stock < reorder_point` |
| **High-risk products** | stockout risk **AND** `criticality_level ∈ {high, critical}` |
| **Delayed deliveries** | `delivery_status = "Delayed"` |
| **Avg supplier on-time rate** | `mean(supplier_on_time_rate) × 100` |
| **Recommended purchase value** | `Σ orders.estimated_cost` |

**Note:** Stockout risk uses the **reorder point**, not the forecast directly. The forecast drives risk scores and order quantities.

---

### AI Copilot — prioritisation

Copilot shows up to **5 actions**, sorted by urgency:

1. Up to 3 **Urgent** purchase recommendations
2. Worst supplier if `risk_level = High`
3. Largest slow mover (`tied_capital`)
4. Up to 2 **critical** products below safety stock
5. Demand surge: `demand_trend_pct > 20%` without stockout flag

**Urgency order:** Urgent → High → Medium.
""",
        "inventory_risk": """
### Composite risk score (0–100)

The score is a weighted sum of six sub-scores:

| Component | Weight | Description |
|-----------|--------|-------------|
| Stock coverage | **35%** | Weeks of stock vs lead time |
| Supplier risk | **20%** | On-time rate and delay |
| Demand volatility | **15%** | Predictability (CV) |
| Criticality | **15%** | Business impact |
| Lead time | **10%** | Long pipeline = slow reaction |
| Margin & returns | **5%** | Product value erosion |

**Composite formula:**

```
risk_score = 0.35×stockout + 0.20×supplier + 0.15×volatility
           + 0.15×criticality + 0.10×lead_time + 0.05×margin_returns
```

---

### Sub-scores

**Weeks of cover:**
```
weekly_demand = forecast_4wk_total / 4
weeks_of_cover = current_stock / weekly_demand    (99 if demand = 0)
```

**Stockout subscore:**
```
lead_weeks = lead_time_days / 7 + 1
if cover ≥ 2 × lead_weeks  → 0 points
if cover ≤ 0               → 100 points
else                       → 100 × (1 − cover / (2 × lead_weeks))
```

**Supplier subscore:**
```
otr_component   = (1 − supplier_on_time_rate) × 100
delay_component = min(supplier_average_delay_days, 10) × 10
→ 0.7 × otr + 0.3 × delay
```

**Volatility subscore:**
```
demand_volatility = std(history) / mean(history)
→ min(volatility / 0.5, 1.0) × 100
```

**Criticality (direct map):**

| Level | Score |
|-------|-------|
| low | 15 |
| medium | 40 |
| high | 70 |
| critical | 100 |

**Lead time subscore:**
```
min(lead_time_days / 35, 1.0) × 100
```

**Margin & returns:**
```
margin_component  = max(0, (25 − margin_%) / 25) × 100
returns_component = min(return_rate / 10, 1.0) × 100
→ 0.5 × margin + 0.5 × returns
```

---

### Risk levels

| Score | Level |
|-------|-------|
| 0–30 | Low |
| 31–50 | Medium |
| 51–70 | High |
| 71–100 | Critical |

**Stockout flag:** `stockout_flag = current_stock < reorder_point`
""",
        "demand_forecast": """
### Forecast horizon

All methods produce a **4-week** forecast (`FORECAST_WEEKS = 4`).

Select in the sidebar: **Exponential smoothing (Holt)**, **Moving average**, or **ML model**.

---

### 1. Moving average (4 weeks)

Flat forecast from the mean of recent observations:

```
level = mean(last 4 weeks of history)
forecast[1..4] = level
```

If fewer than 4 weeks exist, all available weeks are used.

**Best for:** stable, slow-changing demand. **Weakness:** no trend response.

---

### 2. Holt exponential smoothing (default)

Double exponential smoothing (level + trend). Parameters:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| α (alpha) | 0.4 | How fast level reacts to new data |
| β (beta) | 0.2 | How fast trend updates |
| damping | 0.9 | Prevents trend exploding forward |

**Init:** `level = history[0]`, `trend = history[1] − history[0]`

**Update per observation:**
```
level = α × value + (1−α) × (level + trend)
trend = β × (level − prev_level) + (1−β) × trend
```

**Forecast for step s (1…4):**
```
projected = level + trend × Σ(damping^i, i=1..s)
forecast[s] = max(0, projected)
```

If history has fewer than 4 weeks → falls back to moving average.

**Best for:** trending demand. Damping stops a few strong weeks from inflating the forecast.

---

### 3. ML model (placeholder)

Currently calls the same Holt method. In production this could be:

- Gradient boosting on lag features (t−1…t−8)
- SARIMAX / Prophet for seasonal series
- Shared model across SKUs with product features

---

### Derived metrics

| Field | Formula |
|-------|---------|
| `forecast_4wk_total` | `sum(forecast_list)` |
| `demand_volatility` (CV) | `std(history) / mean(history)` |
| `demand_trend_pct` | `(mean(last 4 wk) − mean(prev 4 wk)) / prev × 100` |

Trend is computed only when history has at least 8 weeks.

**Weekly safety reference (chart):** `safety_stock / max(lead_time_days / 7, 1)`
""",
        "suppliers": """
### Supplier scorecard — aggregation

Each supplier is aggregated from SKU level:

| Field | Calculation |
|-------|-------------|
| `skus` | SKU count |
| `on_time_rate` | mean × 100 (%) |
| `avg_delay_days` | mean (days) |
| `delayed_deliveries` | count where `delivery_status = "Delayed"` |
| `inventory_value` | sum of inventory value |
| `categories` | unique categories |

---

### Supplier risk score (0–100)

```
otr_risk        = (1 − on_time_rate) × 100
delay_risk      = min(avg_delay_days, 10) × 10
open_delay_risk = min(delayed_deliveries, 5) × 20
stake           = (max_criticality_rank / 3) × 100

supplier_risk_score = 0.45×otr + 0.20×delay + 0.20×open_delay + 0.15×stake
```

Criticality rank: low=0, medium=1, high=2, critical=3.

**Risk levels:**

| Score | Level |
|-------|-------|
| 0–25 | Low |
| 26–50 | Medium |
| > 50 | High |

Sorted worst-first (`supplier_risk_score` descending).

---

### Warning thresholds

A warning is raised if **any** condition holds:

- `on_time_rate < 88%`
- `avg_delay_days > 3 days`
- `delayed_deliveries ≥ 2`

The chart shows a **90% target** reference line for on-time rate.
""",
        "slow_movers": """
### Slow-mover detection

A product is flagged when **at least 2 of 3** conditions hold:

| Condition | Threshold |
|-----------|-----------|
| Low turnover | `stock_turnover_rate < 4.0` (annual turns) |
| Excess stock | `weeks_of_cover > 12` weeks |
| Declining demand | `demand_trend_pct < −5%` |

Two signals reduce false positives (e.g. strategic buffer stock).

---

### Tied capital

```
weekly_demand = forecast_4wk_total / 4
excess_units  = max(0, current_stock − weekly_demand × 8)
tied_capital  = excess_units × unit_cost
```

**8-week buffer** = target level; excess stock is campaign material.

Sorted by `tied_capital` descending.

---

### Suggested actions (rule chain)

1. `margin ≥ 25%` **AND** `trend < −10%` → price campaign
2. Category *Returns and refurbished* → outlet/refurb channel
3. Category *Accessories* → bundle with best-selling devices
4. `weeks_of_cover > 26` → stop replenishment, clearance campaign
5. Otherwise → campaign planning, pause replenishment
""",
        "purchases": """
### Order-up-to logic (dashboard)

Purchase recommendations use forecast and lead time:

```
REVIEW_PERIOD = 7 days (weekly report cadence)

weekly_demand  = forecast_4wk_total / 4
horizon_weeks  = (lead_time_days + 7) / 7

Criticality uplift on safety stock:
  low=0%, medium=5%, high=10%, critical=20%

target_level = weekly_demand × horizon_weeks + safety_stock × (1 + uplift)

inbound (if delivery_status = "In transit"):
  weekly_demand × 4    ← assumes ~4 weeks of demand in transit

recommended_qty = ceil(max(0, target_level − current_stock − inbound))
```

Only rows with `recommended_qty > 0` are shown.

**Estimated cost:** `recommended_qty × unit_cost`

---

### Priorities

| Condition | Priority |
|-----------|----------|
| `stockout_flag` **AND** criticality high/critical | **Urgent** |
| `stockout_flag` | **High** |
| `risk_score ≥ 50` | **Medium** |
| else | **Normal** |

Sort order: priority → risk score (descending).

---

### Recommendation reason text

Built from matching clauses:

- Stockout flag → weeks of cover vs lead time
- `current_stock ≤ reorder_point`
- `demand_trend_pct > 10%`
- `criticality_level = critical`
- Otherwise: "below order-up-to target level"
""",
        "report": """
### Report generation

Two paths:

1. **LLM path** — if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is in `.env` (currently commented out → always fallback)
2. **Rule-based** (default) — same data, structured markdown EN + FI

The report is assembled from computed analytics — no separate calculation layer.

---

### Report sections

- Executive summary (all KPIs)
- Top 5 risks (`risk_score`)
- Stockout-flagged products (max 8)
- Slow movers (max 5) + suggested actions
- Supplier warnings (max 5)
- Urgent/High purchase orders (max 8)
- KPI summary block
- 4 fixed management action bullets

---

### Export formats

- **Markdown** — both languages
- **PDF** — via `fpdf2`
- **PowerPoint** — EN + FI decks
- **Email** — optional SMTP (`.env`)
""",
        "automation": """
### RPA workflow (10 steps)

1. ERP export found (`data/erp_exports/`)
2. Data validation (12-week history, non-negative stock, lead time ≥ 1)
3.–5. Analysis pipeline (same as dashboard)
6. **Purchase recommendations** — separate RPA formula (see below)
7. PDF report (Finnish)
8. PowerPoint (EN + FI)
9. Email draft (`outbox/email_drafts/`)
10. Archive (`reports/archive/<run_id>/`)

---

### RPA vs dashboard — purchase formula

**Dashboard** uses forecast-based order-up-to logic.

**RPA export** uses a simpler rule:

```
qty = max(0, reorder_point + safety_stock − current_stock)

Priority:
  stock < safety_stock              → Urgent
  stock < reorder_point             → High
  stock < reorder_point + safety    → Medium
  else (qty > 0)                    → Low
```

The RPA table simulates ERP/RPA integration; the dashboard is more accurate for buying decisions.

---

### Stale data

If the data source changes after analysis (file `mtime` + size), a warning prompts re-running the workflow.
""",
    },
}

SECTION_ORDER = [
    "pipeline",
    "overview",
    "inventory_risk",
    "demand_forecast",
    "suppliers",
    "slow_movers",
    "purchases",
    "report",
    "automation",
]


def get_methodology_sections(lang: str) -> list[tuple[str, str]]:
    """Return (tab_label, markdown) pairs for the info page."""
    lang = lang if lang in CONTENT else "fi"
    labels = SECTION_LABELS[lang]
    return [(labels[key], CONTENT[lang][key]) for key in SECTION_ORDER]
