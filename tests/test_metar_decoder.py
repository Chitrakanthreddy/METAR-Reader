"""Unit tests for the pure METAR decoding logic in metar_decoder.py.

These tests exercise the decoding functions directly with hand-built
observation dicts (no Flask, no network) — they check that each piece
of a METAR is translated into the correct plain-English phrase.
"""

import pytest

from metar_decoder import (
    c_to_f,
    decode_metar,
    decode_wx_string,
    degrees_to_compass,
    describe_sky,
    describe_visibility,
    describe_wind,
    hpa_to_inhg,
    knots_to_mph,
)


class TestUnitConversions:
    def test_c_to_f(self):
        assert c_to_f(0) == 32
        assert c_to_f(100) == 212
        assert c_to_f(-40) == -40

    def test_knots_to_mph(self):
        assert knots_to_mph(10) == pytest.approx(11.5078)

    def test_hpa_to_inhg(self):
        assert hpa_to_inhg(1013.25) == pytest.approx(29.9212, abs=1e-4)


class TestDegreesToCompass:
    @pytest.mark.parametrize(
        "degrees, expected",
        [
            (0, "N"),
            (45, "NE"),
            (90, "E"),
            (135, "SE"),
            (180, "S"),
            (225, "SW"),
            (270, "W"),
            (315, "NW"),
            (250, "WSW"),
            (359, "N"),  # wraps back around to North
        ],
    )
    def test_known_headings(self, degrees, expected):
        assert degrees_to_compass(degrees) == expected

    def test_none_returns_none(self):
        assert degrees_to_compass(None) is None


class TestDecodeWxString:
    @pytest.mark.parametrize(
        "wx_string, expected",
        [
            (None, []),
            ("", []),
            ("-RA", ["light rain"]),
            ("+TSRA", ["heavy thunderstorm with rain"]),
            ("BR", ["mist"]),
            ("VCSH", ["nearby showers of"]),
            ("FZFG", ["freezing fog"]),
            ("-RA BR", ["light rain", "mist"]),
        ],
    )
    def test_decodes_expected_phrases(self, wx_string, expected):
        assert decode_wx_string(wx_string) == expected


class TestDescribeWind:
    def test_calm(self):
        assert describe_wind(180, 0, None) == "calm winds"
        assert describe_wind(None, None, None) == "calm winds"

    def test_directional(self):
        assert describe_wind(250, 9, None) == "wind from the WSW at 10 mph"

    def test_variable_direction(self):
        assert describe_wind("VRB", 8, None) == "wind at 9 mph (variable direction)"

    def test_includes_gusts(self):
        assert describe_wind(200, 20, 35) == "wind from the SSW at 23 mph, gusting to 40 mph"


class TestDescribeSky:
    def test_no_clouds_falls_back_to_cover(self):
        assert describe_sky([], "CLR") == "clear skies"
        assert describe_sky(None, "SKC") == "clear skies"

    def test_picks_most_significant_layer(self):
        clouds = [{"cover": "SCT", "base": 11000}, {"cover": "BKN", "base": 25000}]
        assert describe_sky(clouds, "BKN") == "mostly cloudy skies at 25,000 ft"

    def test_formats_large_base_with_thousands_separator(self):
        clouds = [{"cover": "OVC", "base": 500}]
        assert describe_sky(clouds, "OVC") == "overcast skies at 500 ft"


class TestDescribeVisibility:
    @pytest.mark.parametrize(
        "visib, expected",
        [
            (None, None),
            ("10+", "visibility 10+ miles (excellent)"),
            ("1.5", "visibility 1.5 statute miles"),
            ("M1/4", "visibility M1/4 statute miles"),  # unparseable code passed through
        ],
    )
    def test_describes_expected_phrase(self, visib, expected):
        assert describe_visibility(visib) == expected


class TestDecodeMetar:
    def test_clear_day(self, clear_day_observation):
        result = decode_metar(clear_day_observation)

        assert result["station_name"] == "Phoenix Sky Harbor Intl, AZ, US"
        assert result["temperature_f"] == 90
        assert result["temperature_c"] == 32
        assert result["sky"] == "clear skies"
        assert result["wind"] == "wind from the S at 6 mph"
        assert result["visibility"] == "visibility 10+ miles (excellent)"
        assert result["weather"] is None
        assert result["flight_category_text"] == "good flying conditions"
        assert result["summary"] == (
            "Clear skies, 90°F (32°C), wind from the S at 6 mph, "
            "visibility 10+ miles (excellent)."
        )

    def test_thunderstorm_leads_with_weather_not_sky(self, thunderstorm_observation):
        result = decode_metar(thunderstorm_observation)

        assert result["weather"] == "heavy thunderstorm with rain"
        assert result["sky"] == "overcast skies at 500 ft"
        assert result["wind"] == "wind from the SSW at 23 mph, gusting to 40 mph"
        assert result["flight_category_text"] == (
            "very poor flying conditions (very low visibility/ceiling)"
        )
        # Active weather takes precedence over sky cover in the summary.
        assert result["summary"].startswith("Heavy thunderstorm with rain,")

    def test_calm_wind(self, calm_wind_observation):
        result = decode_metar(calm_wind_observation)
        assert result["wind"] == "calm winds"
        assert "calm winds" in result["summary"]

    def test_variable_wind(self, variable_wind_observation):
        result = decode_metar(variable_wind_observation)
        assert result["wind"] == "wind at 9 mph (variable direction)"

    def test_missing_optional_fields_do_not_crash(self):
        minimal_observation = {
            "icaoId": "KABQ",
            "rawOb": "METAR KABQ 111600Z AUTO",
            "temp": 18.0,
        }

        result = decode_metar(minimal_observation)

        assert result["station_name"] == "KABQ"
        assert result["temperature_f"] == 64
        assert result["wind"] == "calm winds"
        assert result["sky"] == "clear skies"
        assert result["dewpoint_f"] is None
        assert result["visibility"] is None
        assert result["altimeter_inhg"] is None
        assert result["flight_category_text"] is None
