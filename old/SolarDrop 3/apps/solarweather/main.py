# SolarWeather v0.1 for SolarOS
# Full-screen UK postcode weather app.
#
# APIs:
#   - postcodes.io for UK postcode -> latitude/longitude
#   - Open-Meteo for current conditions
#
# Controls:
#   Type postcode, Enter to fetch
#   R refresh
#   N new postcode
#   ESC quit
#
# Designed for SolarOS MicroPython + solaros.gfx.

import solaros
from solaros import gfx
import json

try:
    import urequests as requests
except ImportError:
    try:
        import requests
    except ImportError:
        requests = None

KEY_ENTER = 13
KEY_LF = 10
KEY_BACKSPACE = 8
KEY_DELETE = 127
KEY_R = ord("r")
KEY_N = ord("n")

postcode = ""
last_postcode = ""
weather = None
error_message = None

def http_json(url):
    if requests is None:
        raise RuntimeError(
            "HTTP module missing: firmware needs urequests/requests"
        )

    response = requests.get(url)

    try:
        status = getattr(response, "status_code", 200)
        if status < 200 or status >= 300:
            raise RuntimeError("HTTP {}".format(status))

        if hasattr(response, "json"):
            return response.json()

        text = response.text
        return json.loads(text)
    finally:
        try:
            response.close()
        except Exception:
            pass

def encode_postcode(value):
    # Minimal URL encoding sufficient for UK postcodes.
    return value.strip().upper().replace(" ", "%20")

def geocode_postcode(value):
    url = "https://api.postcodes.io/postcodes/" + encode_postcode(value)
    data = http_json(url)

    if not data or data.get("status") != 200 or not data.get("result"):
        raise RuntimeError("Postcode not found")

    result = data["result"]
    return (
        result["latitude"],
        result["longitude"],
        result.get("admin_district") or "",
        result.get("region") or "",
    )

def fetch_weather(value):
    lat, lon, district, region = geocode_postcode(value)

    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude={:.5f}&longitude={:.5f}"
        "&current=temperature_2m,apparent_temperature,"
        "relative_humidity_2m,precipitation,rain,snowfall,"
        "weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m,"
        "wind_direction_10m"
        "&wind_speed_unit=mph"
        "&timezone=Europe%2FLondon"
    ).format(lat, lon)

    data = http_json(url)
    current = data.get("current")
    if not current:
        raise RuntimeError("No current weather data")

    return {
        "postcode": value.strip().upper(),
        "district": district,
        "region": region,
        "temperature": current.get("temperature_2m"),
        "feels": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "rain": current.get("rain"),
        "snow": current.get("snowfall"),
        "code": current.get("weather_code", 0),
        "cloud": current.get("cloud_cover"),
        "wind": current.get("wind_speed_10m"),
        "gust": current.get("wind_gusts_10m"),
        "wind_dir": current.get("wind_direction_10m"),
    }

def weather_label(code):
    if code == 0:
        return "Clear"
    if code in (1, 2):
        return "Partly cloudy"
    if code == 3:
        return "Overcast"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Mixed"

def condition_type(code):
    if code == 0:
        return "sun"
    if code in (1, 2, 3):
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloud"

