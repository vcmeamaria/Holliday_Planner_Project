"""Weather data for each destination, using the free Open-Meteo API.

Open-Meteo needs no API key, which keeps the app runnable for the whole group
with zero setup. We ask it for today's forecast (max temperature, humidity,
cloud cover, wind) at each destination's coordinates. If the network call fails
or times out, we fall back to realistic mock numbers so the app never crashes.
"""

from __future__ import annotations

import requests

# Open-Meteo's forecast endpoint
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# flip this to true to force mock data everywhere 
USE_MOCK_DATA = False


_MOCK_WEATHER = {
    "Bali": {"max_temp": 30.0, "humidity": 78, "cloudiness": 40, "wind_speed": 12.0},
    "Phuket": {"max_temp": 31.0, "humidity": 80, "cloudiness": 45, "wind_speed": 14.0},
    "Cancun": {"max_temp": 29.0, "humidity": 74, "cloudiness": 35, "wind_speed": 16.0},
    "Costa Rica": {"max_temp": 28.0, "humidity": 82, "cloudiness": 55, "wind_speed": 10.0},
    "Zanzibar": {"max_temp": 30.0, "humidity": 76, "cloudiness": 30, "wind_speed": 18.0},
    "Tulum": {"max_temp": 30.0, "humidity": 75, "cloudiness": 38, "wind_speed": 15.0},
    "Ibiza": {"max_temp": 28.0, "humidity": 65, "cloudiness": 20, "wind_speed": 16.0},
    "Da Nang": {"max_temp": 31.0, "humidity": 80, "cloudiness": 50, "wind_speed": 12.0},
    "Mauritius": {"max_temp": 27.0, "humidity": 72, "cloudiness": 35, "wind_speed": 20.0},
    "Goa": {"max_temp": 32.0, "humidity": 78, "cloudiness": 45, "wind_speed": 14.0},
}


def _mock_for(name: str) -> dict:
    """Return mock weather for a destination, with a safe default if it's unknown.

    Takes the destination name. Returns a dict with max_temp, humidity,
    cloudiness, and wind_speed.
    """
    return _MOCK_WEATHER.get(
        name, {"max_temp": 29.0, "humidity": 75, "cloudiness": 40, "wind_speed": 12.0}
    )


def get_weather(name: str, latitude: float, longitude: float) -> dict:
    """Fetch current/forecast weather for one destination from Open-Meteo.

    Takes the destination name and its latitude/longitude.
    Returns a dict with: max_temp (°C, today's forecast high), humidity (%),
    cloudiness (%), wind_speed (km/h), latitude, longitude, and a `source` flag
    of either "open-meteo" or "mock" so the UI can be honest about the source.
    """
    # Respect the global override without even attempting a network call.
    if USE_MOCK_DATA:
        data = _mock_for(name)
        return {**data, "latitude": latitude, "longitude": longitude, "source": "mock"}

    # Open-Meteo for  max temperature plus current conditions
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max",
        "current": "relative_humidity_2m,cloud_cover,wind_speed_10m",
        "timezone": "auto",
        "forecast_days": 1,
    }

    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()

        # Open-Meteo returns daily values as lists
        max_temp = payload["daily"]["temperature_2m_max"][0]
        current = payload.get("current", {})

        return {
            "max_temp": float(max_temp),
            "humidity": int(current.get("relative_humidity_2m", 0)),
            "cloudiness": int(current.get("cloud_cover", 0)),
            "wind_speed": float(current.get("wind_speed_10m", 0.0)),
            "latitude": latitude,
            "longitude": longitude,
            "source": "open-meteo",
        }
    except (requests.RequestException, KeyError, IndexError, ValueError) as error:
        # Log what went wrong (never swallow it silently) and degrade to mock data.
        print(f"[weather] Open-Meteo lookup failed for {name}: {error}. Using mock data.")
        data = _mock_for(name)
        return {**data, "latitude": latitude, "longitude": longitude, "source": "mock"}
