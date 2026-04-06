import time, threading, csv, io, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from broker import DhanEquityBroker

IST = ZoneInfo("Asia/Kolkata")
app = FastAPI(title="ORB VWAP Equity Bot", root_path="/eqorb")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Config ─────────────────────────────────────
CAPITAL = 50000
MAX_RISK_PER_TRADE = 450          # Safe ~0.9%
MAX_POSITIONS = 3
VOLUME_MULTIPLIER = 1.2
PAPER_MODE = True

SCRIP_MASTER = {}
log_entries = []
bot_running = False
broker = None

def ist_now(): return datetime.now(IST)

def log(msg: str):
    entry = f"[{ist_now().strftime('%H:%M:%S')}] {msg}"
    print(entry)
    log_entries.append(entry)
    if len(log_entries) > 200: log_entries.pop(0)

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
                if sym and sym not in SCRIP_MASTER:
                    SCRIP_MASTER[sym] = int(row["SEM_SMST_SECURITY_ID"])
                    count += 1
        log(f"✅ Loaded {count} NSE Equity symbols")
    except Exception as e:
        log(f"❌ Scrip master error: {e}")

# Main Bot Loop
def bot_loop():
    global bot_running
    while bot_running:
        now = ist_now()
        if now.weekday() >= 5 or now.hour < 9 or now.hour >= 15:
            time.sleep(30)
            continue

        log(f"🔍 Scanning market for ORB + VWAP Long signals... (Paper: {PAPER_MODE})")

        # TODO: Add real 15-min candle building, ORB, VWAP, breakout detection, trailing SL here

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
    return {"ok": True, "funds": funds, "message": "Connected successfully"}

@app.get("/api/status")
def status():
    return {
        "bot_running": bot_running,
        "paper_mode": PAPER_MODE,
        "ist_time": ist_now().strftime("%H:%M:%S"),
        "active_trades": len(active_trades),
        "log": log_entries[-40:],
        "symbols": len(SCRIP_MASTER)
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
    log(f"🚀 ORB + VWAP Bot Started (Paper Mode: {PAPER_MODE})")
    return {"ok": True, "message": "Bot started"}

@app.post("/api/stop")
def stop_bot():
    global bot_running
    bot_running = False
    log("⏹️ Bot Stopped")
    return {"ok": True, "message": "Bot stopped"}

@app.post("/api/toggle_paper")
def toggle_paper(data: dict):
    global PAPER_MODE
    PAPER_MODE = data.get("paper_mode", True)
    log(f"Paper Mode set to: {PAPER_MODE}")
    return {"ok": True, "paper_mode": PAPER_MODE}

@app.post("/api/emergency_exit")
def emergency_exit():
    global bot_running
    bot_running = False
    log("⚠️ Emergency Exit triggered")
    return {"ok": True, "message": "Emergency exit triggered"}

@app.get("/")
async def root():
    return FileResponse("index.html")

if __name__ == "__main__":
    load_scrip_master()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
