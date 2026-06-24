"""Charts and the map for the results area.

Returns ready-to-render objects:
  - build_temperature_bar  -> a Plotly bar chart figure (max temp per place)
  - build_radar_chart      -> a Plotly radar/spider figure (amenities per place)
  - build_map              -> a folium Map with a pin per destination

app.py passes these straight to st.plotly_chart / st_folium.
"""

from __future__ import annotations

import folium
import plotly.graph_objects as go

# palette reused across the charts
BAR_COLOUR = "#7C7BD6"
RADAR_COLOURS = ["#2563EB", "#16A34A", "#F59E0B", "#DC2626", "#7C3AED", "#0891B2"]

#five amenity axes, in the order they appear around the radar.
RADAR_AXES = ["Nightlife", "Beaches", "Affordability", "Restaurants", "Adventure"]

# six dimensions shown across the heatmap, in column order.
HEATMAP_DIMENSIONS = [
    "Temperature", "Affordability", "Nightlife", "Beaches", "Restaurants", "Adventure"
]


def build_temperature_bar(results: list[dict]) -> go.Figure:
    """Build a bar chart of max temperature per destination.

    Takes the ranked results list. Returns a Plotly Figure with one bar per
    destination, labelled with the temperature in °C.
    """
    names = [r["name"] for r in results]
    temps = [r["max_temp"] for r in results]

    figure = go.Figure(
        data=[
            go.Bar(
                x=names,
                y=temps,
                marker_color=BAR_COLOUR,
                text=[f"{t:.0f}°C" for t in temps],
                textposition="outside",
            )
        ]
    )
    figure.update_layout(
        yaxis_title="Max Temperature (°C)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        plot_bgcolor="white",
        showlegend=False,
    )
    return figure


def build_radar_chart(results: list[dict]) -> go.Figure:
    """Build a radar/spider chart comparing amenities across destinations.

    Takes the ranked results list (each item carries a `radar` dict). Returns a
    Plotly Figure with one closed line per destination across the five axes.
    """
    figure = go.Figure()

    for index, result in enumerate(results):
        radar = result["radar"]
        values = [radar[axis] for axis in RADAR_AXES]
        colour = RADAR_COLOURS[index % len(RADAR_COLOURS)]

        figure.add_trace(
            go.Scatterpolar(
                # Repeat the first point at the end so the shape closes neatly.
                r=values + [values[0]],
                theta=RADAR_AXES + [RADAR_AXES[0]],
                name=result["name"],
                line_color=colour,
                fill="toself",
                opacity=0.45,
            )
        )

    figure.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        margin=dict(l=30, r=30, t=20, b=20),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
    )
    return figure


def build_score_heatmap(results: list[dict]) -> go.Figure:
    """Build a heatmap of every destination's score across all six dimensions.

    Takes the ranked results list (each item carries a `dimension_scores` dict).
    Returns a Plotly Figure: one row per destination (best at the top), one
    column per scoring dimension, coloured by the 0-10 suitability score. This
    is the "heatmap" called for in the brief and shows at a glance where each
    destination is strong or weak — i.e. why it ranks where it does.
    """ 

    ordered = list(reversed(results))
    names = [r["name"] for r in ordered]
    z = [[r["dimension_scores"][dim] for dim in HEATMAP_DIMENSIONS] for r in ordered]

    figure = go.Figure(
        data=go.Heatmap(
            z=z,
            x=HEATMAP_DIMENSIONS,
            y=names,
            zmin=0,
            zmax=10,
            colorscale="YlGn",  # pale -> green, matching the app's accent
            colorbar=dict(title="Score", tickvals=[0, 5, 10]),
            # Print the value in each cell so the heatmap doubles as a table.
            text=z,
            texttemplate="%{text}",
            textfont={"size": 12},
            hovertemplate="%{y} — %{x}: %{z}/10<extra></extra>",
        )
    )
    figure.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=90 + 46 * len(names),  # grow with the number of destinations
        plot_bgcolor="white",
    )
    return figure


def build_map(results: list[dict]) -> folium.Map:
    """Build a folium map with a pin for each destination.

    Takes the ranked results list. Returns a folium.Map that:
      - uses Esri's World Street Map tiles, which label place names in Latin /
        English worldwide (the default OpenStreetMap tiles use each country's
        local script, e.g. Thai or Arabic), and needs no API key, and
      - frames all the pins via fit_bounds rather than a fixed world-zoom, so the
        view is bounded to the actual destinations, not centred on empty ocean.
    Each destination gets a green marker with a name tooltip and a details popup.
    """

    fmap = folium.Map(location=[0, 0], tiles=None, zoom_start=2)
    folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Street_Map/MapServer/tile/{z}/{y}/{x}"
        ),
        attr="Tiles &copy; Esri — Esri, DeLorme, NAVTEQ, and contributors",
        name="Esri World Street Map",
    ).add_to(fmap)

    for result in results:
        popup_html = (
            f"<b>{result['name']}, {result['country']}</b><br>"
            f"Score: {result['score']}/100<br>"
            f"Max temp: {result['max_temp']:.0f}°C"
        )
        folium.Marker(
            location=[result["latitude"], result["longitude"]],
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=result["name"],
            icon=folium.Icon(color="green", icon="info-sign"),
        ).add_to(fmap)

    if results:
        lats = [r["latitude"] for r in results]
        lons = [r["longitude"] for r in results]
        fmap.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(20, 20))

    return fmap
