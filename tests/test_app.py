"""Unit tests for the Flask routes in app.py.

The aviationweather.gov API is never hit in these tests — `mock_metar_api`
(see conftest.py) stubs out `requests.get` so each test controls exactly
what the "API" returns and asserts on how the page renders it.
"""

import requests


def test_index_with_no_airport_shows_empty_form(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Get Weather" in response.data
    assert b"card result" not in response.data
    assert b"card error" not in response.data


def test_valid_airport_renders_decoded_weather(client, mock_metar_api, clear_day_observation):
    calls = mock_metar_api(observation=clear_day_observation)

    response = client.get("/?airport=KPHX")
    body_lower = response.data.decode().lower()

    assert response.status_code == 200
    assert "phoenix sky harbor intl, az, us" in body_lower
    assert "90°f (32°c)" in body_lower
    assert "wind from the s at 6 mph" in body_lower
    assert "visibility 10+ miles" in body_lower
    # Confirms the airport code was actually forwarded to the API call.
    assert calls == [{"ids": "KPHX", "format": "json"}]


def test_lowercase_input_is_normalized_and_still_looked_up(
    client, mock_metar_api, clear_day_observation
):
    calls = mock_metar_api(observation=clear_day_observation)

    response = client.get("/?airport=kphx")

    assert response.status_code == 200
    assert calls == [{"ids": "KPHX", "format": "json"}]
    # The form should redisplay the code in uppercase.
    assert b'value="KPHX"' in response.data


def test_thunderstorm_reading_is_decoded(client, mock_metar_api, thunderstorm_observation):
    mock_metar_api(observation=thunderstorm_observation)

    response = client.get("/?airport=KMIA")
    body = response.data.decode()

    assert "Heavy thunderstorm with rain" in body
    assert "gusting to 40 mph" in body
    assert "LIFR" in body


def test_unrecognized_airport_code_shows_not_found_message(client, mock_metar_api):
    mock_metar_api(not_found=True)

    response = client.get("/?airport=ZZZZ")
    body = response.data.decode()

    assert response.status_code == 200
    assert "No METAR data found for &#39;ZZZZ&#39;" in body


def test_malformed_airport_code_is_rejected_without_calling_api(client, mock_metar_api):
    calls = mock_metar_api()  # would raise if actually called with a bad code

    response = client.get("/?airport=12")
    body = response.data.decode()

    assert "Please enter a valid 3-4 letter airport code" in body
    # Client-side validation should short-circuit before any network call.
    assert calls == []


def test_timeout_shows_friendly_error(client, mock_metar_api):
    mock_metar_api(raise_exc=requests.exceptions.Timeout())

    response = client.get("/?airport=KJFK")
    body = response.data.decode()

    assert "took too long to respond" in body


def test_connection_error_shows_friendly_error(client, mock_metar_api):
    mock_metar_api(raise_exc=requests.exceptions.ConnectionError())

    response = client.get("/?airport=KJFK")
    body = response.data.decode()

    assert "Could not reach the weather service" in body
