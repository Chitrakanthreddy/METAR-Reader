"""Shared pytest fixtures: a Flask test client, mock METAR observations,
and a helper for stubbing out the aviationweather.gov API call.

Living at the project root (rather than inside tests/) ensures pytest
adds this directory to sys.path, so `import app` resolves correctly
regardless of where pytest is invoked from.
"""

import pytest

from app import app as flask_app


@pytest.fixture
def client():
    """A Flask test client for issuing requests against the app in-process."""
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client


class FakeResponse:
    """A minimal stand-in for requests.Response, just enough for fetch_metar()."""

    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self):
        import json

        return json.loads(self.text)


@pytest.fixture
def mock_metar_api(monkeypatch):
    """Stub out the network call made by app.fetch_metar().

    Returns a configurator function so each test can decide how the
    "API" should respond:

        mock_metar_api(observation=some_dict)          # a normal reading
        mock_metar_api(not_found=True)                 # empty body (204)
        mock_metar_api(raise_exc=requests.exceptions.Timeout())

    The configurator returns the list of `params` dicts the fake `get`
    was called with, so tests can assert on what airport code was requested.
    """

    calls = []

    def _configure(observation=None, not_found=False, raise_exc=None):
        import json

        def fake_get(url, params=None, timeout=None):
            calls.append(params)
            if raise_exc is not None:
                raise raise_exc
            if not_found or observation is None:
                # Mirrors the real API's behavior for an unknown/inactive
                # station: HTTP 200/204 with an empty body.
                return FakeResponse(text="", status_code=200)
            return FakeResponse(text=json.dumps([observation]), status_code=200)

        monkeypatch.setattr("app.requests.get", fake_get)
        return calls

    return _configure


@pytest.fixture
def clear_day_observation():
    """A calm, cloudless VFR day at Phoenix Sky Harbor."""
    return {
        "icaoId": "KPHX",
        "name": "Phoenix Sky Harbor Intl, AZ, US",
        "rawOb": "METAR KPHX 111751Z 18005KT 10SM CLR 32/05 A1015",
        "temp": 32.2,
        "dewp": 5.0,
        "wdir": 180,
        "wspd": 5,
        "wgst": None,
        "visib": "10+",
        "clouds": [],
        "cover": "CLR",
        "altim": 1015.0,
        "fltCat": "VFR",
        "reportTime": "2026-08-11T17:51:00Z",
    }


@pytest.fixture
def thunderstorm_observation():
    """A severe thunderstorm with gusty wind and low visibility at Miami Intl."""
    return {
        "icaoId": "KMIA",
        "name": "Miami Intl, FL, US",
        "rawOb": "METAR KMIA 111800Z 20020G35KT 1SM +TSRA OVC005 28/24 A0995",
        "temp": 28.0,
        "dewp": 24.0,
        "wdir": 200,
        "wspd": 20,
        "wgst": 35,
        "visib": "1",
        "wxString": "+TSRA",
        "clouds": [{"cover": "OVC", "base": 500}],
        "cover": "OVC",
        "altim": 995.0,
        "fltCat": "LIFR",
        "reportTime": "2026-08-11T18:00:00Z",
    }


@pytest.fixture
def calm_wind_observation():
    """Calm (0 kt) wind at Denver Intl."""
    return {
        "icaoId": "KDEN",
        "name": "Denver Intl, CO, US",
        "rawOb": "METAR KDEN 111700Z 00000KT 10SM FEW030 15/M02 A1013",
        "temp": 15.0,
        "dewp": -2.0,
        "wdir": 0,
        "wspd": 0,
        "visib": "10+",
        "clouds": [{"cover": "FEW", "base": 3000}],
        "cover": "FEW",
        "altim": 1013.0,
        "fltCat": "VFR",
        "reportTime": "2026-08-11T17:00:00Z",
    }


@pytest.fixture
def variable_wind_observation():
    """Variable-direction wind at Chicago O'Hare."""
    return {
        "icaoId": "KORD",
        "name": "Chicago O'Hare Intl, IL, US",
        "rawOb": "METAR KORD 111650Z VRB08KT 6SM SCT040 20/12 A1010",
        "temp": 20.0,
        "dewp": 12.0,
        "wdir": "VRB",
        "wspd": 8,
        "visib": "6",
        "clouds": [{"cover": "SCT", "base": 4000}],
        "cover": "SCT",
        "altim": 1010.0,
        "fltCat": "MVFR",
        "reportTime": "2026-08-11T16:50:00Z",
    }
