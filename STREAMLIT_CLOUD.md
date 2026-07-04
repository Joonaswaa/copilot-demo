# Streamlit Community Cloud — copilotdemo

Ilmainen osoite: **https://copilotdemo.streamlit.app**

## 1. GitHub (kerran)

1. Luo repo: https://github.com/new  
   - Nimi esim. `telecom-supply-chain-copilot`  
   - **Public** (ilmainen Streamlit Cloud vaatii julkisen repon)

2. Pushaa koodi:

```powershell
cd "C:\Users\etula\OneDrive\Työpöytä\Projektit\telecom_supply_chain_ai_copilot"
git remote add origin https://github.com/KAYTTAJATUNNUS/telecom-supply-chain-copilot.git
git branch -M main
git push -u origin main
```

## 2. Streamlit Cloud

1. Avaa https://share.streamlit.io  
2. Kirjaudu GitHub-tilillä  
3. **Create app**  
4. Valitse repo ja branch `main`  
5. **Main file path:** `app.py`  
6. **App URL (optional):** `copilotdemo` → julkaisu osoitteessa `https://copilotdemo.streamlit.app`  
   - Jos nimi on varattu, kokeile `copilotdemo-etula` tms.  
7. **Deploy**

Ensimmäinen build kestää noin 2–5 minuuttia.

## 3. Valinnaiset salaisuudet

Streamlit Cloud → app → **Settings → Secrets**:

```toml
# SMTP (valinnainen)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USER = "..."
SMTP_PASSWORD = "..."
REPORT_SENDER = "..."
REPORT_RECIPIENTS = "..."
```

## Huomioita

- RPA-workflow kirjoittaa tiedostoja palvelimelle; Streamlit Cloudissa ne **eivät säily** uudelleenkäynnistyksen jälkeen (demo OK).
- `.env` ei toimi pilvessä — käytä **Secrets**-välilehteä.
- Päivitys: push GitHubiin → Streamlit deployaa automaattisesti uudelleen.
