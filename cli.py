#!/usr/bin/env python3
"""
cli.py – Command-line interface for the Binance Futures Testnet trading bot.

Usage examples:
    # Market buy
    python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

    # Limit sell
    python cli.py order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 95000

    # List open orders
    python cli.py open-orders --symbol BTCUSDT

    # Account info
    python cli.py account
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from dotenv import load_dotenv

from bot import (
    BinanceClient,
    BinanceAPIError,
    ValidationError,
    place_order,
    get_open_orders,
    get_account_info,
    setup_logger,
)

load_dotenv()
logger = setup_logger("trading_bot.cli")


# ---------------------------------------------------------------------------
# Colour helpers (graceful fallback on Windows / no-colour terminals)
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
DIM    = "\033[2m"


def _c(text: str, *codes: str) -> str:
    """Wrap text with ANSI codes only when stdout is a real TTY."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + RESET


def _header(title: str) -> None:
    width = 54
    print()
    print(_c("─" * width, DIM))
    print(_c(f"  {title}", BOLD, CYAN))
    print(_c("─" * width, DIM))


def _kv(label: str, value: str, *, highlight: bool = False) -> None:
    colour = GREEN if highlight else RESET
    print(f"  {_c(label + ':', BOLD):<28} {_c(str(value), colour)}")


def _success(msg: str) -> None:
    print(_c(f"\n  ✔  {msg}", GREEN, BOLD))


def _failure(msg: str) -> None:
    print(_c(f"\n  ✘  {msg}", RED, BOLD))


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def cmd_order(args: argparse.Namespace, client: BinanceClient) -> int:
    """Handle the `order` sub-command."""
    price: Optional[float] = args.price

    # -- Print request summary --
    _header("Order Request Summary")
    _kv("Symbol",     args.symbol)
    _kv("Side",       args.side)
    _kv("Type",       args.type)
    _kv("Quantity",   args.quantity)
    if price is not None:
        _kv("Price", price)

    logger.info(
        "CLI order request | symbol=%s side=%s type=%s qty=%s price=%s",
        args.symbol, args.side, args.type, args.quantity, price,
    )

    # -- Place order --
    result = place_order(
        client=client,
        symbol=args.symbol,
        side=args.side,
        order_type=args.type,
        quantity=args.quantity,
        price=price,
    )

    # -- Print response --
    _header("Order Response")

    if result["success"]:
        o = result["order"]
        _kv("Order ID",       o["orderId"],     highlight=True)
        _kv("Status",         o["status"],      highlight=True)
        _kv("Symbol",         o["symbol"])
        _kv("Side",           o["side"])
        _kv("Type",           o["type"])
        _kv("Original Qty",   o["origQty"])
        _kv("Executed Qty",   o["executedQty"])
        _kv("Avg Price",      o["avgPrice"] or "—")
        _kv("Limit Price",    o["price"] or "—")
        _kv("Time In Force",  o["timeInForce"] or "—")
        _kv("Client Order ID",o["clientOrderId"])
        _success("Order placed successfully!")
        print()
        return 0
    else:
        _failure(f"Order failed: {result['error']}")
        print()
        return 1


def cmd_open_orders(args: argparse.Namespace, client: BinanceClient) -> int:
    """Handle the `open-orders` sub-command."""
    _header(f"Open Orders – {args.symbol.upper()}")

    result = get_open_orders(client, args.symbol)

    if not result["success"]:
        _failure(f"Could not fetch orders: {result['error']}")
        return 1

    orders = result["orders"]
    if not orders:
        print(_c("  No open orders found.", DIM))
        print()
        return 0

    for i, o in enumerate(orders, start=1):
        print(_c(f"\n  [{i}]", BOLD, CYAN))
        _kv("Order ID",  o.get("orderId"))
        _kv("Side",      o.get("side"))
        _kv("Type",      o.get("type"))
        _kv("Price",     o.get("price"))
        _kv("Orig Qty",  o.get("origQty"))
        _kv("Status",    o.get("status"))

    print()
    return 0


def cmd_account(args: argparse.Namespace, client: BinanceClient) -> int:
    """Handle the `account` sub-command."""
    _header("Account Information")

    result = get_account_info(client)

    if not result["success"]:
        _failure(f"Could not fetch account info: {result['error']}")
        return 1

    acc = result["account"]
    _kv("Total Wallet Balance", acc.get("totalWalletBalance", "—"))
    _kv("Available Balance",    acc.get("availableBalance", "—"))
    _kv("Total Unrealised PnL", acc.get("totalUnrealizedProfit", "—"))
    _kv("Total Margin Balance", acc.get("totalMarginBalance", "—"))

    assets = [a for a in acc.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
    if assets:
        print()
        print(_c("  Non-zero asset balances:", BOLD))
        for a in assets:
            print(f"    {a['asset']:<8} {a['walletBalance']}")

    print()
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet trading bot CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py order --symbol BTCUSDT --side BUY  --type MARKET --quantity 0.01
  python cli.py order --symbol ETHUSDT --side SELL --type LIMIT  --quantity 0.1 --price 3200
  python cli.py open-orders --symbol BTCUSDT
  python cli.py account
        """,
    )

    # Global options
    parser.add_argument("--api-key",    default=None, help="Binance API key (overrides BINANCE_API_KEY env var)")
    parser.add_argument("--api-secret", default=None, help="Binance API secret (overrides BINANCE_API_SECRET env var)")
    parser.add_argument("--base-url",   default=None, help="Testnet base URL (default: https://testnet.binancefuture.com)")

    sub = parser.add_subparsers(dest="command", required=True)

    # ---- order ----
    p_order = sub.add_parser("order", help="Place a market or limit order")
    p_order.add_argument("--symbol",   required=True,              help="Trading pair, e.g. BTCUSDT")
    p_order.add_argument("--side",     required=True,              help="BUY or SELL")
    p_order.add_argument("--type",     required=True,              help="MARKET or LIMIT")
    p_order.add_argument("--quantity", required=True, type=float,  help="Order quantity in base asset")
    p_order.add_argument("--price",               type=float,      help="Limit price (required for LIMIT orders)")

    # ---- open-orders ----
    p_open = sub.add_parser("open-orders", help="List open orders for a symbol")
    p_open.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")

    # ---- account ----
    sub.add_parser("account", help="Show futures account balance and margin info")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve credentials: CLI flag > env var
    api_key    = args.api_key    or os.getenv("BINANCE_API_KEY",    "")
    api_secret = args.api_secret or os.getenv("BINANCE_API_SECRET", "")

    if not api_key or not api_secret:
        print(_c("\n  ✘  API credentials not found.", RED, BOLD))
        print(
            "     Set BINANCE_API_KEY and BINANCE_API_SECRET in a .env file\n"
            "     or pass them via --api-key / --api-secret.\n"
        )
        return 1

    from bot.client import TESTNET_BASE_URL
    base_url = args.base_url or TESTNET_BASE_URL

    client = BinanceClient(api_key=api_key, api_secret=api_secret, base_url=base_url)

    # Quick connectivity check
    if not client.test_connectivity():
        _failure("Cannot reach the Binance testnet. Check your internet connection.")
        return 1

    # Dispatch
    dispatch = {
        "order":       cmd_order,
        "open-orders": cmd_open_orders,
        "account":     cmd_account,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args, client)
    except KeyboardInterrupt:
        print("\n  Interrupted by user.")
        return 130
    except Exception as exc:
        logger.exception("Unexpected error in command '%s'", args.command)
        _failure(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
