# SolarWeather v0.5
# Full-screen UK postcode weather app for SolarOS.
# Built on the exact syntax style proven by solarweather_ui_test_v2.py.

import solaros

gfx = solaros.gfx

KEY_ENTER = 13
KEY_LF = 10
KEY_BACKSPACE = 8
KEY_SPACE = 32
KEY_Q = 113
KEY_R = 114
KEY_R_UP = 82
KEY_N = 110
KEY_N_UP = 78

def idiv(a, b):
    q = 0
    while a >= b:
        a = a - b
        q = q + 1
    return q

def chars_to_text(chars):
    text = ""
    for ch in chars:
        text = text + ch
    return text

def postcode_url_text(chars):
    text = ""
    for ch in chars:
        if ch == " ":
            text = text + "%20"
        else:
            text = text + ch
    return text

def load_requests():
    try:
        import urequests
        return urequests
    except ImportError:
        pass

    try:
        import requests
        return requests
    except ImportError:
        pass

    return None

def http_json(requests, url):
    response = requests.get(url)

    status = 200
    if hasattr(response, "status_code"):
        status = response.status_code

    if status < 200 or status >= 300:
        try:
            response.close()
        except Exception:
            pass
        raise Exception("HTTP " + str(status))

    data = None

    if hasattr(response, "json"):
        data = response.json()
    else:
        import json
        data = json.loads(response.text)

    try:
        response.close()
    except Exception:
        pass

    return data

def fetch_weather(requests, chars):
    postcode_url = postcode_url_text(chars)

    postcode_api = "https://api.postcodes.io/postcodes/" + postcode_url
    postcode_data = http_json(requests, postcode_api)

    if postcode_data == None:
        raise Exception("No postcode response")

    if postcode_data.get("status") != 200:
        raise Exception("Postcode not found")

    result = postcode_data.get("result")
    if result == None:
        raise Exception("Postcode not found")

    lat = result.get("latitude")
    lon = result.get("longitude")
    district = result.get("admin_district")
    region = result.get("region")

    if district == None:
        district = ""
    if region == None:
        region = ""

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_url = weather_url + "?latitude=" + str(lat)
    weather_url = weather_url + "&longitude=" + str(lon)
    weather_url = weather_url + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,snowfall,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m,wind_direction_10m"
    weather_url = weather_url + "&wind_speed_unit=mph"
    weather_url = weather_url + "&timezone=Europe%2FLondon"

    weather_data = http_json(requests, weather_url)
    current = weather_data.get("current")

    if current == None:
        raise Exception("No current weather data")

    data = {}
    data["postcode"] = chars_to_text(chars)
    data["district"] = district
    data["region"] = region
    data["temperature"] = current.get("temperature_2m")
    data["feels"] = current.get("apparent_temperature")
    data["humidity"] = current.get("relative_humidity_2m")
    data["precipitation"] = current.get("precipitation")
    data["rain"] = current.get("rain")
    data["snow"] = current.get("snowfall")
    data["code"] = current.get("weather_code")
    data["cloud"] = current.get("cloud_cover")
    data["wind"] = current.get("wind_speed_10m")
    data["gust"] = current.get("wind_gusts_10m")
    data["wind_dir"] = current.get("wind_direction_10m")

    return data

def number_text(value, suffix):
    if value == None:
        return "--"
    try:
        return str(int(value + 0.5)) + suffix
    except Exception:
        return str(value) + suffix

def decimal_text(value, suffix):
    if value == None:
        return "--"
    try:
        scaled = int(value * 10)
        whole = idiv(scaled, 10)
        fraction = scaled - whole * 10
        return str(whole) + "." + str(fraction) + suffix
    except Exception:
        return str(value) + suffix

def weather_label(code):
    if code == None:
        return "Unknown"
    if code == 0:
        return "Clear"
    if code == 1 or code == 2:
        return "Partly cloudy"
    if code == 3:
        return "Overcast"
    if code == 45 or code == 48:
        return "Fog"
    if code >= 51 and code <= 67:
        return "Rain"
    if code >= 71 and code <= 77:
        return "Snow"
    if code >= 80 and code <= 82:
        return "Rain showers"
    if code == 85 or code == 86:
        return "Snow showers"
    if code >= 95:
        return "Thunderstorm"
    return "Mixed"

