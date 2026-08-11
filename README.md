# METAR Reader

A small Flask web app that turns a cryptic aviation weather report (METAR)
into a plain-English summary. Type in an airport code and get back
something like:

> Mostly cloudy skies at 25,000 ft, 76°F (24°C), wind from the WSW at 10
> mph, visibility 10+ miles (excellent).

## How it works

1. You enter an airport's ICAO/FAA code (e.g. `KJFK` for New York JFK).
2. The app fetches the latest METAR observation for that airport from the
   [NOAA Aviation Weather Center API](https://aviationweather.gov/data/api/)
   (free, public, no API key required).
3. `metar_decoder.py` translates the raw, coded fields (temperature, wind,
   sky cover, visibility, present weather, etc.) into a plain-English
   summary, which is rendered on the page.

## Project structure

```
METAR-Reader/
├── app.py               # Flask routes and request handling
├── metar_decoder.py      # METAR -> plain English decoding logic
├── templates/
│   └── index.html        # Search form + results page
├── static/
│   └── style.css          # Page styling
├── tests/
│   ├── test_app.py        # Route tests (network mocked out)
│   └── test_metar_decoder.py  # Decoding logic tests
├── conftest.py            # Shared pytest fixtures and mock METAR data
├── requirements.txt
└── requirements-dev.txt
```

## Requirements

- Python 3.9+
- pip

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/<your-username>/METAR-Reader.git
   cd METAR-Reader
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the app

```bash
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser and enter an airport
code (e.g. `KJFK`, `KLAX`, `EGLL`).

> **Note:** `app.py` runs Flask's built-in development server, which is
> not intended for production use. For a public deployment, run it behind
> a production WSGI server such as [gunicorn](https://gunicorn.org/):
>
> ```bash
> pip install gunicorn
> gunicorn app:app
> ```

## Running tests

Install the dev dependencies (this also installs `requirements.txt`):

```bash
pip install -r requirements-dev.txt
```

Then run the test suite with [pytest](https://docs.pytest.org/):

```bash
pytest -v
```

Tests are split into two files:

- `tests/test_metar_decoder.py` — unit tests for the decoding logic
  (unit conversions, wind/sky/visibility phrasing, full METAR-to-summary
  decoding), using hand-built mock observations.
- `tests/test_app.py` — tests for the Flask routes, using mock METAR
  readings in place of the real aviationweather.gov API (via the
  `mock_metar_api` fixture in `conftest.py`), so the suite runs offline
  and deterministically.

To check test coverage:

```bash
pytest --cov=app --cov=metar_decoder --cov-report=term-missing
```

`.coveragerc` excludes the `if __name__ == "__main__":` dev-server
startup line, which never runs under test.

## Airport codes

The app looks up airports by their 4-letter ICAO identifier, e.g. `KJFK`
(New York JFK), `KLAX` (Los Angeles), `EGLL` (London Heathrow). U.S.
airports are usually the 3-letter FAA code prefixed with `K` (JFK →
KJFK). If a code isn't recognized, the page will let you know so you can
double-check it.

## License

No license has been chosen yet for this project.
