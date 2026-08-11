"""METAR decoding logic.

Translates a structured METAR observation — as returned by the NOAA
Aviation Weather Center's JSON API — into a plain-English weather
summary. Working from the API's pre-parsed fields (temperature, wind,
clouds, etc.) is far more reliable than re-parsing the raw METAR text
ourselves, since the raw format has many optional and station-specific
groups.

Reference: https://aviationweather.gov/data/api/
METAR code reference: https://www.aviationweather.gov/metar/symbol
"""

from typing import Dict, List, Optional, Union

# Sky cover codes, ordered from clearest to most obscured. Also used by
# _cover_rank() below to pick the most significant cloud layer.
CLOUD_COVER = {
    "SKC": "clear skies",
    "CLR": "clear skies",
    "CAVOK": "clear skies",
    "FEW": "a few clouds",
    "SCT": "scattered clouds",
    "BKN": "mostly cloudy skies",
    "OVC": "overcast skies",
    "VV": "sky obscured",
}

# Intensity prefixes that can precede a weather phenomenon code, e.g.
# "-RA" (light rain) or "+TSRA" (heavy thunderstorm with rain).
WX_INTENSITY = {
    "-": "light",
    "+": "heavy",
    "VC": "nearby",
}

# Two-letter "descriptor" codes that modify a phenomenon, e.g. the "SH"
# in "SHRA" (showers of rain) or the "FZ" in "FZFG" (freezing fog).
WX_DESCRIPTOR = {
    "MI": "shallow",
    "PR": "partial",
    "BC": "patchy",
    "DR": "low drifting",
    "BL": "blowing",
    "SH": "showers of",
    "TS": "thunderstorm with",
    "FZ": "freezing",
}

# Two-letter codes for the weather phenomenon itself (precipitation,
# obscuration, or other), e.g. "RA" (rain) or "FG" (fog).
WX_PHENOMENON = {
    "DZ": "drizzle",
    "RA": "rain",
    "SN": "snow",
    "SG": "snow grains",
    "IC": "ice crystals",
    "PL": "ice pellets",
    "GR": "hail",
    "GS": "small hail",
    "UP": "unknown precipitation",
    "BR": "mist",
    "FG": "fog",
    "FU": "smoke",
    "VA": "volcanic ash",
    "DU": "dust",
    "SA": "sand",
    "HZ": "haze",
    "PY": "spray",
    "PO": "dust whirls",
    "SQ": "squalls",
    "FC": "funnel cloud",
    "SS": "sandstorm",
    "DS": "duststorm",
}

# Overall flight-category classification, derived by the API from
# ceiling and visibility.
FLIGHT_CATEGORY = {
    "VFR": "good flying conditions",
    "MVFR": "marginal flying conditions",
    "IFR": "poor flying conditions (low visibility/ceiling)",
    "LIFR": "very poor flying conditions (very low visibility/ceiling)",
}

# The 16 standard compass points, in order, for converting a wind
# direction in degrees to a human-friendly heading.
COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]

# A single METAR observation, as returned by the API (one dict per station).
Observation = Dict[str, Union[str, int, float, list, None]]


def degrees_to_compass(degrees: Optional[float]) -> Optional[str]:
    """Convert a wind direction in degrees (0-360) to a compass point."""
    if degrees is None:
        return None
    index = round(degrees / 22.5) % len(COMPASS_POINTS)
    return COMPASS_POINTS[index]


