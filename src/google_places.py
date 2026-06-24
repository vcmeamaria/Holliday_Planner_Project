"""Nightlife, restaurant, and rating data from the Google Places API.

If a GOOGLE_PLACES_API_KEY is present in the environment we make a REAL call to
the Google Places "Nearby Search" endpoint (we never fake a real response). If
the key is missing or the call fails, we fall back to realistic mock data and
say so clearly in the console, so the app keeps working with zero setup.
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

# load variables from a local .env file (if one exists) into os.environ
load_dotenv()

# legacy Places "Nearby Search" endpoint
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# search radius around each destination's centre, in metres.
SEARCH_RADIUS_M = 5000

# mock fallback values per destination
_MOCK_PLACES = {
    "Bali": {"nightlife_spots": 128, "rating": 4.6},
    "Phuket": {"nightlife_spots": 95, "rating": 4.4},
    "Cancun": {"nightlife_spots": 110, "rating": 4.3},
    "Costa Rica": {"nightlife_spots": 65, "rating": 4.5},
    "Zanzibar": {"nightlife_spots": 48, "rating": 4.2},
    "Tulum": {"nightlife_spots": 72, "rating": 4.4},
    "Ibiza": {"nightlife_spots": 150, "rating": 4.7},
    "Da Nang": {"nightlife_spots": 55, "rating": 4.3},
    "Mauritius": {"nightlife_spots": 40, "rating": 4.4},
    "Goa": {"nightlife_spots": 90, "rating": 4.4},
}


def _mock_for(name: str) -> dict:
    """Return mock places data for a destination, with a safe default.

    Takes the destination name. Returns a dict with nightlife_spots and rating.
    """
    return _MOCK_PLACES.get(name, {"nightlife_spots": 50, "rating": 4.2})


def get_places(name: str, latitude: float, longitude: float) -> dict:
    """Get nightlife count and average rating near a destination.

    Takes the destination name and its latitude/longitude.
    Returns a dict with: nightlife_spots (int), rating (float, out of 5), and a
    `source` flag of "google-places" or "mock" so the UI stays honest.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")

    if not api_key:
        print(f"[google_places] No API key set; using mock data for {name}.")
        return {**_mock_for(name), "source": "mock"}

    params = {
        "location": f"{latitude},{longitude}",
        "radius": SEARCH_RADIUS_M,
        # "night_club" focuses the search on bars/clubs
        "type": "night_club",
        "key": api_key,
    }

    try:
        response = requests.get(PLACES_NEARBY_URL, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()

        # The API reports its own status; anything other than OK / ZERO_RESULTS
        status = payload.get("status", "UNKNOWN")
        if status not in ("OK", "ZERO_RESULTS"):
            print(f"[google_places] API returned status {status} for {name}. Using mock data.")
            return {**_mock_for(name), "source": "mock"}

        results = payload.get("results", [])
        nightlife_spots = len(results)

        # average the ratings of the returned venues (those that have one).
        ratings = [place["rating"] for place in results if "rating" in place]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

        return {
            "nightlife_spots": nightlife_spots,
            "rating": avg_rating,
            "source": "google-places",
        }
    except (requests.RequestException, ValueError, KeyError) as error:
        # to not crash the app on a bad network call
        print(f"[google_places] Lookup failed for {name}: {error}. Using mock data.")
        return {**_mock_for(name), "source": "mock"}
