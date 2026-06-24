"""Scoring and ranking logic for the Holiday Planner.

Given a list of destinations (already enriched with weather, places, and price
data in app.py) plus the user's preferences, this module:
  1. filters out anywhere too cold or too expensive,
  2. scores what's left out of 100 with a weighted blend of factors, and
  3. returns a ranked list with a plain-English reason for each pick.

The weighting deliberately leans toward whatever the user said matters to them.
"""

from __future__ import annotations

from typing import Iterable


def estimate_total_cost(destination: dict, nights: int, people: int = 1) -> int:
    """Estimate the total trip cost for the traveller(s), in GBP.

    Takes an enriched destination dict (with flight, hotel_per_night, daily), the
    number of nights, and the number of travellers (default 1). Returns the total
    estimated cost as an int.

    Cost assumptions (kept explicit so the UI can state them honestly):
      - flight is a per-person return fare        -> multiplied by `people`
      - hotel_per_night is a per-ROOM rate (a single room for the party)
                                                  -> NOT multiplied by `people`
      - daily is a per-person spend               -> multiplied by `people`
    """
    flights_total = destination.get("flight", 0) * people
    hotel_total = destination.get("hotel_per_night", 0) * nights  # one shared room
    daily_total = destination.get("daily", 0) * nights * people
    return int(flights_total + hotel_total + daily_total)


def _temperature_score(max_temp: float, min_temp: float) -> float:
    """Score how warm a place is relative to the user's minimum (0-1).

    Being exactly at the minimum scores low; being ~10°C warmer scores full
    marks. We cap at 1.0 so a heatwave doesn't dominate the overall score.
    """
    return max(0.0, min(1.0, (max_temp - min_temp) / 10.0))


def _affordability_score(total_cost: int, max_budget: int) -> float:
    """Score how cheap a trip is relative to the user's budget (0-1).

    Spending none of the budget approaches 1.0; spending all of it approaches 0.
    """
    if max_budget <= 0:
        return 0.0
    return max(0.0, min(1.0, (max_budget - total_cost) / max_budget))


def _nightlife_score(spots: int, rating: float, editorial: int) -> float:
    """Blend venue count, average rating, and editorial feel into one score (0-1).

    Counts are capped at 150 venues so a single huge city doesn't swamp the rest.
    The three signals are averaged equally.
    """
    count_part = min(1.0, spots / 150.0)
    rating_part = rating / 5.0
    editorial_part = editorial / 10.0
    return (count_part + rating_part + editorial_part) / 3.0


def score_destinations(
    destinations: Iterable[dict],
    min_temp: float,
    max_budget: int,
    priorities: list[str],
    nights: int,
    people: int = 1,
) -> list[dict]:
    """Filter, score, and rank destinations for the user's preferences.

    Takes the enriched destinations and the user's settings: minimum temperature,
    maximum budget (the total budget for the whole trip), the list of priorities
    they ticked (any of "Nightlife", "Beaches", "Adventure"), the trip length in
    nights, and the number of travellers (default 1). Both the budget filter and
    the total cost are computed for the same party size, so they compare like for
    like.

    Returns a list of result dicts sorted best-first. Each result copies the
    destination's fields and adds: total_cost (for the group), score (0-100 int),
    reason (str), radar (five 0-10 axes), and dimension_scores (six 0-10 axes).
    """
    results: list[dict] = []

    for dest in destinations:
        # Drop anywhere colder than then min benchmark
        if dest["max_temp"] < min_temp:
            continue

        total_cost = estimate_total_cost(dest, nights, people)
        # drop anywhere that blows  budget
        if total_cost > max_budget:
            continue

        # component scores 
        temp = _temperature_score(dest["max_temp"], min_temp)
        afford = _affordability_score(total_cost, max_budget)
        nightlife = _nightlife_score(
            dest["nightlife_spots"], dest["rating"], dest["nightlife_editorial_score"]
        )
        beaches = dest["beaches_score"] / 10.0          
        adventure = dest["adventure_score"] / 10.0 
        restaurants = dest["rating"] / 5.0  

        #  weights, by what the user requires
        weights = {
            "temperature": 1.0,
            "affordability": 1.0,
            "nightlife": 1.0,
            "beaches": 1.0,
            "adventure": 1.0,
            "restaurants": 1.0,
        }
        if "Nightlife" in priorities:
            weights["nightlife"] += 1.5
        if "Beaches" in priorities:
            weights["beaches"] += 1.5
        if "Adventure" in priorities:
            weights["adventure"] += 1.5

        components = {
            "temperature": temp,
            "affordability": afford,
            "nightlife": nightlife,
            "beaches": beaches,
            "adventure": adventure,
            "restaurants": restaurants,
        }

        # weighted average
        total_weight = sum(weights.values())
        weighted = sum(components[k] * weights[k] for k in components)
        score = round((weighted / total_weight) * 100)

        results.append(
            {
                **dest,
                "total_cost": total_cost,
                "score": score,
                "reason": _build_reason(components, dest),
                "radar": {
                    "Nightlife": round(nightlife * 10, 1),
                    "Beaches": round(beaches * 10, 1),
                    "Affordability": round(afford * 10, 1),
                    "Restaurants": round(restaurants * 10, 1),
                    "Adventure": round(adventure * 10, 1),
                },
                "dimension_scores": {
                    "Temperature": round(temp * 10, 1),
                    "Affordability": round(afford * 10, 1),
                    "Nightlife": round(nightlife * 10, 1),
                    "Beaches": round(beaches * 10, 1),
                    "Restaurants": round(restaurants * 10, 1),
                    "Adventure": round(adventure * 10, 1),
                },
            }
        )

    # best score first
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def _build_reason(components: dict, dest: dict) -> str:
    """Turn the strongest scoring factors into a short, readable sentence.

    Takes the 0-1 component scores and the destination dict. Returns a sentence
    like "Warm climate, strong nightlife scene, and fits within your budget."
    """
    phrases = {
        "temperature": "a warm tropical climate",
        "affordability": "a comfortable fit within your budget",
        "nightlife": "a strong nightlife scene",
        "beaches": "excellent beaches",
        "adventure": "plenty of adventure activities",
        "restaurants": "well-rated restaurants and bars",
    }

    # show the top three by score
    ranked = sorted(components.items(), key=lambda kv: kv[1], reverse=True)
    highlights = [phrases[name] for name, value in ranked[:3] if value >= 0.5]

    if not highlights:
        return f"{dest['name']} matches your filters but scores moderately overall."

    if len(highlights) == 1:
        body = highlights[0]
    else:
        body = ", ".join(highlights[:-1]) + ", and " + highlights[-1]

    return f"{dest['name']} offers {body}."
