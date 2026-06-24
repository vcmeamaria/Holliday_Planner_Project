# Holiday Planner 🌴

Holiday Planner is a Streamlit application that recommends holiday destinations based on a user's budget, preferred temperature, trip length, and interests. It combines weather, cost, and amenity data to score and rank destinations, presenting the results through interactive charts, maps, and tables.

The application is designed to run without API keys, ensuring it remains easy to reproduce, assess, and deploy on Streamlit Community Cloud.

## What it does

The app starts with ten destinations from `data/destinations.json` and adds live or estimated data such as weather, nightlife, flights, hotel prices, and daily costs.

It then filters destinations based on temperature and budget, before scoring them across six factors: temperature, affordability, nightlife, beaches, restaurants, and adventure.

The results are shown as ranked cards, charts, a heatmap, a map, and a cost table. Each search is also saved to a small SQLite database.

## Setup

You need Python 3.11 - that's what `runtime.txt` pins, and it's what the dependency
versions in `requirements.txt` were tested against. Clone the repo, make a virtual
environment, and install the pinned dependencies.

Mac / Linux:

```bash
git clone <your-repo-url> Holiday_Planner_Project
cd Holiday_Planner_Project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
git clone <your-repo-url> Holiday_Planner_Project
cd Holiday_Planner_Project
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

That's enough to run it. If you want live data instead of the fallbacks, copy
`.env.example` to `.env` and fill in whichever keys you have — `cp .env.example .env`
on Mac/Linux, `copy .env.example .env` on Windows. None of the keys are required.

## Running it locally

```bash
streamlit run app.py
```
When the app starts, Streamlit opens in your browser (typically at `http://localhost:8501`).

The left-hand sidebar contains the user preferences, while the main page displays ranked destination cards, charts, maps, heatmaps, and a cost comparison table.

The app automatically loads with default settings, so results are visible immediately. Adjust any preferences and click **Find Destinations** to refresh the recommendations.

## Environment variables

The app loads settings from a `.env` file using `python-dotenv`, but it will run perfectly without one.

-   **Weather data** comes from Open-Meteo and requires no API key. Weather is fetched live when an internet connection is available, with automatic fallback to built-in sample data if the request fails.
    
-   **`GOOGLE_PLACES_API_KEY`** is optional. When provided, the app retrieves real nightlife venue data and ratings from Google Places. Without it, nightlife information comes from a predefined mock dataset, clearly identified as such.
    
-   **`AMADEUS_API_KEY`** and **`AMADEUS_API_SECRET`** are optional and must be used together. They enable real flight fare estimates through the Amadeus Self-Service API. Free keys use the Amadeus test environment, which provides representative rather than fully live fares. Without these keys, flight costs fall back to estimated values.
    
-   **`AMADEUS_BASE_URL`** can be set to the production API endpoint when using production Amadeus credentials.
    
-   **`ORIGIN_IATA`** defines the departure airport and defaults to `LON` (all London airports).
    
-   **`SCRAPER_SOURCE_URL`** allows the scraper to use a live external source instead of the bundled sample data.

## Project structure

```
Holiday_Planner_Project/
|-- app.py                  # Streamlit page: sidebar, cards, charts, map, cost table
|-- requirements.txt        # Pinned dependencies
|-- runtime.txt             # Python 3.11 pin for Streamlit Cloud
|-- .env.example            
|-- .streamlit/
│   |-- config.toml         # Forces the light theme for all users
|-- data/
│   |-- destinations.json   # destinations + scores
│   |-- sample_prices.html  
│   |-- holiday_planner.db   # SQLite search history
|-- src/
│   |-- weather.py          # Open-Meteo lookups + mock fallback
│   |-- google_places.py    # Google Places lookups + mock fallback
│   |-- flights.py          # Amadeus return-flight prices + fallback
│   |-- scraper.py          # requests + BeautifulSoup price scraping
│   |-- recommender.py      # Filtering, scoring
│   |-- database.py         # SQLite search history
│   |-- visualisations.py   # Bar chart, radar, heatmap, folium map

```

The single-traveller costing is driven by a `PEOPLE` constant at the top of `app.py`,
with a small `people_phrase()` helper handling the "1 person" vs "N people" wording
everywhere it appears. We had it briefly set to two travellers at one point and walked it
back, which is why that machinery exists even though it's currently always one.

## A note on the scraper

The web-scraping component is real `requests` + `BeautifulSoup` code - it loads an HTML
page and walks the rows of a table with `id="prices"`, pulling flight, hotel, and daily
figures out of the cells. What it scrapes by default is a small static page we bundle at
`data/sample_prices.html`. That was a judgement call. Real flight and hotel pages either
block scrapers, hide prices behind a login, or quietly rename their HTML, and any of
those would make a graded demo fail on the marker's machine through no fault of the code.
The bundled page has the same column shape a real listings page would, so if you set
`SCRAPER_SOURCE_URL` to a live URL with that layout, the exact same parsing code runs
against it with no changes. It is genuinely parsing the page, not reading a dictionary
dressed up as a scrape.

## Known limitations

-   Without a Google Places API key, amenity data is mocked. Even with a key, nightlife is only measured by the number of venues within 5 km and doesn't reflect quality or popularity.
-   Amadeus free API keys use a test environment, so flight prices are estimates rather than live fares.
-   Hotel and daily cost data come from a bundled static source, so they should be treated as indicative only.
-   Beach and adventure scores are manually assigned placeholder values and are not based on real activity data.
-   The app currently supports a fixed list of ten destinations and does not offer free-text destination search.
-   Map labels use Esri World Street Map tiles to ensure place names appear in English/Latin characters. Because destinations are spread across multiple continents, the map view remains fairly zoomed out.
-   The "View Details" button sits below each destination card due to Streamlit limitations with interactive elements inside custom HTML cards.
-   On Streamlit Cloud, search history is stored in temporary storage and will reset whenever the app restarts.

## How AI was used

Artificial Intelligence tools (including ChatGPT and Claude) were used during the development of this project as coding assistants.

AI support was used for:
-   Code improvement and debugging.
-   Guidance on technical decisions, including API selection and integration approaches.
-   Suggestions for Streamlit layout and user interface design.
-   Minor improvements to written documentation and project descriptions.
    
All code, design decisions, testing, and final implementation were reviewed, modified, and validated by the project team. AI-generated content was not used without human verification.