def compass(deg):
    if deg is None:
        return ""
    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    idx = int((deg + 22.5) // 45) % 8
    return names[idx]

# ---------- icon drawing ----------

def draw_sun(cx, cy, r):
    gfx.circle(cx, cy, r)
    gfx.fill_circle(cx, cy, r - 2)
    rr = r + 10
    for dx, dy in (
        (0, -1), (1, -1), (1, 0), (1, 1),
        (0, 1), (-1, 1), (-1, 0), (-1, -1)
    ):
        x1 = cx + dx * rr
        y1 = cy + dy * rr
        x2 = cx + dx * (rr + 8)
        y2 = cy + dy * (rr + 8)
        gfx.line(x1, y1, x2, y2)

def draw_cloud(cx, cy, scale=1):
    gfx.fill_circle(cx - 18 * scale, cy, 14 * scale)
    gfx.fill_circle(cx, cy - 8 * scale, 19 * scale)
    gfx.fill_circle(cx + 20 * scale, cy, 14 * scale)
    gfx.fill_rect(cx - 31 * scale, cy, 62 * scale, 19 * scale)

def draw_rain(cx, cy):
    draw_cloud(cx, cy - 12, 1)
    for x in (-20, 0, 20):
        gfx.line(cx + x, cy + 20, cx + x - 5, cy + 34)
        gfx.line(cx + x - 1, cy + 20, cx + x - 6, cy + 34)

def draw_snow(cx, cy):
    draw_cloud(cx, cy - 12, 1)
    for x in (-20, 0, 20):
        sy = cy + 28
        gfx.line(cx + x - 5, sy, cx + x + 5, sy)
        gfx.line(cx + x, sy - 5, cx + x, sy + 5)
        gfx.line(cx + x - 4, sy - 4, cx + x + 4, sy + 4)
        gfx.line(cx + x - 4, sy + 4, cx + x + 4, sy - 4)

def draw_fog(cx, cy):
    draw_cloud(cx, cy - 16, 1)
    for y in (18, 28, 38):
        gfx.line(cx - 34, cy + y, cx + 34, cy + y)

def draw_storm(cx, cy):
    draw_cloud(cx, cy - 14, 1)
    gfx.line(cx + 3, cy + 14, cx - 8, cy + 33)
    gfx.line(cx - 8, cy + 33, cx + 4, cy + 31)
    gfx.line(cx + 4, cy + 31, cx - 7, cy + 50)

def draw_weather_icon(kind, cx, cy):
    gfx.color(gfx.BLACK)
    if kind == "sun":
        draw_sun(cx, cy, 27)
    elif kind == "rain":
        draw_rain(cx, cy)
    elif kind == "snow":
        draw_snow(cx, cy)
    elif kind == "fog":
        draw_fog(cx, cy)
    elif kind == "storm":
        draw_storm(cx, cy)
    else:
        # partial sun behind cloud
        gfx.circle(cx - 28, cy - 20, 20)
        draw_cloud(cx + 5, cy, 1)

def draw_wind_icon(x, y):
    gfx.line(x, y, x + 38, y)
    gfx.line(x + 38, y, x + 30, y - 6)
    gfx.line(x + 38, y, x + 30, y + 6)

    gfx.line(x + 8, y + 12, x + 48, y + 12)
    gfx.line(x + 48, y + 12, x + 40, y + 6)
    gfx.line(x + 48, y + 12, x + 40, y + 18)

def draw_drop(x, y):
    gfx.circle(x, y + 8, 7)
    gfx.line(x, y - 8, x - 7, y + 5)
    gfx.line(x, y - 8, x + 7, y + 5)

# ---------- screens ----------

def centered_text(y, text, font):
    gfx.font(font)
    # Approximation avoids requiring text measurement API.
    char_w = 10 if font in (gfx.FONT_BOLD_18, gfx.FONT_MONO_18) else 8
    w, _ = gfx.size()
    x = max(4, (w - len(text) * char_w) // 2)
    gfx.text(x, y, text)

def draw_entry():
    w, h = gfx.size()
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    centered_text(38, "SolarWeather", gfx.FONT_BOLD_20)
    centered_text(72, "Enter UK postcode", gfx.FONT_BOLD_16)

    box_w = min(w - 40, 300)
    box_x = (w - box_w) // 2
    box_y = h // 2 - 28

    gfx.rect(box_x, box_y, box_w, 52)
    gfx.font(gfx.FONT_MONO_20)
    shown = postcode + "_"
    gfx.text(box_x + 14, box_y + 34, shown)

    centered_text(h - 34, "ENTER fetches weather   ESC quits", gfx.FONT_MONO_12)
    gfx.refresh()

def draw_loading():
    w, h = gfx.size()
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)
    centered_text(h // 2 - 8, "Fetching weather...", gfx.FONT_BOLD_18)
    centered_text(h // 2 + 20, postcode.upper(), gfx.FONT_MONO_14)
    gfx.refresh()

def fmt(value, decimals=0, suffix=""):
    if value is None:
        return "--"
    if decimals == 0:
        return "{}{}".format(int(round(value)), suffix)
    return ("{:" + "." + str(decimals) + "f}{}").format(value, suffix)

def draw_weather(data):
    w, h = gfx.size()
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    # Header
    gfx.font(gfx.FONT_BOLD_18)
    gfx.text(10, 25, data["postcode"])

    location = data["district"] or data["region"]
    if location:
        gfx.font(gfx.FONT_MONO_12)
        gfx.text(10, 43, location[:35])

    # Main icon
    icon_x = w // 4
    icon_y = 110
    draw_weather_icon(condition_type(data["code"]), icon_x, icon_y)

    # Temperature and condition
    text_x = w // 2
    gfx.font(gfx.FONT_BOLD_20)
    gfx.text(text_x, 94, fmt(data["temperature"], 0, " C"))

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(text_x, 118, weather_label(data["code"]))

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(text_x, 138, "Feels " + fmt(data["feels"], 0, " C"))

    # Separator
    gfx.line(10, 160, w - 10, 160)

    # Metrics row
    col = w // 3

    # Rain
    draw_drop(col // 2, 192)
    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(12, 224, "Precip")
    gfx.font(gfx.FONT_MONO_14)
    gfx.text(12, 244, fmt(data["precipitation"], 1, " mm"))

    # Wind
    draw_wind_icon(col + 12, 186)
    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(col + 12, 224, "Wind")
    gfx.font(gfx.FONT_MONO_14)
    wind = fmt(data["wind"], 0, " mph")
    direction = compass(data["wind_dir"])
    gfx.text(col + 12, 244, wind + " " + direction)

    # Humidity/cloud
    gfx.circle(2 * col + 34, 197, 18)
    gfx.text(2 * col + 28, 202, "%")
    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(2 * col + 12, 224, "Humidity")
    gfx.font(gfx.FONT_MONO_14)
    gfx.text(2 * col + 12, 244, fmt(data["humidity"], 0, "%"))

    # Footer
    if data["gust"] is not None:
        gfx.font(gfx.FONT_MONO_12)
        gfx.text(10, h - 32, "Gusts " + fmt(data["gust"], 0, " mph")
                 + "   Cloud " + fmt(data["cloud"], 0, "%"))

    gfx.text(10, h - 12, "R refresh   N new postcode   ESC quit")
    gfx.refresh()

def draw_error(message):
    w, h = gfx.size()
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    centered_text(55, "Weather error", gfx.FONT_BOLD_18)

    gfx.font(gfx.FONT_MONO_12)
    msg = str(message)
    max_chars = max(20, (w - 24) // 7)
    lines = []
    while msg:
        lines.append(msg[:max_chars])
        msg = msg[max_chars:]

    y = 95
    for line in lines[:6]:
        gfx.text(12, y, line)
        y += 18

    centered_text(h - 28, "N new postcode   ESC quit", gfx.FONT_MONO_12)
    gfx.refresh()

def fetch_current():
    global weather, error_message, last_postcode
    draw_loading()

    try:
        weather = fetch_weather(postcode)
        last_postcode = postcode
        error_message = None
    except Exception as exc:
        weather = None
        error_message = str(exc)

def edit_postcode_key(key):
    global postcode

    if key in (KEY_ENTER, KEY_LF):
        if len(postcode.strip()) >= 5:
            return "fetch"
        return None

    if key in (KEY_BACKSPACE, KEY_DELETE, getattr(gfx, "KEY_DELETE", -999)):
        postcode = postcode[:-1]
        return "redraw"

    if key == gfx.KEY_ESCAPE:
        return "quit"

    # Printable ASCII, limited to postcode-ish characters.
    if key is not None and 32 <= key <= 126 and len(postcode) < 9:
        ch = chr(key).upper()
        if ch.isalnum() or ch == " ":
            postcode += ch
            return "redraw"

    return None

gfx_started = False

try:
    gfx.begin()
    gfx_started = True
    draw_entry()

    mode = "entry"

    while not solaros.should_exit():
        key = gfx.getch(100)

        if mode == "entry":
            action = edit_postcode_key(key)

            if action == "quit":
                break
            elif action == "redraw":
                draw_entry()
            elif action == "fetch":
                fetch_current()
                if weather:
                    mode = "weather"
                    draw_weather(weather)
                else:
                    mode = "error"
                    draw_error(error_message)

        elif mode == "weather":
            if key == gfx.KEY_ESCAPE:
                break
            elif key in (KEY_R, ord("R")):
                postcode = last_postcode
                fetch_current()
                if weather:
                    draw_weather(weather)
                else:
                    mode = "error"
                    draw_error(error_message)
            elif key in (KEY_N, ord("N")):
                postcode = ""
                mode = "entry"
                draw_entry()

        elif mode == "error":
            if key == gfx.KEY_ESCAPE:
                break
            elif key in (KEY_N, ord("N")):
                postcode = ""
                mode = "entry"
                draw_entry()
            elif key in (KEY_R, ord("R")) and last_postcode:
                postcode = last_postcode
                fetch_current()
                if weather:
                    mode = "weather"
                    draw_weather(weather)
                else:
                    draw_error(error_message)

finally:
    if gfx_started:
        gfx.end()