def condition_type(code):
    if code == 0:
        return "sun"
    if code == 45 or code == 48:
        return "fog"
    if code != None:
        if code >= 51 and code <= 67:
            return "rain"
        if code >= 80 and code <= 82:
            return "rain"
        if code >= 71 and code <= 77:
            return "snow"
        if code == 85 or code == 86:
            return "snow"
        if code >= 95:
            return "storm"
    return "cloud"

def compass(deg):
    if deg == None:
        return ""

    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

    d = int(deg)
    d = d + 22

    while d >= 360:
        d = d - 360

    index = idiv(d, 45)

    if index > 7:
        index = 0

    return names[index]

def draw_sun(cx, cy):
    gfx.fill_circle(cx, cy, 22)
    gfx.line(cx, cy - 38, cx, cy - 30)
    gfx.line(cx, cy + 30, cx, cy + 38)
    gfx.line(cx - 38, cy, cx - 30, cy)
    gfx.line(cx + 30, cy, cx + 38, cy)
    gfx.line(cx - 28, cy - 28, cx - 22, cy - 22)
    gfx.line(cx + 22, cy + 22, cx + 28, cy + 28)
    gfx.line(cx + 22, cy - 22, cx + 28, cy - 28)
    gfx.line(cx - 28, cy + 28, cx - 22, cy + 22)

def draw_cloud(cx, cy):
    gfx.fill_circle(cx - 18, cy, 13)
    gfx.fill_circle(cx, cy - 8, 18)
    gfx.fill_circle(cx + 20, cy, 13)
    gfx.fill_rect(cx - 30, cy, 60, 18)

def draw_rain(cx, cy):
    draw_cloud(cx, cy - 12)
    gfx.line(cx - 20, cy + 18, cx - 25, cy + 32)
    gfx.line(cx, cy + 18, cx - 5, cy + 32)
    gfx.line(cx + 20, cy + 18, cx + 15, cy + 32)

def draw_snow(cx, cy):
    draw_cloud(cx, cy - 12)
    x = cx - 20
    while x <= cx + 20:
        gfx.line(x - 4, cy + 28, x + 4, cy + 28)
        gfx.line(x, cy + 24, x, cy + 32)
        x = x + 20

def draw_fog(cx, cy):
    draw_cloud(cx, cy - 16)
    gfx.line(cx - 34, cy + 22, cx + 34, cy + 22)
    gfx.line(cx - 34, cy + 32, cx + 34, cy + 32)
    gfx.line(cx - 34, cy + 42, cx + 34, cy + 42)

def draw_storm(cx, cy):
    draw_cloud(cx, cy - 12)
    gfx.line(cx + 5, cy + 15, cx - 7, cy + 32)
    gfx.line(cx - 7, cy + 32, cx + 4, cy + 30)
    gfx.line(cx + 4, cy + 30, cx - 6, cy + 46)

def draw_icon(kind, cx, cy):
    if kind == "sun":
        draw_sun(cx, cy)
    elif kind == "rain":
        draw_rain(cx, cy)
    elif kind == "snow":
        draw_snow(cx, cy)
    elif kind == "fog":
        draw_fog(cx, cy)
    elif kind == "storm":
        draw_storm(cx, cy)
    else:
        draw_cloud(cx, cy)

def draw_entry(w, h, chars):
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 18, "SolarWeather")

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 40, "Enter UK postcode:")

    box_w = w - 40
    if box_w > 300:
        box_w = 300

    box_x = idiv(w - box_w, 2)
    box_y = 62

    gfx.rect(box_x, box_y, box_w, 38)

    gfx.font(gfx.FONT_MONO_14)
    gfx.text(box_x + 10, box_y + 25, chars_to_text(chars))

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, h - 10, "Enter fetches weather, ESC quits")
    gfx.refresh()

def draw_loading(w, h, chars):
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 18, "SolarWeather")

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, idiv(h, 2), "Fetching " + chars_to_text(chars) + " ...")
    gfx.refresh()

