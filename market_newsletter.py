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
OUTPUT_DIR = os.path.join(BASE_DIR,"output")
os.makedirs(OUTPUT_DIR,exist_ok=True)

# -------------------------
# NSE SESSION
# -------------------------

session = requests.Session()

headers={
"user-agent":"Mozilla/5.0",
"accept-language":"en-US,en;q=0.9",
"accept":"application/json,text/html"
}

session.get("https://www.nseindia.com",headers=headers)

# -------------------------
# NIFTY DATA
# -------------------------

url="https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"

data=session.get(url,headers=headers).json()
time.sleep(1)

stocks=pd.DataFrame(data["data"][1:])
nifty=data["data"][0]

nifty_open=nifty.get("open","N/A")
nifty_close=nifty.get("lastPrice","N/A")
nifty_change=nifty.get("pChange","N/A")

# -------------------------
# SENSEX DATA
# -------------------------

try:

    sensex = yf.Ticker("^BSESN")

    sensex_data = sensex.history(period="1d")

    sensex_open = round(sensex_data["Open"].iloc[-1],2)
    sensex_close = round(sensex_data["Close"].iloc[-1],2)

    sensex_change = round(((sensex_close - sensex_open) / sensex_open) * 100,2)

except:

    sensex_open="N/A"
    sensex_close="N/A"
    sensex_change="N/A"

# -------------------------
# TOP GAINERS / LOSERS
# -------------------------

gainers=stocks.sort_values("pChange",ascending=False).head(5)
losers=stocks.sort_values("pChange").head(5)

# -------------------------
# MARKET BREADTH
# -------------------------

advances=(stocks["pChange"]>0).sum()
declines=(stocks["pChange"]<0).sum()

# -------------------------
# FII / DII DATA
# -------------------------

try:

    fii_url="https://www.nseindia.com/api/fiidiiTradeReact"
    fii=session.get(fii_url,headers=headers).json()
    time.sleep(1)

    fii_buy=fii[0]["buyValue"]
    fii_sell=fii[0]["sellValue"]

    dii_buy=fii[1]["buyValue"]
    dii_sell=fii[1]["sellValue"]

except:

    fii_buy=fii_sell=dii_buy=dii_sell="N/A"

# -------------------------
# OPTIONS DATA
# -------------------------

try:

    option_url="https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"

    opt=session.get(option_url,headers=headers).json()
    time.sleep(1)

    records=opt.get("records",{}).get("data",[])

    total_pe_oi=0
    total_ce_oi=0
    strike_pain={}

    for r in records:

        if "PE" in r and "CE" in r:

            pe=r["PE"]["openInterest"]
            ce=r["CE"]["openInterest"]

            total_pe_oi+=pe
            total_ce_oi+=ce

            strike=r["strikePrice"]
            strike_pain[strike]=abs(pe-ce)

    if total_ce_oi!=0:
        pcr=round(total_pe_oi/total_ce_oi,2)
    else:
        pcr="N/A"

    if strike_pain:
        max_pain=min(strike_pain,key=strike_pain.get)
    else:
        max_pain="N/A"

except:

    pcr="N/A"
    max_pain="N/A"

# -------------------------
# INDIA VIX
# -------------------------

try:

    vix_url="https://www.nseindia.com/api/equity-stockIndices?index=INDIA%20VIX"

    vix=session.get(vix_url,headers=headers).json()
    time.sleep(1)

    vix_value=vix["data"][0]["lastPrice"]
    vix_change=vix["data"][0]["pChange"]

except:

    vix_value="N/A"
    vix_change="N/A"

# -------------------------
# SECTOR ROTATION
# -------------------------

sector_list=[
"NIFTY BANK","NIFTY IT","NIFTY FMCG","NIFTY AUTO",
"NIFTY PHARMA","NIFTY METAL","NIFTY REALTY",
"NIFTY MEDIA","NIFTY PSU BANK","NIFTY FIN SERVICE"
]

sector_data=[]

for sector in sector_list:

    try:

        url=f"https://www.nseindia.com/api/equity-stockIndices?index={sector.replace(' ','%20')}"

        s=session.get(url,headers=headers).json()
        time.sleep(1)

        index=s["data"][0]

        sector_data.append({
            "sector":sector,
            "change":index["pChange"]
        })

    except:
        pass

sector_df=pd.DataFrame(sector_data)

avg_change=sector_df["change"].mean()

def classify(row):

    if row["change"]>avg_change and row["change"]>0:
        return "Leading"
    elif row["change"]>0:
        return "Improving"
    elif row["change"]<avg_change:
        return "Lagging"
    else:
        return "Weakening"

sector_df["stage"]=sector_df.apply(classify,axis=1)

leading=sector_df[sector_df["stage"]=="Leading"]
improving=sector_df[sector_df["stage"]=="Improving"]
weakening=sector_df[sector_df["stage"]=="Weakening"]
lagging=sector_df[sector_df["stage"]=="Lagging"]