def c_to_f(celsius: float) -> float:
    """Convert a temperature from Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32


def knots_to_mph(knots: float) -> float:
    """Convert a speed from knots to miles per hour."""
    return knots * 1.15078


def hpa_to_inhg(hpa: float) -> float:
    """Convert an atmospheric pressure from hectopascals to inches of mercury."""
    return hpa / 33.8639


def decode_wx_string(wx_string: Optional[str]) -> List[str]:
    """Decode a METAR present-weather string into plain-English phrases.

    The field is a space-separated list of codes such as ``"-RA BR"``
    (light rain, mist) or ``"+TSRA"`` (heavy thunderstorm with rain).
    Each code may have an optional 1-2 character intensity prefix,
    followed by one or more 2-character descriptor/phenomenon groups.

    Args:
        wx_string: The raw ``wxString`` field from the API, or ``None``.

    Returns:
        A list of human-readable phrases, one per code in the string.
        Empty if no weather phenomena were reported.
    """
    if not wx_string:
        return []

    descriptions = []
    for token in wx_string.split():
        remaining = token
        intensity = ""

        if remaining.startswith("+") or remaining.startswith("-"):
            intensity = WX_INTENSITY[remaining[0]]
            remaining = remaining[1:]
        elif remaining.startswith("VC"):
            intensity = WX_INTENSITY["VC"]
            remaining = remaining[2:]

        # The remainder is made up of 2-character descriptor/phenomenon
        # groups, e.g. "TSRA" -> ["TS", "RA"].
        parts = [remaining[i:i + 2] for i in range(0, len(remaining), 2)]
        words = []
        for part in parts:
            if part in WX_DESCRIPTOR:
                words.append(WX_DESCRIPTOR[part])
            elif part in WX_PHENOMENON:
                words.append(WX_PHENOMENON[part])
            else:
                # Unrecognized code: surface it verbatim rather than
                # silently dropping information.
                words.append(part)

        phrase = " ".join(filter(None, [intensity] + words))
        if phrase:
            descriptions.append(phrase)

    return descriptions


def _cover_rank(cover: Optional[str]) -> int:
    """Rank a cloud cover code by how much of the sky it obscures.

    Used to pick the most significant layer out of several reported
    cloud layers. Unrecognized codes rank lowest (-1).
    """
    order = ["SKC", "CLR", "FEW", "SCT", "BKN", "OVC", "VV"]
    return order.index(cover) if cover in order else -1


def describe_sky(clouds: Optional[List[dict]], cover: Optional[str]) -> str:
    """Describe sky conditions from the reported cloud layers.

    Args:
        clouds: A list of ``{"cover": ..., "base": ...}`` layer dicts,
            as returned by the API, or ``None``/empty if none reported.
        cover: A fallback overall cover code, used when no per-layer
            detail is available.
    """
    if not clouds:
        return CLOUD_COVER.get(cover, "clear skies")

    highest_layer = max(clouds, key=lambda layer: _cover_rank(layer.get("cover")))
    description = CLOUD_COVER.get(highest_layer.get("cover"), "cloudy skies")
    base = highest_layer.get("base")
    if base:
        return f"{description} at {base:,} ft"
    return description


def describe_wind(
    wdir: Optional[float], wspd: Optional[float], wgst: Optional[float]
) -> str:
    """Describe wind speed, direction, and gusts in plain English."""
    if not wspd:
        return "calm winds"

    speed_mph = round(knots_to_mph(wspd))
    # wdir can be the string "VRB" (variable) instead of a numeric
    # heading; only convert it to a compass point when it's a number.
    direction = degrees_to_compass(wdir) if isinstance(wdir, (int, float)) else None

    if direction:
        text = f"wind from the {direction} at {speed_mph} mph"
    else:
        text = f"wind at {speed_mph} mph (variable direction)"

    if wgst:
        text += f", gusting to {round(knots_to_mph(wgst))} mph"

    return text


def describe_visibility(visib: Optional[Union[str, float]]) -> Optional[str]:
    """Describe visibility in plain English.

    The API reports ``visib`` as a numeric string, sometimes with a
    trailing "+" to mean "at least" (e.g. ``"10+"`` for 10+ miles).
    """
    if visib is None:
        return None
    visib_str = str(visib).replace("+", "")
    try:
        value = float(visib_str)
    except ValueError:
        return f"visibility {visib} statute miles"

    if value >= 10:
        return "visibility 10+ miles (excellent)"
    return f"visibility {value:g} statute miles"


def decode_metar(observation: Observation) -> dict:
    """Build a plain-English weather summary from a METAR observation.

    Args:
        observation: A single station's parsed METAR record, as returned
            by the aviationweather.gov JSON API (see module docstring).

    Returns:
        A dict of decoded fields, including a one-sentence ``summary``
        suitable for display, plus the individual components (wind,
        sky, temperature, etc.) for a more detailed breakdown.
    """
    station = observation.get("name") or observation.get("icaoId", "the station")
    raw = observation.get("rawOb", "")

    temp_c = observation.get("temp")
    dewp_c = observation.get("dewp")
    wx_phrases = decode_wx_string(observation.get("wxString"))
    sky = describe_sky(observation.get("clouds"), observation.get("cover"))
    wind = describe_wind(
        observation.get("wdir"), observation.get("wspd"), observation.get("wgst")
    )
    visibility = describe_visibility(observation.get("visib"))
    flight_category = observation.get("fltCat")

    # Lead the summary with active weather (rain, fog, etc.) when
    # present, since that's more newsworthy than routine sky cover.
    sentence_parts = []
    if wx_phrases:
        sentence_parts.append(", ".join(wx_phrases).capitalize())
    else:
        sentence_parts.append(sky.capitalize())

    if temp_c is not None:
        sentence_parts.append(f"{round(c_to_f(temp_c))}°F ({round(temp_c)}°C)")

    sentence_parts.append(wind)

    if visibility:
        sentence_parts.append(visibility)

    summary = ", ".join(sentence_parts) + "."

    return {
        "station_name": station,
        "raw_metar": raw,
        "summary": summary,
        "temperature_f": round(c_to_f(temp_c)) if temp_c is not None else None,
        "temperature_c": round(temp_c) if temp_c is not None else None,
        "dewpoint_f": round(c_to_f(dewp_c)) if dewp_c is not None else None,
        "wind": wind,
        "sky": sky,
        "weather": ", ".join(wx_phrases) if wx_phrases else None,
        "visibility": visibility,
        "altimeter_inhg": round(hpa_to_inhg(observation["altim"]), 2)
        if observation.get("altim")
        else None,
        "flight_category": flight_category,
        "flight_category_text": FLIGHT_CATEGORY.get(flight_category),
        "observation_time": observation.get("reportTime"),
    }
