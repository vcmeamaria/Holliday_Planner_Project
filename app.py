"""Holiday Planner - Streamlit single-page app. """

# import libraries

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

from src import database, flights, google_places, scraper, visualisations, weather
from src.recommender import score_destinations

# price the trip (days from today) - used for flight lookups
BOOKING_LEAD_DAYS = 30

# Constants and one-time setup

CURRENCY = "£"
DATA_FILE = Path(__file__).resolve().parent / "data" / "destinations.json"

# trips calculated for this many travellers
PEOPLE = 1

# temperature sliders default
WARM_ONLY_THRESHOLD = 25


def people_phrase(n: int) -> str:
    """Return a natural label for a traveller count: '1 person' or 'N people'."""
    return "1 person" if n == 1 else f"{n} people"

st.set_page_config(page_title="Holiday Planner", page_icon="🌴", layout="wide")


database.init_db()



# custom CSS 

def inject_css() -> None:
    """Inject the custom CSS that styles the sidebar, cards, and badges.

    Takes nothing and returns nothing. Streamlit has no native "card" component,
    so we hand-roll the look with CSS and small HTML snippets elsewhere.
    """
    st.markdown(
        """
        <style>
        /* Belt-and-suspenders light theme. The primary control is
           .streamlit/config.toml (base="light"); these rules reinforce it so
           the page still looks right even if that file is missing, and stop a
           viewer's dark browser theme from bleeding through. */
        .stApp { background-color: #FFFFFF; color: #111827; }
        /* Headings, captions, labels, and list text -> dark on white. We scope
           to layout containers (not .dest-card) so the green/score badges keep
           their own colours. */
        .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] li { color: #1F2937; }

        /* Light grey sidebar to match the reference. */
        section[data-testid="stSidebar"] { background-color: #F1F3F5; }

        /* Blue, full-width primary button. */
        section[data-testid="stSidebar"] .stButton button {
            background-color: #2563EB; color: white; border: none;
            border-radius: 8px; font-weight: 600; width: 100%;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background-color: #1D4ED8; color: white;
        }

        /* Destination card shell. */
        .dest-card {
            background: white; border: 1px solid #E5E7EB; border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow: hidden;
            margin-bottom: 8px;
        }
        /* Hero image area: a background image with a colour fallback so a broken
           photo URL never shows a broken-image icon. */
        .dest-hero {
            height: 150px; background-size: cover; background-position: center;
            background-color: #94A3B8; position: relative;
        }
        .rank-badge {
            position: absolute; top: 10px; left: 10px; background: #16A34A;
            color: white; width: 28px; height: 28px; border-radius: 6px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700;
        }
        .dest-body { padding: 14px 16px 4px 16px; }
        .dest-title-row {
            display: flex; justify-content: space-between; align-items: center;
        }
        .dest-name { font-size: 1.15rem; font-weight: 700; color: #111827; }
        .score-badge {
            background: #DCFCE7; color: #166534; font-weight: 700;
            padding: 2px 10px; border-radius: 999px; font-size: 0.85rem;
        }
        .metrics {
            display: grid; grid-template-columns: 1fr 1fr; gap: 10px 8px;
            margin-top: 12px;
        }
        .metric-val { font-weight: 700; color: #111827; }
        .metric-lbl { color: #6B7280; font-size: 0.8rem; }

        /* Cost table. */
        .cost-table { width: 100%; border-collapse: collapse; }
        .cost-table th, .cost-table td {
            text-align: left; padding: 10px 12px; border-bottom: 1px solid #E5E7EB;
            font-size: 0.9rem;
        }
        .cost-table th { color: #374151; font-weight: 600; }
        .cost-total { color: #16A34A; font-weight: 700; }

        /* About box. */
        .about-box {
            background: #F8FAFC; border: 1px solid #E5E7EB; border-radius: 12px;
            padding: 18px 20px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



# data loading and enrichment (cached so repeated clicks stay fast)

@st.cache_data(ttl=600, show_spinner=False)
def load_enriched_destinations(nights: int) -> list[dict]:
    """Load the destination shortlist and attach live data to each one.

    Takes the trip length in nights (so flight prices use the right return date,
    and so the cache refreshes when the user changes trip duration). Returns a
    list of enriched destination dicts, each merging the static JSON fields with
    weather, real/estimated flight prices, scraped hotel + daily costs, and
    places data. Cached for 10 minutes per trip length so we don't re-hit the
    APIs on every interaction.
    """
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))["destinations"]

    # Hotel + daily costs come from one scrape; flights are priced per route.
    prices = scraper.scrape_prices()

    # Price the trip a month out, returning after `nights` nights.
    depart = date.today() + timedelta(days=BOOKING_LEAD_DAYS)
    depart_str = depart.isoformat()
    return_str = (depart + timedelta(days=nights)).isoformat()

    enriched: list[dict] = []
    for dest in raw:
        wx = weather.get_weather(dest["name"], dest["latitude"], dest["longitude"])
        places = google_places.get_places(dest["name"], dest["latitude"], dest["longitude"])
        price = prices.get(
            dest["name"], {"flight": 700, "hotel_per_night": 85, "daily": 35}
        )

        # try a real Amadeus fare first; fall back to the scraped estimate

        live_flight = flights.get_return_flight_price(dest["iata"], depart_str, return_str)
        if live_flight is not None:
            flight_cost = round(live_flight)
            flight_source = "live"
        else:
            flight_cost = price["flight"]
            flight_source = "estimated"

        enriched.append(
            {
                **dest,
                "max_temp": wx["max_temp"],
                "humidity": wx["humidity"],
                "cloudiness": wx["cloudiness"],
                "wind_speed": wx["wind_speed"],
                "nightlife_spots": places["nightlife_spots"],
                "rating": places["rating"],
                "flight": flight_cost,
                "flight_source": flight_source,
                "hotel_per_night": price["hotel_per_night"],
                "daily": price["daily"],
            }
        )
    return enriched



# rendering helpers

def render_card(result: dict, rank: int) -> None:
    """Render one destination card (visual block + a details expander).

    Takes a single result dict and its 1-based rank. Returns nothing; writes
    directly to the current Streamlit column.
    """
    st.markdown(
        f"""
        <div class="dest-card">
          <div class="dest-hero" style="background-image:url('{result['photo_url']}');">
            <div class="rank-badge">{rank}</div>
          </div>
          <div class="dest-body">
            <div class="dest-title-row">
              <span class="dest-name">{result['name']}, {result['country']}</span>
              <span class="score-badge">{result['score']}/100</span>
            </div>
            <div class="metrics">
              <div><span class="metric-val">☀️ {result['max_temp']:.0f}°C</span>
                   <div class="metric-lbl">Max Temp</div></div>
              <div><span class="metric-val">💲 {CURRENCY}{result['total_cost']:,}</span>
                   <div class="metric-lbl">Total ({people_phrase(PEOPLE)})</div></div>
              <div><span class="metric-val">🍸 {result['nightlife_spots']}</span>
                   <div class="metric-lbl">Nightlife Spots</div></div>
              <div><span class="metric-val">⭐ {result['rating']}</span>
                   <div class="metric-lbl">Rating</div></div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # Streamlit can't put an interactive expander inside raw HTML - "View Details" control sits just below the card instead
    with st.expander("View Details"):
        st.write(result["reason"])
        nights = result["nights"]
        people = result["people"]
        ppl = people_phrase(people)
        flight_pp = result["flight"]
        flight_total = flight_pp * people
        hotel_total = result["hotel_per_night"] * nights
        daily_total = result["daily"] * nights * people
        flight_tag = "live fare" if result["flight_source"] == "live" else "estimate"

        if people == 1:
            flight_line = f"✈️ Flights (return): {CURRENCY}{flight_pp:,}  _({flight_tag})_"
            daily_line = (
                f"🍽️ Daily expenses: {CURRENCY}{result['daily']:,} × {nights} nights "
                f"= {CURRENCY}{daily_total:,}"
            )
        else:
            flight_line = (
                f"✈️ Flights (return): {CURRENCY}{flight_pp:,} per person, "
                f"{CURRENCY}{flight_total:,} for {people}  _({flight_tag})_"
            )
            daily_line = (
                f"🍽️ Daily (per person): {CURRENCY}{result['daily']:,} × {people} people "
                f"× {nights} nights = {CURRENCY}{daily_total:,}"
            )
        hotel_line = (
            f"🏨 Hotel: {CURRENCY}{result['hotel_per_night']:,}/night × {nights} nights "
            f"= {CURRENCY}{hotel_total:,}"
        )
        st.markdown(
            f"**Cost breakdown ({ppl}, {nights} nights)**  \n"
            f"{flight_line}  \n"
            f"{hotel_line}  \n"
            f"{daily_line}  \n"
            f"**Total ({ppl}): {CURRENCY}{result['total_cost']:,}**"
        )
        st.caption(
            f"Humidity {result['humidity']}% · Cloud {result['cloudiness']}% · "
            f"Wind {result['wind_speed']:.0f} km/h"
        )


def render_cost_table(results: list[dict], nights: int, people: int) -> None:
    """Render the cost breakdown table.

    Takes the ranked results, the trip length in nights, and the traveller count.
    Money columns are totals for the trip: flights are per-person fares × people,
    hotel is the room for the stay, and daily is per-person spend × people ×
    nights. For groups the per-person fare is shown beneath each flight total;
    for a single traveller that subtext is omitted (it would just repeat the
    total). Live (Amadeus) fares are marked with a ✓; estimates are unmarked.
    """
    rows = ""
    any_live = False
    for r in results:
        flight_total = r["flight"] * people
        hotel_total = r["hotel_per_night"] * nights
        daily_total = r["daily"] * nights * people
        tick = ""
        if r["flight_source"] == "live":
            tick = " ✓"
            any_live = True
        # only show per person  when there is more than one traveller
        if people > 1:
            flight_cell = (
                f"{CURRENCY}{flight_total:,}{tick}"
                f"<div style='font-size:0.78rem;color:#6B7280'>"
                f"{CURRENCY}{r['flight']:,} pp</div>"
            )
        else:
            flight_cell = f"{CURRENCY}{flight_total:,}{tick}"
        rows += (
            f"<tr><td>{r['name']}, {r['country']}</td>"
            f"<td>{flight_cell}</td>"
            f"<td>{CURRENCY}{hotel_total:,}</td>"
            f"<td>{CURRENCY}{daily_total:,}</td>"
            f"<td class='cost-total'>{CURRENCY}{r['total_cost']:,}</td></tr>"
        )

    if people > 1:
        flight_h = f"Flights (return, {people} ppl)"
        daily_h = f"Daily ({people} ppl, {nights} nights)"
        total_h = f"Total ({people} ppl)"
    else:
        flight_h = "Flight (Return)"
        daily_h = f"Daily ({nights} Nights)"
        total_h = "Total"

    st.markdown(
        f"""
        <table class="cost-table">
          <thead><tr>
            <th>Destination</th><th>{flight_h}</th>
            <th>Hotel ({nights} Nights)</th>
            <th>{daily_h}</th>
            <th>{total_h}</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    if people == 1:
        assumptions = f"Totals are for one traveller, for {nights} nights. "
    else:
        assumptions = (
            f"Totals are for {people} people sharing one room, for {nights} nights. "
        )
    if any_live:
        st.caption(
            assumptions
            + "✓ marks live return fares from the Amadeus API. Hotel and daily "
            "costs are scraped indicative estimates. Unmarked flights fell back "
            "to estimates."
        )
    else:
        st.caption(
            assumptions
            + "Flight, hotel, and daily costs are indicative estimates "
        )



# Sidebar

def render_sidebar() -> dict:
    """Build the preferences sidebar.

    Takes nothing. Returns a dict of the user's choices: min_temp (the effective
    minimum after applying the warm-weather preset), slider_min (the raw slider
    value), warm_only (bool), max_budget (total for the group), priorities (list),
    trip_label (str), nights (int), people (int), and search (bool).
    """
    with st.sidebar:
        st.markdown("## 🌴 Holiday Planner")
        st.caption("Find your perfect tropical getaway")
        st.markdown("### Your Preferences")

        slider_min = st.slider("Min Temperature (°C)", 20, 40, 25)
        # preset that sits on TOP of the slider: when on, it raises the effective minimum to the warm threshold (without moving the slider)
        warm_only = st.checkbox(
            f"Warm weather only ({WARM_ONLY_THRESHOLD}°C+)", value=False
        )

        # Budget is the total for the whole trip (one traveller)
        max_budget = st.slider(
            f"Max Budget ({CURRENCY}, total for {people_phrase(PEOPLE)})",
            500, 5000, 2500, step=50,
        )

        st.markdown("**What matters most to you?**")
        nightlife = st.checkbox("Nightlife (bars, clubs)", value=True)
        beaches = st.checkbox("Beaches", value=True)
        adventure = st.checkbox("Adventure Activities", value=True)

        # 4 nights is the default; other lengths remain selectable.
        trip_label = st.selectbox(
            "Trip Duration", ["4 days", "7 days", "10 days", "14 days"]
        )
        search = st.button("Find Destinations")

        # state the costing assumption 
        if PEOPLE == 1:
            st.caption("Prices shown are for one traveller.")
        else:
            st.caption(f"Prices shown are for {PEOPLE} people sharing a room.")

        st.markdown("---")
        st.caption("**Data provided by**")
        st.caption(
            "• Open-Meteo (Weather)\n\n"
            "• Google Places API (Amenities)\n\n"
            "• Amadeus API (Flight Prices)\n\n"
            "• Web Scraping (Hotel & Daily Costs)"
        )

    # translate the ticked boxes into the priority labels 
    priorities = []
    if nightlife:
        priorities.append("Nightlife")
    if beaches:
        priorities.append("Beaches")
    if adventure:
        priorities.append("Adventure")

  
    effective_min = max(slider_min, WARM_ONLY_THRESHOLD) if warm_only else slider_min

    # "4 days" -> 4 nights for the cost estimate.
    nights = int(trip_label.split()[0])

    return {
        "min_temp": effective_min,
        "slider_min": slider_min,
        "warm_only": warm_only,
        "max_budget": max_budget,
        "priorities": priorities,
        "trip_label": trip_label,
        "nights": nights,
        "people": PEOPLE,
        "search": search,
    }



# main results 

def render_results(prefs: dict) -> None:
    """Run the recommender for the given preferences and render everything.

    Takes the preferences dict from the sidebar. Returns nothing; renders cards,
    charts, the map, the cost table, and saves the search to history.
    """
    with st.spinner("Gathering weather, amenities, and live flight prices…"):
        enriched = load_enriched_destinations(prefs["nights"])
        results = score_destinations(
            enriched,
            prefs["min_temp"],
            prefs["max_budget"],
            prefs["priorities"],
            prefs["nights"],
            prefs["people"],
        )

    # The cards/expanders need the trip length and group size for the breakdown.
    for result in results:
        result["nights"] = prefs["nights"]
        result["people"] = prefs["people"]

    # save this search 
    top = results[0] if results else None
    database.insert_search(
        prefs["min_temp"], prefs["max_budget"], prefs["priorities"],
        prefs["trip_label"], top["name"] if top else None,
        top["score"] if top else None,
    )

    if not results:
        st.warning(
            "No destinations match those filters. Try lowering the minimum temperature or raising your budget."
        )
        return

    # cards
    for start in range(0, len(results), 4):
        row = results[start:start + 4]
        columns = st.columns(len(row))
        for offset, (col, result) in enumerate(zip(columns, row)):
            with col:
                render_card(result, rank=start + offset + 1)

    # charts and map 
    st.markdown("###")
    chart_col, radar_col, map_col = st.columns(3)

    with chart_col:
        st.markdown("**Weather Comparison (Max Temp °C)**")
        st.plotly_chart(
            visualisations.build_temperature_bar(results), use_container_width=True
        )

    with radar_col:
        st.markdown("**Nightlife & Amenities Comparison**")
        st.plotly_chart(
            visualisations.build_radar_chart(results), use_container_width=True
        )

    with map_col:
        st.markdown("**Destinations Map**")
        st_folium(
            visualisations.build_map(results), height=320, use_container_width=True
        )

    # score heatmap (full width)
    st.markdown("### Destination Score Heatmap")
    st.plotly_chart(
        visualisations.build_score_heatmap(results), use_container_width=True
    )
    st.caption(
        "Suitability scores (0-10) for each destination across all six factors (weighted by your priorities) to each destination's overall score."
    )

    # cost table 
    st.markdown(
        f"### Estimated Costs (for {people_phrase(prefs['people'])}, "
        f"{prefs['nights']} nights)"
    )
    render_cost_table(results, prefs["nights"], prefs["people"])

    # about box 
    st.markdown("###")
    if prefs["people"] == 1:
        cost_note = (
            f"All costs are estimated for <b>one traveller</b> for the selected "
            f"trip length (<b>{prefs['nights']} nights</b>, default 4): a return "
            f"flight, the room rate for the stay, and daily spending. Prices are "
            f"indicative and may vary."
        )
    else:
        cost_note = (
            f"All costs are estimated for <b>{people_phrase(prefs['people'])}</b> for the selected trip length (<b>{prefs['nights']} nights</b>, "
            f"default 4). Flights are per-person return fares; daily expenses are per person. Prices are indicative and may vary."
        )
    


# Page entry point

def main() -> None:
    """Wire the page together: CSS, header, sidebar, and results."""
    inject_css()
    prefs = render_sidebar()

    st.markdown("## Top Destination Recommendations 🌴")
    st.caption("Based on your preferences and current data")

    # show results on first load and on every "Find Destinations" - page is never empty
    render_results(prefs)


if __name__ == "__main__":
    main()
