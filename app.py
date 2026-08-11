"""METAR Reader web application.

A small Flask app that looks up the current METAR (aviation weather
report) for an airport code and renders it as a plain-English summary.
Raw METAR data is fetched from the NOAA Aviation Weather Center API:
https://aviationweather.gov/data/api/
"""

from typing import Optional, Tuple

import requests
from flask import Flask, render_template, request

from metar_decoder import decode_metar

app = Flask(__name__)

# Public, keyless API — no credentials required.
METAR_API_URL = "https://aviationweather.gov/api/data/metar"

# Network requests should never hang indefinitely; fail fast instead.
REQUEST_TIMEOUT_SECONDS = 10


@app.template_filter("sentence_case")
def sentence_case(text: str) -> str:
    """Capitalize only the first character of a string.

    Jinja's built-in ``capitalize`` filter lowercases every character
    after the first, which mangles aviation acronyms such as "WSW" or
    "VFR". This filter preserves the rest of the string as-is.
    """
    return text[0].upper() + text[1:] if text else text


def fetch_metar(airport_code: str) -> Tuple[Optional[dict], Optional[str]]:
    """Fetch the latest raw METAR observation for a given airport code.

    Args:
        airport_code: A 3-4 letter ICAO/FAA airport identifier, e.g. "KJFK".

    Returns:
        A ``(observation, error_message)`` tuple. Exactly one of the two
        values is ``None``: ``observation`` holds the parsed JSON record
        on success, ``error_message`` holds a user-facing explanation on
        failure.

    Raises:
        requests.exceptions.RequestException: If the HTTP request itself
            fails (timeout, connection error, non-2xx status, etc.). The
            caller is expected to handle this.
    """
    not_found_message = (
        f"No METAR data found for '{airport_code}'. "
        "Check the airport code and try again."
    )

    response = requests.get(
        METAR_API_URL,
        params={"ids": airport_code, "format": "json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    # The API returns HTTP 200/204 with an empty body (rather than an
    # error) when the airport code doesn't exist or has no active report.
    if not response.text.strip():
        return None, not_found_message

    data = response.json()
    if not data:
        return None, not_found_message

    # The endpoint always returns a list; a single ID yields one record.
    return data[0], None


@app.route("/")
def index():
    """Render the search form and, if an airport code was supplied, its report."""
    airport_code = request.args.get("airport", "").strip().upper()
    result = None
    error = None

    if airport_code:
        if not (3 <= len(airport_code) <= 4) or not airport_code.isalnum():
            error = "Please enter a valid 3-4 letter airport code, e.g. KJFK."
        else:
            try:
                observation, error = fetch_metar(airport_code)
                if observation:
                    result = decode_metar(observation)
            except requests.exceptions.Timeout:
                error = "The weather service took too long to respond. Please try again."
            except requests.exceptions.RequestException:
                error = "Could not reach the weather service. Please try again later."

    return render_template(
        "index.html", airport_code=airport_code, result=result, error=error
    )


if __name__ == "__main__":
    # The Flask dev server is for local development only. For a public
    # deployment, run this app behind a production WSGI server such as
    # gunicorn (see README.md).
    app.run(debug=True)
