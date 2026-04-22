# NEXUS – Binance Futures Testnet Trading Bot

Ye ek simple but complete trading bot project hai jo Python me bana hai. Isme FastAPI backend, browser UI aur CLI support hai — sab ek hi core `bot/` module use karte hain (no duplicate code).

---

## Project Overview

Is project ka flow kuch aisa hai:

UI (browser) → FastAPI server → bot logic → Binance Testnet

CLI bhi same bot logic use karta hai, bas UI skip ho jata hai.

---

## Folder Structure

```
trading_bot/
│
├── bot/                # Core logic (main brain)
│   ├── client.py       # Binance API calls + signing
│   ├── orders.py       # Order handling
│   ├── validators.py   # Input validation
│   └── logging_config.py
│
├── logs/               # Logs store hote hain
│
├── server.py           # FastAPI backend
├── cli.py              # CLI tool
├── ui.html             # Browser UI
├── .env.example        # API key format
└── requirements.txt
```

---

## Setup

### 1. Binance Testnet Account

- Visit: https://testnet.binancefuture.com  
- Login karo  
- API key generate karo  

---

### 2. Install Project

```bash
git clone <repo-link>
cd trading_bot

pip install -r requirements.txt
```

---

### 3. API Keys Setup

```bash
cp .env.example .env
```

`.env` file me apni keys daalo:

```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
```

---

## Run Options

### Option 1: Web UI (Recommended)

```bash
python server.py
```

Phir:

- `ui.html` browser me open karo  
- API key + secret daalo  
- Connect karo  
- BUY / SELL use karo  

---

### Option 2: CLI

```bash
# Market Buy
python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

# Limit Sell
python cli.py order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 95000

# Open Orders
python cli.py open-orders --symbol BTCUSDT

# Account Info
python cli.py account
```

---

### Option 3: API Docs

Browser me open karo:

```
http://localhost:8000/docs
```

---

## API Endpoints

| Endpoint | Description |
|----------|------------|
| `/health` | Server check |
| `/api/connect` | API key verify |
| `/api/order` | Order place |
| `/api/open-orders` | Open orders |
| `/api/account` | Account info |
| `/api/tickers` | Market data |
| `/api/logs` | Logs fetch |

---

## Logging

- Logs `logs/` folder me save hote hain  
- Har API call aur error record hota hai  
- UI me bhi live logs dekh sakte ho  

---

## Error Handling

- Server band → UI warning  
- Invalid input → clear error  
- Binance error → exact message  
- Network issue → handled + logged  
- Missing keys → prompt  

---

## Dependencies

```
requests
fastapi
uvicorn
pydantic
python-dotenv
```

---

