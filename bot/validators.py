"""
validators.py – Input validation for order parameters.

All validation logic lives here so both the CLI and any future UI / API layer
can call the same functions without duplicating rules.
"""

from __future__ import annotations

from typing import Optional


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT"}

# Binance minimum notional / qty sanity checks (rough guards only;
# the exchange will enforce its own filters and we surface those errors clearly)
MIN_QUANTITY = 0.001
MAX_SYMBOL_LENGTH = 20


class ValidationError(ValueError):
    """Raised when user-supplied order parameters fail validation."""


def validate_symbol(symbol: str) -> str:
    """Return the normalised (upper-case, stripped) symbol or raise ValidationError."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValidationError("Symbol cannot be empty.")
    if len(symbol) > MAX_SYMBOL_LENGTH:
        raise ValidationError(
            f"Symbol '{symbol}' is too long (max {MAX_SYMBOL_LENGTH} characters)."
        )
    if not symbol.isalnum():
        raise ValidationError(
            f"Symbol '{symbol}' contains invalid characters. Use only letters and digits (e.g. BTCUSDT)."
        )
    return symbol


def validate_side(side: str) -> str:
    """Return normalised side string or raise ValidationError."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """Return normalised order type or raise ValidationError."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: float | str) -> float:
    """Parse and validate quantity; raise ValidationError on bad input."""
    try:
        qty = float(quantity)
    except (TypeError, ValueError):
        raise ValidationError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValidationError(f"Quantity must be greater than zero, got {qty}.")
    if qty < MIN_QUANTITY:
        raise ValidationError(
            f"Quantity {qty} is below the minimum allowed value of {MIN_QUANTITY}."
        )
    return qty


def validate_price(price: Optional[float | str], order_type: str) -> Optional[float]:
    """
    Validate price depending on order type.
    - LIMIT orders require a positive price.
    - MARKET orders must not supply a price.
    Returns the parsed float or None.
    """
    order_type = order_type.strip().upper()

    if order_type == "LIMIT":
        if price is None:
            raise ValidationError("A price is required for LIMIT orders.")
        try:
            p = float(price)
        except (TypeError, ValueError):
            raise ValidationError(f"Price '{price}' is not a valid number.")
        if p <= 0:
            raise ValidationError(f"Price must be greater than zero, got {p}.")
        return p

    # MARKET order
    if price is not None:
        raise ValidationError(
            "Price should not be provided for MARKET orders. Remove the --price flag."
        )
    return None


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float | str,
    price: Optional[float | str] = None,
) -> dict:
    """
    Run all validators and return a clean parameter dict.
    Raises ValidationError on the first problem found.
    """
    clean_symbol = validate_symbol(symbol)
    clean_side = validate_side(side)
    clean_type = validate_order_type(order_type)
    clean_qty = validate_quantity(quantity)
    clean_price = validate_price(price, clean_type)

    params: dict = {
        "symbol": clean_symbol,
        "side": clean_side,
        "order_type": clean_type,
        "quantity": clean_qty,
    }
    if clean_price is not None:
        params["price"] = clean_price

    return params