def draw_error(w, h, message):
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 18, "Weather error")

    gfx.font(gfx.FONT_MONO_12)

    text = str(message)
    line = ""
    y = 50
    i = 0

    while i < len(text):
        line = line + text[i]
        if len(line) >= 38:
            gfx.text(10, y, line)
            y = y + 16
            line = ""
        i = i + 1

    if len(line) > 0:
        gfx.text(10, y, line)

    gfx.text(10, h - 10, "N new postcode, ESC quits")
    gfx.refresh()

def draw_weather(w, h, data):
    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 18, data["postcode"])

    location = data["district"]
    if location == "":
        location = data["region"]

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 38, location)

    icon_x = idiv(w, 4)
    icon_y = 105
    draw_icon(condition_type(data["code"]), icon_x, icon_y)

    text_x = idiv(w, 2)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(text_x, 86, number_text(data["temperature"], " C"))

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(text_x, 108, weather_label(data["code"]))
    gfx.text(text_x, 128, "Feels " + number_text(data["feels"], " C"))

    gfx.line(10, 155, w - 10, 155)

    col = idiv(w, 3)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 180, "Precip")
    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 200, decimal_text(data["precipitation"], " mm"))

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(col + 8, 180, "Wind")
    gfx.font(gfx.FONT_MONO_12)
    gfx.text(col + 8, 200, number_text(data["wind"], " mph") + " " + compass(data["wind_dir"]))

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text((col * 2) + 8, 180, "Humidity")
    gfx.font(gfx.FONT_MONO_12)
    gfx.text((col * 2) + 8, 200, number_text(data["humidity"], "%"))

    gfx.font(gfx.FONT_MONO_12)
    footer = "Gust " + number_text(data["gust"], " mph")
    footer = footer + "  Cloud " + number_text(data["cloud"], "%")
    gfx.text(10, h - 30, footer)
    gfx.text(10, h - 10, "R refresh, N new postcode, ESC quits")

    gfx.refresh()

def main():
    gfx.begin()

    w, h = gfx.size()
    chars = []
    last_chars = []
    weather = None
    mode = "entry"
    requests = load_requests()

    if requests == None:
        draw_error(w, h, "HTTP module missing: urequests or requests not available")
        while not solaros.should_exit():
            key = gfx.getch(100)
            if key == gfx.KEY_ESCAPE or key == KEY_ENTER or key == KEY_LF:
                break
        gfx.end()
        return

    draw_entry(w, h, chars)

    while not solaros.should_exit():
        key = gfx.getch(100)

        if key == gfx.KEY_ESCAPE or key == KEY_Q:
            break

        if mode == "entry":
            if key == KEY_BACKSPACE:
                if len(chars) > 0:
                    chars.pop()
                    draw_entry(w, h, chars)
                continue

            if key == KEY_ENTER or key == KEY_LF:
                if len(chars) >= 5:
                    draw_loading(w, h, chars)

                    try:
                        weather = fetch_weather(requests, chars)

                        last_chars = []
                        for ch in chars:
                            last_chars.append(ch)

                        mode = "weather"
                        draw_weather(w, h, weather)
                    except Exception as exc:
                        mode = "error"
                        draw_error(w, h, str(exc))
                continue

            if key != None:
                if key >= 32 and key <= 126:
                    if len(chars) < 9:
                        chars.append(chr(key))
                        draw_entry(w, h, chars)

        elif mode == "weather":
            if key == KEY_N or key == KEY_N_UP:
                chars = []
                mode = "entry"
                draw_entry(w, h, chars)
                continue

            if key == KEY_R or key == KEY_R_UP:
                if len(last_chars) > 0:
                    draw_loading(w, h, last_chars)

                    try:
                        weather = fetch_weather(requests, last_chars)
                        draw_weather(w, h, weather)
                    except Exception as exc:
                        mode = "error"
                        draw_error(w, h, str(exc))
                continue

        elif mode == "error":
            if key == KEY_N or key == KEY_N_UP:
                chars = []
                mode = "entry"
                draw_entry(w, h, chars)
                continue

    gfx.end()

main()
