"""
server.py – FastAPI backend for the Binance Futures Testnet Trading Bot.

Architecture:
    ui.html  →  FastAPI (server.py)  →  bot/client.py  →  Binance Testnet
    cli.py   →  bot/client.py        →  Binance Testnet

All order logic reuses the same bot/ package that the CLI uses.
No code is duplicated — the API is just another entry point into bot/.

Endpoints:
    POST /api/connect          – verify credentials, return account info
    POST /api/order            – place market or limit order
    GET  /api/open-orders      – list open orders for a symbol
    GET  /api/account          – fetch account balance
    GET  /api/tickers          – fetch live ticker prices
    GET  /api/logs             – return recent log lines
    GET  /health               – simple health check
"""

from __future__ import annotations

import os
import re
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# ── Bot internals ──────────────────────────────────────────────────────────
from bot.client import BinanceClient, BinanceAPIError, TESTNET_BASE_URL
from bot.orders import place_order, get_open_orders, get_account_info
from bot.validators import ValidationError
from bot.logging_config import setup_logger, LOG_DIR

load_dotenv()
logger = setup_logger("trading_bot.server")

# ── App setup ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Binance Futures Testnet Trading Bot API",
    description="FastAPI backend — bridges the browser UI to the bot/ package.",
    version="1.0.0",
)

# Allow the browser UI (any origin in dev; lock this down in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory client store (per session via headers) ──────────────────────
# We don't store secrets server-side between requests.
# The UI sends key+secret with every request; we build a fresh client each time.
# This is intentional — the server is stateless w.r.t. credentials.


def _make_client(api_key: str, api_secret: str) -> BinanceClient:
    """Build a BinanceClient from the provided credentials."""
    if not api_key or not api_secret:
        raise HTTPException(status_code=401, detail="API key and secret are required.")
    return BinanceClient(api_key=api_key, api_secret=api_secret, base_url=TESTNET_BASE_URL)


def _get_creds(request: Request) -> tuple[str, str]:
    """Extract API credentials from request headers."""
    key    = request.headers.get("X-API-Key", "").strip()
    secret = request.headers.get("X-API-Secret", "").strip()
    return key, secret


# ── Pydantic models ───────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    api_key:    str = Field(..., min_length=1)
    api_secret: str = Field(..., min_length=1)


class OrderRequest(BaseModel):
    symbol:     str   = Field(..., example="BTCUSDT")
    side:       str   = Field(..., example="BUY")
    order_type: str   = Field(..., alias="type", example="MARKET")
    quantity:   float = Field(..., gt=0, example=0.01)
    price:      Optional[float] = Field(None, gt=0, example=62000.0)

    class Config:
        populate_by_name = True


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Quick liveness check."""
    return {"status": "ok", "service": "trading-bot-api"}


@app.post("/api/connect")
async def connect(body: ConnectRequest):
    """
    Verify credentials against Binance Testnet and return account info.
    Called once when the user clicks 'Connect' in the UI.
    """
    logger.info("Connect attempt with key ending …%s", body.api_key[-4:])
    try:
        client = BinanceClient(
            api_key=body.api_key,
            api_secret=body.api_secret,
            base_url=TESTNET_BASE_URL,
        )
        # Ping first
        client.get("/fapi/v1/ping")
        # Then verify auth by fetching account
        raw = client.get("/fapi/v2/account", signed=True)
        logger.info("Connect OK – account verified")
        return {
            "success": True,
            "totalWalletBalance":    raw.get("totalWalletBalance"),
            "availableBalance":      raw.get("availableBalance"),
            "totalUnrealizedProfit": raw.get("totalUnrealizedProfit"),
            "totalMarginBalance":    raw.get("totalMarginBalance"),
        }
    except BinanceAPIError as exc:
        logger.error("Connect failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/order")
async def create_order(body: OrderRequest, request: Request):
    """
    Place a MARKET or LIMIT order.
    Credentials must be sent as X-API-Key and X-API-Secret headers.
    """
    api_key, api_secret = _get_creds(request)
    client = _make_client(api_key, api_secret)

    logger.info(
        "UI order request | %s %s %s qty=%s price=%s",
        body.side, body.order_type, body.symbol, body.quantity, body.price,
    )

    result = place_order(
        client=client,
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        quantity=body.quantity,
        price=body.price,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return {"success": True, "order": result["order"]}


@app.get("/api/open-orders")
async def open_orders(symbol: str, request: Request):
    """List all open orders for the given symbol."""
    api_key, api_secret = _get_creds(request)
    client = _make_client(api_key, api_secret)

    result = get_open_orders(client, symbol)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return {"success": True, "orders": result["orders"]}


@app.get("/api/account")
async def account(request: Request):
    """Fetch futures account balance and margin info."""
    api_key, api_secret = _get_creds(request)
    client = _make_client(api_key, api_secret)

    result = get_account_info(client)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    acc = result["account"]
    return {
        "success":               True,
        "totalWalletBalance":    acc.get("totalWalletBalance"),
        "availableBalance":      acc.get("availableBalance"),
        "totalUnrealizedProfit": acc.get("totalUnrealizedProfit"),
        "totalMarginBalance":    acc.get("totalMarginBalance"),
        "assets": [
            a for a in acc.get("assets", [])
            if float(a.get("walletBalance", 0)) > 0
        ],
    }


@app.get("/api/tickers")
async def tickers():
    """
    Fetch 24-hour ticker data for common futures pairs.
    No auth needed — public endpoint.
    """
    import requests as req
    try:
        r = req.get(f"{TESTNET_BASE_URL}/fapi/v1/ticker/24hr", timeout=8)
        r.raise_for_status()
        all_tickers = r.json()
        wanted = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"}
        filtered = [t for t in all_tickers if t.get("symbol") in wanted]
        return {"success": True, "tickers": filtered}
    except Exception as exc:
        logger.warning("Ticker fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Ticker fetch failed: {exc}")


@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """
    Return the last N lines from today's log file.
    Used by the UI to show real Python logs in the browser.
    """
    import glob
    import os

    log_files = sorted(glob.glob(os.path.join(LOG_DIR, "trading_bot_*.log")))
    if not log_files:
        return {"success": True, "logs": []}

    latest = log_files[-1]
    try:
        with open(latest, encoding="utf-8") as f:
            all_lines = f.readlines()
        recent = all_lines[-lines:]
        parsed = []
        for line in recent:
            line = line.rstrip()
            if not line:
                continue
            # Determine level from log line
            level = "info"
            if "| ERROR" in line or "| ERR " in line:
                level = "error"
            elif "| DEBUG" in line:
                level = "debug"
            elif "| WARNING" in line:
                level = "warning"
            elif "successfully" in line.lower() or "placed" in line.lower() or "ok" in line.lower():
                level = "success"
            parsed.append({"text": line, "level": level})
        return {"success": True, "logs": parsed}
    except Exception as exc:
        logger.error("Log read failed: %s", exc)
        return {"success": True, "logs": []}


# ── Global error handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {exc}"})


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  NEXUS Trading Bot – FastAPI Server")
    print("  ─────────────────────────────────")
    print("  API docs : http://localhost:8000/docs")
    print("  UI       : open ui.html in your browser")
    print("  ─────────────────────────────────\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
