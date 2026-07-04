# Julkaisu omalla domainilla

Suositus: **Render.com** (ilmainen taso + oma domain CNAME:llä) tai **Streamlit Community Cloud** (nopein, mutta oma domain vaatii yleensä maksullisen Streamlit Cloud -tilin).

---

## Vaihtoehto A — Render + oma domain (suositus)

### 1. GitHub-repositorio

```powershell
cd telecom_supply_chain_ai_copilot
git init
git add .
git commit -m "Initial deploy: Supply Chain AI Copilot"
```

Luo tyhjä repo GitHubissa (esim. `telecom-supply-chain-ai-copilot`), sitten:

```powershell
git remote add origin https://github.com/KAYTTAJATUNNUS/telecom-supply-chain-ai-copilot.git
git branch -M main
git push -u origin main
```

### 2. Render-palvelu

1. Rekisteröidy [render.com](https://render.com)
2. **New → Blueprint**
3. Yhdistä GitHub-repo → Render lukee `render.yaml`
4. Odota build (2–5 min)
5. Saat osoitteen: `https://telecom-supply-chain-copilot.onrender.com`

### 3. Oma domain (esim. `copilot.sinunyritys.fi`)

Render-dashboardissa: **Settings → Custom Domains → Add**

Render antaa CNAME-tavoitteen, esim.:

```
telecom-supply-chain-copilot.onrender.com
```

Domain-rekisteröijässä (GoDaddy, Cloudflare, Namecheap, …):

| Tyyppi | Nimi | Arvo |
|--------|------|------|
| CNAME | `copilot` (tai `@` jos apex) | `....onrender.com` |

DNS:n propagointi kestää yleensä 5–60 min. Render myöntää automaattisesti **Let's Encrypt -SSL:n**.

**Huom:** Ilmaisella Render-planilla palvelu **nukkuu** ~15 min käyttämättömyyden jälkeen — ensimmäinen lataus voi kestää ~30 s.

---

## Vaihtoehto B — Streamlit Community Cloud

1. Push koodi GitHubiin (yllä)
2. [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Repo, branch `main`, main file: **`app.py`**
4. Saat osoitteen: `https://<app>.streamlit.app`

Oma domain: Streamlit Cloud **Team** -tila → Custom domain -asetus. Ilmaisversiossa vain `*.streamlit.app` -osoite.

---

## Vaihtoehto C — Docker (VPS / Azure / AWS)

```bash
docker build -t supply-chain-copilot .
docker run -p 8501:8501 supply-chain-copilot
```

Nginx reverse proxy + Let's Encrypt edessä domainille.

---

## Ympäristömuuttujat (valinnainen)

Tuotannossa `.env` **ei** kuulu repoon. Renderissä: **Environment → Add Environment Variable**

| Muuttuja | Käyttö |
|----------|--------|
| `SMTP_HOST` … | Sähköpostilähetys (valinnainen) |
| `ANTHROPIC_API_KEY` | LLM-raportti (valinnainen) |

---

## RPA / tiedostot pilvessä

Automation Center kirjoittaa raportit palvelimen levytilaan ajon ajaksi. Renderin ilmaisella planilla levy on **ephemeral** — tiedostot katoavat uudelleenkäynnistyksessä. Demo-käyttöön OK; tuotantoon tarvitaan S3/Azure Blob tai Render Persistent Disk.

---

## Tarkistus ennen pushia

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Avaa paikallisesti: http://localhost:8501
