"""
orders.py – Order placement and management logic.

Sits between the raw HTTP client (client.py) and the CLI (cli.py).
Each function validates its inputs, builds the correct Binance payload,
delegates to the client, and returns a structured result dict.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .client import BinanceClient, BinanceAPIError
from .validators import validate_all, ValidationError
from .logging_config import setup_logger

logger = setup_logger("trading_bot.orders")


def _build_order_payload(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Assemble the parameter dict for the Binance /fapi/v1/order endpoint.
    Limit orders use GTC (Good Till Cancelled) time-in-force by default.
    """
    payload: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": quantity,
    }

    if order_type == "LIMIT":
        payload["price"] = price
        payload["timeInForce"] = "GTC"

    return payload


def _format_order_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the fields we care about from the raw API response.
    Returns a clean dict that's easy to display and test against.
    """
    return {
        "orderId": raw.get("orderId"),
        "symbol": raw.get("symbol"),
        "side": raw.get("side"),
        "type": raw.get("type"),
        "origQty": raw.get("origQty"),
        "executedQty": raw.get("executedQty"),
        "avgPrice": raw.get("avgPrice"),
        "price": raw.get("price"),
        "status": raw.get("status"),
        "timeInForce": raw.get("timeInForce"),
        "clientOrderId": raw.get("clientOrderId"),
        "updateTime": raw.get("updateTime"),
    }


def place_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float | str,
    price: Optional[float | str] = None,
) -> Dict[str, Any]:
    """
    Validate inputs, place an order, and return a structured result.

    Parameters
    ----------
    client      : Authenticated BinanceClient instance.
    symbol      : Trading pair, e.g. "BTCUSDT".
    side        : "BUY" or "SELL".
    order_type  : "MARKET" or "LIMIT".
    quantity    : Order size in base asset units.
    price       : Required for LIMIT orders; must be None for MARKET.

    Returns
    -------
    dict with keys: success (bool), order (dict | None), error (str | None)
    """

  
    try:
        params = validate_all(symbol, side, order_type, quantity, price)
    except ValidationError as exc:
        logger.warning("Validation failed: %s", exc)
        return {"success": False, "order": None, "error": str(exc)}

    payload = _build_order_payload(
        symbol=params["symbol"],
        side=params["side"],
        order_type=params["order_type"],
        quantity=params["quantity"],
        price=params.get("price"),
    )

    logger.info(
        "Placing %s %s order | symbol=%s | qty=%s%s",
        params["side"],
        params["order_type"],
        params["symbol"],
        params["quantity"],
        f" | price={params['price']}" if "price" in params else "",
    )

    
    try:
        raw_response = client.post("/fapi/v1/order", params=payload)
    except BinanceAPIError as exc:
        logger.error(
            "Order failed | symbol=%s | side=%s | type=%s | error=%s (code=%s)",
            params["symbol"],
            params["side"],
            params["order_type"],
            exc,
            exc.code,
        )
        return {"success": False, "order": None, "error": str(exc)}

    order = _format_order_response(raw_response)
    logger.info(
        "Order placed successfully | orderId=%s | status=%s | executedQty=%s",
        order["orderId"],
        order["status"],
        order["executedQty"],
    )

    return {"success": True, "order": order, "error": None}


def get_open_orders(client: BinanceClient, symbol: str) -> Dict[str, Any]:
    """Fetch all open orders for a given symbol."""
    try:
        symbol = symbol.strip().upper()
        raw = client.get("/fapi/v1/openOrders", params={"symbol": symbol}, signed=True)
        logger.info("Fetched %d open order(s) for %s", len(raw), symbol)
        return {"success": True, "orders": raw, "error": None}
    except BinanceAPIError as exc:
        logger.error("Failed to fetch open orders for %s: %s", symbol, exc)
        return {"success": False, "orders": [], "error": str(exc)}


def get_account_info(client: BinanceClient) -> Dict[str, Any]:
    """Fetch futures account balance/margin info."""
    try:
        raw = client.get("/fapi/v2/account", signed=True)
        logger.info("Fetched account info successfully.")
        return {"success": True, "account": raw, "error": None}
    except BinanceAPIError as exc:
        logger.error("Failed to fetch account info: %s", exc)
        return {"success": False, "account": None, "error": str(exc)}
