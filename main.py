import time, threading, csv, io, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from broker import DhanEquityBroker

IST = ZoneInfo("Asia/Kolkata")
app = FastAPI(
    title="ORB VWAP Equity Bot",
    root_path="/eqorb"          # Important for subpath
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCRIP_MASTER = {}
log_entries = []
bot_running = False
broker = None

def ist_now(): return datetime.now(IST)

def log(msg):
    entry = f"[{ist_now().strftime('%H:%M:%S')}] {msg}"
    print(entry)
    log_entries.append(entry)
    if len(log_entries) > 100: log_entries.pop(0)

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
        "log": log_entries[-30:],
        "symbols": len(SCRIP_MASTER)
    }

@app.post("/api/start")
def start_bot():
    global bot_running
    if not broker:
        raise HTTPException(400, "Connect first")
    bot_running = True
    log("🚀 Bot Started (Long Only)")
    return {"ok": True, "message": "Bot started"}

@app.post("/api/emergency_exit")
def emergency_exit():
    global bot_running
    bot_running = False
    log("⚠️ Emergency exit - bot stopped")
    return {"ok": True, "message": "Emergency exit triggered"}

@app.get("/")
async def root():
    return FileResponse("index.html")

if __name__ == "__main__":
    load_scrip_master()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
