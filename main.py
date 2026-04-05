import os, time, threading, csv, io, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from broker import DhanEquityBroker

IST = ZoneInfo("Asia/Kolkata")
app = FastAPI(title="ORB VWAP Equity - Long Only")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Config ─────────────────────────────────────
CAPITAL = 50000
MAX_RISK_PER_TRADE = 500
MAX_POSITIONS = 3
VOLUME_MULTIPLIER = 1.2   # Mild filter as you wanted

SCRIP_MASTER = {}   # symbol -> security_id for NSE_EQ
active_trades = []
log_entries = []
bot_running = False
broker = None

def ist_now(): return datetime.now(IST)

def log(msg: str):
    entry = f"[{ist_now().strftime('%H:%M:%S')}] {msg}"
    print(entry)
    log_entries.append(entry)
    if len(log_entries) > 150:
        log_entries.pop(0)

# Improved Scrip Master Loading
def load_scrip_master():
    global SCRIP_MASTER
    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    try:
        res = requests.get(url, timeout=40)
        res.raise_for_status()
        reader = csv.DictReader(io.StringIO(res.text))
        count = 0
        for row in reader:
            # Robust filter for NSE Equity
            if (row.get("SEM_EXM_EXCH_ID") == "NSE" or row.get("SEM_SEGMENT") in ["E", "EQUITY", "NSE_EQ"]) and \
               row.get("SEM_INSTRUMENT_NAME") in ["EQUITY", "Equity", ""]:
                sym = row.get("SEM_TRADING_SYMBOL", "").strip()
                if sym and sym not in SCRIP_MASTER:
                    try:
                        SCRIP_MASTER[sym] = int(row["SEM_SMST_SECURITY_ID"])
                        count += 1
                    except:
                        pass
        log(f"✅ Successfully loaded {count} NSE Equity symbols")
        if count > 0:
            sample = list(SCRIP_MASTER.keys())[:15]
            log(f"Sample symbols: {sample}")
        else:
            log("⚠️ Still 0 equity loaded - CSV structure may have changed")
    except Exception as e:
        log(f"❌ Failed to load scrip master: {e}")

# Rest of the code remains same as previous version (connect, status, start, emergency_exit, root)

@app.post("/api/connect")
async def connect(data: dict):
    global broker
    cid = data.get("client_id")
    tok = data.get("access_token")
    if not cid or not tok:
        raise HTTPException(400, "Client ID and Access Token required")
    broker = DhanEquityBroker(cid, tok)
    funds = broker.get_funds()
    log(f"✅ Connected with Client ID: {cid}")
    return {"ok": True, "funds": funds, "message": "Connected successfully"}

@app.get("/api/status")
def get_status():
    return {
        "bot_running": bot_running,
        "ist_time": ist_now().strftime("%H:%M:%S"),
        "active_trades": active_trades,
        "log": log_entries[-40:],
        "total_symbols": len(SCRIP_MASTER)
    }

@app.post("/api/start")
def start_bot():
    global bot_running
    if not broker:
        raise HTTPException(400, "Please connect first")
    bot_running = True
    threading.Thread(target=bot_loop, daemon=True).start()
    log("🚀 ORB + VWAP Bot Started (Long Only)")
    return {"ok": True, "message": "Bot started"}

@app.post("/api/emergency_exit")
def emergency_exit():
    global active_trades
    for trade in active_trades[:]:
        if broker:
            broker.place_order(trade["security_id"], trade["qty"], side="SELL")
        log(f"Emergency exit executed for {trade.get('symbol')}")
    active_trades.clear()
    return {"ok": True, "message": "All positions closed"}

@app.get("/")
async def root():
    return FileResponse("index.html")

# Bot loop (still skeleton - will expand fully once you confirm)
def bot_loop():
    while bot_running:
        time.sleep(15)   # placeholder

if __name__ == "__main__":
    load_scrip_master()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
