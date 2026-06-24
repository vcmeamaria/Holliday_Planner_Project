"""Real return-flight prices from the Amadeus Self-Service API.

Why Amadeus: Google has no public Flights API (it retired QPX in 2018), so to
get genuine airline fares in a free, reproducible project we use Amadeus, whose
self-service portal gives free API keys in minutes. If no keys are set, or a
lookup fails, the caller falls back to the scraped/mock prices, so the app still
runs with zero configuration.

How it works:
  1. Exchange the API key + secret for a short-lived OAuth token (cached).
  2. Call Flight Offers Search for a round trip and read the cheapest fare.

Note on prices: free keys default to the Amadeus TEST environment, whose fares
are representative cached data rather than always-current live prices. Set
AMADEUS_BASE_URL=https://api.amadeus.com with production keys for live fares.
"""

from __future__ import annotations

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

# test environment by default; override with AMADEUS_BASE_URL for production.
BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com").rstrip("/")
TOKEN_URL = f"{BASE_URL}/v1/security/oauth2/token"
FLIGHT_OFFERS_URL = f"{BASE_URL}/v2/shopping/flight-offers"

# where the trip starts from. A city code like "LON" covers all London airports.
ORIGIN_IATA = os.getenv("ORIGIN_IATA", "LON").upper()

# simple module-level cache for the OAuth token: {"token": str, "expires_at": float}.
_token_cache: dict = {}


def is_configured() -> bool:
    """Report whether Amadeus credentials are available.

    Takes nothing. Returns True if both AMADEUS_API_KEY and AMADEUS_API_SECRET
    are set in the environment, otherwise False.
    """
    return bool(os.getenv("AMADEUS_API_KEY") and os.getenv("AMADEUS_API_SECRET"))


def _get_access_token() -> str | None:
    """Get a valid OAuth access token, reusing a cached one until it expires.

    Takes nothing. Returns the bearer token string, or None if authentication
    isn't possible (missing keys or a failed request).
    """
    # Reuse the cached token while it still has a comfortable margin of life.
    if _token_cache.get("token") and time.time() < _token_cache.get("expires_at", 0):
        return _token_cache["token"]

    if not is_configured():
        return None

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": os.getenv("AMADEUS_API_KEY"),
                "client_secret": os.getenv("AMADEUS_API_SECRET"),
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()

        token = payload["access_token"]
        # Refresh ~60s before the real expiry so we never use a stale token.
        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + payload.get("expires_in", 1799) - 60
        return token
    except (requests.RequestException, KeyError, ValueError) as error:
        print(f"[flights] Amadeus auth failed: {error}.")
        return None


def _parse_cheapest_price(payload: dict, currency: str) -> float | None:
    """pull the cheapest grand-total fare out of a flight-offers response.

    Takes the parsed JSON payload and the expected currency. Returns the lowest
    grand total as a float, or None if the payload has no usable offers. Kept
    separate from the network call so it can be unit-tested with sample data.
    """
    offers = payload.get("data", [])
    prices: list[float] = []
    for offer in offers:
        price = offer.get("price", {})
        # grandTotal includes taxes/fees (what you actually pay); fall back to total.
        amount = price.get("grandTotal") or price.get("total")
        if amount is None:
            continue
        try:
            prices.append(float(amount))
        except (TypeError, ValueError):
            continue
    return min(prices) if prices else None


def get_return_flight_price(
    destination_iata: str,
    depart_date: str,
    return_date: str,
    currency: str = "GBP",
) -> float | None:
    """Look up the cheapest return fare to a destination.

    Takes the destination airport IATA code and the outbound/return dates
    (YYYY-MM-DD), plus an optional currency. Returns the cheapest round-trip
    price as a float in that currency, or None if Amadeus isn't configured, has
    no offers for the route, or the request fails (so the caller can fall back).
    """
    token = _get_access_token()
    if token is None:
        return None

    params = {
        "originLocationCode": ORIGIN_IATA,
        "destinationLocationCode": destination_iata,
        "departureDate": depart_date,
        "returnDate": return_date,
        "adults": 1,
        "currencyCode": currency,
        "max": 5,  # a handful of offers is enough to find the cheapest
    }

    try:
        response = requests.get(
            FLIGHT_OFFERS_URL,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return _parse_cheapest_price(response.json(), currency)
    except (requests.RequestException, ValueError) as error:
        print(f"[flights] Flight lookup failed for {destination_iata}: {error}.")
        return None
