import requests
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import os
import yfinance as yf
import feedparser
import time

today = datetime.date.today()

# -------------------------
# OUTPUT FOLDER
# -------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------
# TELEGRAM CONFIG (FROM GITHUB SECRETS)
# -------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# -------------------------
# NSE SESSION
# -------------------------

session = requests.Session()

headers = {
    "user-agent": "Mozilla/5.0",
    "accept-language": "en-US,en;q=0.9",
    "accept": "application/json,text/html"
}

session.get("https://www.nseindia.com", headers=headers, timeout=10)

# -------------------------
# NIFTY DATA
# -------------------------

url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"

data = session.get(url, headers=headers, timeout=10).json()
time.sleep(1)

stocks = pd.DataFrame(data["data"][1:])
nifty = data["data"][0]

nifty_open = nifty.get("open", "N/A")
nifty_close = nifty.get("lastPrice", "N/A")
nifty_change = nifty.get("pChange", "N/A")

# -------------------------
# SENSEX DATA
# -------------------------

try:
    sensex = yf.Ticker("^BSESN")
    sensex_data = sensex.history(period="1d")

    sensex_open = round(sensex_data["Open"].iloc[-1], 2)
    sensex_close = round(sensex_data["Close"].iloc[-1], 2)

    sensex_change = round(((sensex_close - sensex_open) / sensex_open) * 100, 2)

except:
    sensex_open = sensex_close = sensex_change = "N/A"

# -------------------------
# TOP GAINERS / LOSERS
# -------------------------

gainers = stocks.sort_values("pChange", ascending=False).head(5)
losers = stocks.sort_values("pChange").head(5)

# -------------------------
# MARKET BREADTH
# -------------------------

advances = (stocks["pChange"] > 0).sum()
declines = (stocks["pChange"] < 0).sum()

# -------------------------
# FII / DII DATA
# -------------------------

try:
    fii_url = "https://www.nseindia.com/api/fiidiiTradeReact"
    fii = session.get(fii_url, headers=headers, timeout=10).json()
    time.sleep(1)

    fii_buy = fii[0]["buyValue"]
    fii_sell = fii[0]["sellValue"]

    dii_buy = fii[1]["buyValue"]
    dii_sell = fii[1]["sellValue"]

except:
    fii_buy = fii_sell = dii_buy = dii_sell = "N/A"

# -------------------------
# OPTIONS DATA
# -------------------------

try:
    option_url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    opt = session.get(option_url, headers=headers, timeout=10).json()
    time.sleep(1)

    records = opt.get("records", {}).get("data", [])

    total_pe_oi = 0
    total_ce_oi = 0
    strike_pain = {}

    for r in records:
        if "PE" in r and "CE" in r:
            pe = r["PE"]["openInterest"]
            ce = r["CE"]["openInterest"]

            total_pe_oi += pe
            total_ce_oi += ce

            strike = r["strikePrice"]
            strike_pain[strike] = abs(pe - ce)

    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi != 0 else "N/A"
    max_pain = min(strike_pain, key=strike_pain.get) if strike_pain else "N/A"

except:
    pcr = max_pain = "N/A"

# -------------------------
# INDIA VIX
# -------------------------

try:
    vix_url = "https://www.nseindia.com/api/equity-stockIndices?index=INDIA%20VIX"
    vix = session.get(vix_url, headers=headers, timeout=10).json()
    time.sleep(1)

    vix_value = vix["data"][0]["lastPrice"]
    vix_change = vix["data"][0]["pChange"]

except:
    vix_value = vix_change = "N/A"

# -------------------------
# SECTOR ROTATION
# -------------------------

sector_list = [
    "NIFTY BANK","NIFTY IT","NIFTY FMCG","NIFTY AUTO",
    "NIFTY PHARMA","NIFTY METAL","NIFTY REALTY",
    "NIFTY MEDIA","NIFTY PSU BANK","NIFTY FIN SERVICE"
]