# -------------------------
# BREAKOUT SCANNER
# -------------------------

def breakout_scan(symbols):

    breakouts=[]

    for s in symbols[:25]:

        try:

            ticker=yf.Ticker(s+".NS")
            df=ticker.history(period="1mo")

            if len(df)>0 and df["Close"].iloc[-1]>=df["Close"].max():
                breakouts.append(s)

        except:
            pass

    return breakouts

breakout_stocks=breakout_scan(stocks["symbol"].tolist())

# -------------------------
# MARKET NEWS
# -------------------------

news=feedparser.parse(
"https://news.google.com/rss/search?q=Indian+stock+market"
)

news_list=[]

for entry in news.entries[:5]:
    news_list.append(entry.title)

news_text=""

for n in news_list:
    news_text+=f"• {n}\n"

# -------------------------
# CHARTS
# -------------------------

if not sector_df.empty:

    plt.figure(figsize=(8,4))
    plt.bar(sector_df["sector"],sector_df["change"])
    plt.xticks(rotation=45)
    plt.title("Sector Performance")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR,"sector_chart.png"))
    plt.close()

plt.figure(figsize=(8,4))
plt.bar(gainers["symbol"],gainers["pChange"])
plt.title("Top Gainers")
plt.savefig(os.path.join(OUTPUT_DIR,"gainers_chart.png"))
plt.close()

# -------------------------
# AI STYLE MARKET COMMENTARY
# -------------------------

try:

    top_sector=leading.iloc[0]["sector"]
    worst_sector=lagging.iloc[0]["sector"]

    top_stock=gainers.iloc[0]["symbol"]
    worst_stock=losers.iloc[0]["symbol"]

    commentary=f"""
Markets closed with Nifty at {nifty_close} ({nifty_change}%).
Strength was visible in {top_sector} while {worst_sector} remained under pressure.

Among individual stocks, {top_stock} emerged as the top gainer,
whereas {worst_stock} was among the notable laggards.

Market breadth showed {advances} advancing stocks against {declines} declines,
indicating {'broad buying interest' if advances>declines else 'some caution in the broader market'}.

Options data shows a PCR of {pcr} with Max Pain around {max_pain},
while India VIX moved to {vix_value}, suggesting {'higher volatility' if isinstance(vix_change,float) and vix_change>0 else 'stable volatility expectations'}.
"""

except:

    commentary="Market commentary unavailable."

# -------------------------
# TABLE FORMATTER
# -------------------------

def table(df):

    text=""

    for _,row in df.iterrows():
        text+=f"{row['symbol']} ({round(row['pChange'],2)}%)\n"

    return text

def sector_table(df):

    text=""

    for _,row in df.iterrows():
        text+=f"{row['sector']} ({round(row['change'],2)}%)\n"

    return text

# -------------------------
# NEWSLETTER
# -------------------------

newsletter=f"""

After Market Report – {today}

Market Snapshot
----------------

Nifty Open : {nifty_open}
Nifty Close : {nifty_close}
Change : {nifty_change} %

Sensex Open : {sensex_open}
Sensex Close : {sensex_close}
Change : {sensex_change} %

Market Breadth
----------------

Advances : {advances}
Declines : {declines}

Top Gainers
----------------
{table(gainers)}

Top Losers
----------------
{table(losers)}

Sector Rotation
----------------

Leading Sectors
{sector_table(leading)}

Improving Sectors
{sector_table(improving)}

Weakening Sectors
{sector_table(weakening)}

Lagging Sectors
{sector_table(lagging)}

Institutional Activity
----------------

FII Buy : {fii_buy} Cr
FII Sell : {fii_sell} Cr

DII Buy : {dii_buy} Cr
DII Sell : {dii_sell} Cr

Options Data
----------------

PCR : {pcr}
Max Pain : {max_pain}

Volatility
----------------

India VIX : {vix_value}
Change : {vix_change} %

Breakout Stocks
----------------

{", ".join(breakout_stocks)}

Market Commentary
----------------

{commentary}

Market News
----------------

{news_text}

"""

file=os.path.join(OUTPUT_DIR,"newsletter.txt")

with open(file,"w") as f:
    f.write(newsletter)

print("Newsletter Generated Successfully")
print("Saved at:",file)

# -------------------------
# TELEGRAM SENDER
# -------------------------

BOT_TOKEN = "8799919200:AAHGECSqTuqyfShWxmJsgiKiqJ_TKPWTQx8"
CHAT_ID = "1776786705"

def send_telegram():

    with open(file,"r") as f:
        message=f.read()

    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload={
        "chat_id":CHAT_ID,
        "text":message
    }

    requests.post(url,data=payload)

send_telegram()

print("Newsletter sent to Telegram")