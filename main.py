import os, json, sqlite3, threading, time, datetime
from pathlib import Path
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Inversor IA - Simulador")
ROOT = Path(__file__).parent
DB = os.getenv("INVERSOR_DB", str(ROOT / "paper.sqlite3"))
lock = threading.RLock()
ASSETS = {"BTCUSDT","ETHUSDT","SOLUSDT","AAPL","MSFT","NVDA"}
CRYPTO = {"BTCUSDT","ETHUSDT","SOLUSDT"}

def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    return db

def init():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, running INTEGER NOT NULL, cash REAL NOT NULL, initial REAL NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, qty REAL NOT NULL, avg_price REAL NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, side TEXT, qty REAL, price REAL)")
        db.execute("INSERT OR IGNORE INTO state VALUES (1,0,1000,1000)")
init()

def price(symbol):
    if symbol not in ASSETS:
        raise HTTPException(400,"Activo no admitido")
    try:
        if symbol in CRYPTO:
            data=requests.get("https://api.binance.com/api/v3/ticker/price",params={"symbol":symbol},timeout=8)
            data.raise_for_status()
            return float(data.json()["price"])
        data=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/"+symbol,params={"range":"5d","interval":"1d"},headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        data.raise_for_status()
        return float(data.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except (ValueError,KeyError,IndexError,requests.RequestException) as e:
        raise HTTPException(503,"Proveedor de cotizaciones no disponible") from e

def history(symbol):
    try:
        if symbol in CRYPTO:
            r=requests.get("https://api.binance.com/api/v3/klines",params={"symbol":symbol,"interval":"1d","limit":65},timeout=10)
            r.raise_for_status()
            return [float(x[4]) for x in r.json()]
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/"+symbol,params={"range":"6mo","interval":"1d"},headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        r.raise_for_status()
        return [float(x) for x in r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if x is not None]
    except (ValueError,KeyError,IndexError,requests.RequestException) as e:
        raise HTTPException(503,"No se pudo obtener historial") from e

def signal(closes):
    if len(closes)<50:
        return {"action":"WAIT","reason":"Historial insuficiente","confidence":None}
    short=sum(closes[-20:])/20
    long=sum(closes[-50:])/50
    delta=[closes[i]-closes[i-1] for i in range(len(closes)-14,len(closes))]
    gains=sum(max(d,0) for d in delta)/14
    losses=sum(max(-d,0) for d in delta)/14
    rsi=100 if losses==0 else 100-100/(1+gains/losses)
    action="BUY" if short>long and rsi<70 else "SELL" if short<long and rsi>30 else "WAIT"
    return {"action":action,"reason":f"SMA20={short:.4f}, SMA50={long:.4f}, RSI14={rsi:.1f}","confidence":None}

@app.get("/api/status")
def status():
    with lock, connect() as db:
        s=dict(db.execute("SELECT * FROM state WHERE id=1").fetchone())
        return {"settings":s,"positions":[dict(x) for x in db.execute("SELECT * FROM positions")],"trades":[dict(x) for x in db.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 40")]}

@app.get("/api/analyze/{symbol}")
def analyze(symbol:str):
    symbol=symbol.upper()
    if symbol not in ASSETS: raise HTTPException(400,"Activo no admitido")
    closes=history(symbol)
    if not closes: raise HTTPException(503,"Sin cotizaciones")
    return {"symbol":symbol,"price":closes[-1],**signal(closes),"disclaimer":"Señal técnica experimental, no predicción garantizada"}

@app.post("/api/start")
def start():
    with lock,connect() as db:
        db.execute("UPDATE state SET running=1 WHERE id=1")
    return {"running":True,"note":"Motor de simulación habilitado; no hay órdenes reales"}

@app.post("/api/stop")
def stop():
    with lock,connect() as db:
        db.execute("UPDATE state SET running=0 WHERE id=1")
    return {"running":False,"note":"Nuevas operaciones automáticas deshabilitadas"}

class Order(BaseModel):
    symbol:str
    side:str
    qty:float

@app.post("/api/paper-order")
def paper_order(o:Order):
    sym=o.symbol.upper()
    side=o.side.upper()
    if sym not in ASSETS or side not in ("BUY","SELL") or not (0<o.qty<1e9):
        raise HTTPException(400,"Orden inválida")
    px=price(sym)
    with lock,connect() as db:
        s=db.execute("SELECT * FROM state WHERE id=1").fetchone()
        p=db.execute("SELECT * FROM positions WHERE symbol=?",(sym,)).fetchone()
        oldqty=p["qty"] if p else 0
        if side=="BUY":
            if px*o.qty>s["cash"] or px*o.qty>max(0.1*s["initial"],0.01):
                raise HTTPException(400,"Saldo insuficiente o límite del 10% del capital inicial")
            newqty=oldqty+o.qty
            avg=((p["avg_price"]*oldqty if p else 0)+px*o.qty)/newqty
            db.execute("INSERT OR REPLACE INTO positions VALUES (?,?,?)",(sym,newqty,avg))
            db.execute("UPDATE state SET cash=cash-? WHERE id=1",(px*o.qty,))
        else:
            if oldqty+1e-9<o.qty: raise HTTPException(400,"Posición insuficiente")
            if oldqty-o.qty<1e-9: db.execute("DELETE FROM positions WHERE symbol=?",(sym,))
            else: db.execute("UPDATE positions SET qty=? WHERE symbol=?",(oldqty-o.qty,sym))
            db.execute("UPDATE state SET cash=cash+? WHERE id=1",(px*o.qty,))
        db.execute("INSERT INTO trades(timestamp,symbol,side,qty,price) VALUES (?,?,?,?,?)",(datetime.datetime.now(datetime.timezone.utc).isoformat(),sym,side,o.qty,px))
    return {"paper":True,"symbol":sym,"side":side,"qty":o.qty,"price":px}

@app.get("/")
def home():
    return FileResponse(ROOT/"web"/"index.html")
app.mount("/",StaticFiles(directory=ROOT/"web"),name="web")
