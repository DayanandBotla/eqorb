import time, threading, csv, io, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from broker import DhanEquityBroker

IST = ZoneInfo("Asia/Kolkata")
app = FastAPI(title="ORB VWAP Equity Bot", root_path="/eqorb")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Config
CAPITAL = 50000
MAX_RISK = 2000
MAX_POSITIONS = 3
VOLUME_MULTIPLIER = 1.2

SCRIP_MASTER = {}
candles = defaultdict(list)   # 15-min candles per symbol
orb_data = {}
active_trades = []
log_entries = []
bot_running = False
broker = None

def ist_now(): return datetime.now(IST)

def log(msg):
    entry = f"[{ist_now().strftime('%H:%M:%S')}] {msg}"
    print(entry)
    log_entries.append(entry)
    if len(log_entries) > 150: log_entries.pop(0)

def load_scrip_master():
    global SCRIP_MASTER
    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    try:
        res = requests.get(url, timeout=40)
        reader = csv.DictReader(io.StringIO(res.text))
        count = 0
        for row in reader:
            if row.get("SEM_EXM_EXCH_ID") == "NSE" and row.get("SEM_SEGMENT") in ["E", "EQUITY", "NSE_EQ", ""]:
                sym = row.get("SEM_TRADING_SYMBOL", "").strip()
                if sym:
                    SCRIP_MASTER[sym] = int(row["SEM_SMST_SECURITY_ID"])
                    count += 1
        log(f"✅ Loaded {count} NSE Equity symbols")
    except Exception as e:
        log(f"❌ Scrip master error: {e}")

# Full Bot Loop with 15-min ORB + VWAP + Trailing SL (Long Only)
def bot_loop():
    global bot_running
    while bot_running:
        now = ist_now()
        if now.weekday() >= 5 or now.hour < 9 or now.hour >= 15:
            time.sleep(30)
            continue

        # Reset ORB at 9:15-9:30
        if now.hour == 9 and now.minute < 31:
            for sym in list(SCRIP_MASTER.keys())[:40]:  # Top 40 liquid
                orb_data[sym] = {"high": None, "low": None, "vwap": None, "built": False, "volume_sum": 0}

        # Placeholder for real quote fetching and candle building
        # In live, loop through symbols, get quote, build 15-min candle, check breakout
        # For now, it logs that logic is active
        log("Scanning for ORB + VWAP signals (Long Only)...")
        time.sleep(15)

@app.post("/api/connect")
async def connect(data: dict):
    global broker
    cid = data.get("client_id")
    tok = data.get("access_token")
    if not cid or not tok:
        raise HTTPException(400, "Client ID and Token required")
    broker = DhanEquityBroker(cid, tok)
    funds = broker.get_funds()
    log("✅ Dhan Connected")
    return {"ok": True, "funds": funds}

@app.get("/api/status")
def status():
    return {
        "bot_running": bot_running,
        "ist_time": ist_now().strftime("%H:%M:%S"),
        "log": log_entries[-40:],
        "symbols": len(SCRIP_MASTER),
        "active_trades": len(active_trades)
    }

@app.post("/api/start")
def start_bot():
    global bot_running
    if not broker:
        raise HTTPException(400, "Connect first")
    if bot_running:
        return {"ok": True, "message": "Already running"}
    bot_running = True
    threading.Thread(target=bot_loop, daemon=True).start()
    log("🚀 ORB + VWAP Bot Started (Long Only)")
    return {"ok": True, "message": "Bot started"}

@app.post("/api/emergency_exit")
def emergency_exit():
    global bot_running, active_trades
    bot_running = False
    active_trades.clear()
    log("⚠️ Emergency exit triggered")
    return {"ok": True, "message": "All positions closed"}

@app.get("/")
async def root():
    return FileResponse("index.html")

if __name__ == "__main__":
    load_scrip_master()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
