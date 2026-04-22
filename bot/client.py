"""
client.py – Low-level Binance Futures Testnet REST client.

Handles authentication (HMAC-SHA256 signatures), request signing,
timestamping, and raw HTTP communication.  Higher-level order logic
lives in orders.py; this module is only concerned with the transport layer.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .logging_config import setup_logger

logger = setup_logger("trading_bot.client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT = 10  # seconds


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx status or an error payload."""

    def __init__(self, message: str, code: Optional[int] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code                  # Binance error code (e.g. -1121)
        self.status_code = status_code    # HTTP status code


class BinanceClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    Usage
    -----
    client = BinanceClient(api_key="...", api_secret="...")
    response = client.post("/fapi/v1/order", params={...})
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str = TESTNET_BASE_URL):
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be non-empty strings.")
        self.api_key = api_key
        self._api_secret = api_secret.encode()  # bytes for hmac
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

  

    def _timestamp(self) -> int:
        """Return current UTC timestamp in milliseconds."""
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append timestamp + HMAC-SHA256 signature to the parameter dict.
        The signature covers the entire query string.
        """
        params["timestamp"] = self._timestamp()
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret,
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse the response JSON and raise BinanceAPIError on failure."""
        try:
            data = response.json()
        except ValueError:
            raise BinanceAPIError(
                f"Non-JSON response (HTTP {response.status_code}): {response.text}",
                status_code=response.status_code,
            )

        if not response.ok:
            code = data.get("code")
            msg = data.get("msg", "Unknown error")
            logger.error("Binance API error | HTTP %s | code=%s | msg=%s", response.status_code, code, msg)
            raise BinanceAPIError(msg, code=code, status_code=response.status_code)

        return data

  

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Dict[str, Any]:
        """Send a signed or unsigned GET request."""
        params = params or {}
        if signed:
            params = self._sign(params)

        url = f"{self.base_url}{endpoint}"
        logger.debug("GET %s | params=%s", url, {k: v for k, v in params.items() if k != "signature"})

        try:
            response = self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.ConnectionError as exc:
            raise BinanceAPIError(f"Network connection failed: {exc}") from exc
        except requests.exceptions.Timeout:
            raise BinanceAPIError(f"Request timed out after {DEFAULT_TIMEOUT}s.")

        logger.debug("GET response | HTTP %s | %s", response.status_code, response.text[:400])
        return self._handle_response(response)

    def post(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a signed POST request (all order endpoints require signing)."""
        params = params or {}
        params = self._sign(params)

        url = f"{self.base_url}{endpoint}"
        # Log request without leaking the signature
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.debug("POST %s | params=%s", url, safe_params)

        try:
            response = self._session.post(url, data=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.ConnectionError as exc:
            raise BinanceAPIError(f"Network connection failed: {exc}") from exc
        except requests.exceptions.Timeout:
            raise BinanceAPIError(f"Request timed out after {DEFAULT_TIMEOUT}s.")

        logger.debug("POST response | HTTP %s | %s", response.status_code, response.text[:800])
        return self._handle_response(response)

    def test_connectivity(self) -> bool:
        """Ping the testnet to verify the connection and API key are working."""
        try:
            self.get("/fapi/v1/ping")
            logger.info("Connectivity test passed – testnet is reachable.")
            return True
        except BinanceAPIError as exc:
            logger.error("Connectivity test failed: %s", exc)
            return False