sector_data = []

for sector in sector_list:
    try:
        url = f"https://www.nseindia.com/api/equity-stockIndices?index={sector.replace(' ','%20')}"
        s = session.get(url, headers=headers, timeout=10).json()
        time.sleep(1)

        index = s["data"][0]

        sector_data.append({
            "sector": sector,
            "change": index["pChange"]
        })
    except:
        pass

sector_df = pd.DataFrame(sector_data)

if sector_df.empty:
    leading = improving = weakening = lagging = pd.DataFrame()
else:
    avg_change = sector_df["change"].mean()

    def classify(row):
        if row["change"] > avg_change and row["change"] > 0:
            return "Leading"
        elif row["change"] > 0:
            return "Improving"
        elif row["change"] < avg_change:
            return "Lagging"
        else:
            return "Weakening"

    sector_df["stage"] = sector_df.apply(classify, axis=1)

    leading = sector_df[sector_df["stage"] == "Leading"]
    improving = sector_df[sector_df["stage"] == "Improving"]
    weakening = sector_df[sector_df["stage"] == "Weakening"]
    lagging = sector_df[sector_df["stage"] == "Lagging"]

# -------------------------
# BREAKOUT SCANNER
# -------------------------

def breakout_scan(symbols):
    breakouts = []
    for s in symbols[:25]:
        try:
            df = yf.Ticker(s + ".NS").history(period="1mo")
            if len(df) > 0 and df["Close"].iloc[-1] >= df["Close"].max():
                breakouts.append(s)
        except:
            pass
    return breakouts

breakout_stocks = breakout_scan(stocks["symbol"].tolist())

# -------------------------
# MARKET NEWS
# -------------------------

news = feedparser.parse("https://news.google.com/rss/search?q=Indian+stock+market")

news_text = ""
for entry in news.entries[:5]:
    news_text += f"• {entry.title}\n"

# -------------------------
# COMMENTARY
# -------------------------

try:
    commentary = f"""
Markets closed with Nifty at {nifty_close} ({nifty_change}%).
Market breadth stood at {advances} advances vs {declines} declines.

PCR at {pcr} and VIX at {vix_value} indicate {'volatility' if isinstance(vix_change, float) and vix_change > 0 else 'stability'}.
"""
except:
    commentary = "Market commentary unavailable."

# -------------------------
# TABLE FORMATTERS
# -------------------------

def table(df):
    return "\n".join([f"{row['symbol']} ({round(row['pChange'],2)}%)" for _, row in df.iterrows()])

def sector_table(df):
    if df.empty:
        return "No data"
    return "\n".join([f"{row['sector']} ({round(row['change'],2)}%)" for _, row in df.iterrows()])

# -------------------------
# NEWSLETTER
# -------------------------

newsletter = f"""
After Market Report – {today}

Nifty: {nifty_close} ({nifty_change}%)
Sensex: {sensex_close} ({sensex_change}%)

Advances: {advances} | Declines: {declines}

Top Gainers:
{table(gainers)}

Top Losers:
{table(losers)}

Sector Leaders:
{sector_table(leading)}

FII Buy: {fii_buy} | Sell: {fii_sell}
DII Buy: {dii_buy} | Sell: {dii_sell}

PCR: {pcr} | Max Pain: {max_pain}
VIX: {vix_value} ({vix_change}%)

Breakouts:
{", ".join(breakout_stocks) if breakout_stocks else "None"}

Commentary:
{commentary}

News:
{news_text}
"""

file = os.path.join(OUTPUT_DIR, "newsletter.txt")

with open(file, "w") as f:
    f.write(newsletter)

# -------------------------
# TELEGRAM SEND (SPLIT SAFE)
# -------------------------

def send_telegram():
    with open(file, "r") as f:
        message = f.read()

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    for i in range(0, len(message), 4000):
        chunk = message[i:i+4000]

        response = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": chunk
        })

        print("Telegram Response:", response.text)
