# SolarWeather v0.3 - conservative MicroPython build
# Full-screen UK postcode weather app for SolarOS.

import solaros

gfx = solaros.gfx

KEY_ENTER = 13
KEY_LF = 10
KEY_BACKSPACE = 8
KEY_DELETE = 127
KEY_R = 114
KEY_R_UP = 82
KEY_N = 110
KEY_N_UP = 78

postcode = ""
last_postcode = ""
weather = None
error_message = ""
requests = None

def idiv(a, b):
    q = 0
    while a >= b:
        a = a - b
        q = q + 1
    return q

# Try HTTP module after startup so import failure is a normal app error.
def load_requests():
    global requests
    try:
        import urequests
        requests = urequests
        return True
    except ImportError:
        pass

    try:
        import requests as req
        requests = req
        return True
    except ImportError:
        pass

    return False

def http_json(url):
    if requests is None:
        raise Exception("HTTP module missing: urequests/requests unavailable")

    response = requests.get(url)

    try:
        status = 200
        if hasattr(response, "status_code"):
            status = response.status_code

        if status < 200 or status >= 300:
            raise Exception("HTTP error " + str(status))

        if hasattr(response, "json"):
            return response.json()

        import json
        return json.loads(response.text)
    finally:
        try:
            response.close()
        except Exception:
            pass

def encode_postcode(value):
    value = value.strip().upper()
    return value.replace(" ", "%20")

def geocode_postcode(value):
    url = "https://api.postcodes.io/postcodes/" + encode_postcode(value)
    data = http_json(url)

    if data is None:
        raise Exception("No postcode response")

    if data.get("status") != 200:
        raise Exception("Postcode not found")

    result = data.get("result")
    if result is None:
        raise Exception("Postcode not found")

    lat = result.get("latitude")
    lon = result.get("longitude")
    district = result.get("admin_district")
    region = result.get("region")

    if district is None:
        district = ""
    if region is None:
        region = ""

    return lat, lon, district, region

def fetch_weather(value):
    lat, lon, district, region = geocode_postcode(value)

    url = "https://api.open-meteo.com/v1/forecast"
    url = url + "?latitude=" + str(lat)
    url = url + "&longitude=" + str(lon)
    url = url + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,snowfall,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m,wind_direction_10m"
    url = url + "&wind_speed_unit=mph"
    url = url + "&timezone=Europe%2FLondon"

    data = http_json(url)
    current = data.get("current")

    if current is None:
        raise Exception("No current weather data")

    result = {}
    result["postcode"] = value.strip().upper()
    result["district"] = district
    result["region"] = region
    result["temperature"] = current.get("temperature_2m")
    result["feels"] = current.get("apparent_temperature")
    result["humidity"] = current.get("relative_humidity_2m")
    result["precipitation"] = current.get("precipitation")
    result["rain"] = current.get("rain")
    result["snow"] = current.get("snowfall")
    result["code"] = current.get("weather_code")
    result["cloud"] = current.get("cloud_cover")
    result["wind"] = current.get("wind_speed_10m")
    result["gust"] = current.get("wind_gusts_10m")
    result["wind_dir"] = current.get("wind_direction_10m")

    return result

def weather_label(code):
    if code is None:
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
    if code is not None and ((code >= 51 and code <= 67) or (code >= 80 and code <= 82)):
        return "rain"
    if code is not None and ((code >= 71 and code <= 77) or code == 85 or code == 86):
        return "snow"
    if code is not None and code >= 95:
        return "storm"
    return "cloud"

def compass(deg):
    if deg is None:
        return ""

    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    index = int((deg + 22.5) / 45) % 8
    return names[index]

def number_text(value, suffix):
    if value is None:
        return "--"
    try:
        return str(int(round(value))) + suffix
    except Exception:
        return str(value) + suffix

def decimal_text(value, suffix):
    if value is None:
        return "--"
    try:
        x = int(value * 10)
        whole = idiv(x, 10)
        fraction = x % 10
        return str(whole) + "." + str(fraction) + suffix
    except Exception:
        return str(value) + suffix

def center_x(text, width, char_width):
    x = idiv(width - len(text) * char_width, 2)
    if x < 4:
        x = 4
    return x

def draw_sun(cx, cy):
    gfx.fill_circle(cx, cy, 25)

    gfx.line(cx, cy - 43, cx, cy - 34)
    gfx.line(cx, cy + 34, cx, cy + 43)
    gfx.line(cx - 43, cy, cx - 34, cy)
    gfx.line(cx + 34, cy, cx + 43, cy)

    gfx.line(cx - 31, cy - 31, cx - 25, cy - 25)
    gfx.line(cx + 25, cy + 25, cx + 31, cy + 31)
    gfx.line(cx + 25, cy - 25, cx + 31, cy - 31)
    gfx.line(cx - 31, cy + 31, cx - 25, cy + 25)

def draw_cloud(cx, cy):
    gfx.fill_circle(cx - 20, cy, 15)
    gfx.fill_circle(cx, cy - 9, 20)
    gfx.fill_circle(cx + 21, cy, 15)
    gfx.fill_rect(cx - 34, cy, 68, 20)

def draw_rain(cx, cy):
    draw_cloud(cx, cy - 14)

    gfx.line(cx - 20, cy + 18, cx - 26, cy + 34)
    gfx.line(cx, cy + 18, cx - 6, cy + 34)
    gfx.line(cx + 20, cy + 18, cx + 14, cy + 34)

def draw_snow(cx, cy):
    draw_cloud(cx, cy - 14)

    x = cx - 20
    while x <= cx + 20:
        gfx.line(x - 5, cy + 28, x + 5, cy + 28)
        gfx.line(x, cy + 23, x, cy + 33)
        x = x + 20

def draw_fog(cx, cy):
    draw_cloud(cx, cy - 18)
    gfx.line(cx - 35, cy + 22, cx + 35, cy + 22)
    gfx.line(cx - 35, cy + 32, cx + 35, cy + 32)
    gfx.line(cx - 35, cy + 42, cx + 35, cy + 42)

def draw_storm(cx, cy):
    draw_cloud(cx, cy - 14)
    gfx.line(cx + 5, cy + 16, cx - 8, cy + 34)
    gfx.line(cx - 8, cy + 34, cx + 5, cy + 31)
    gfx.line(cx + 5, cy + 31, cx - 6, cy + 48)

def draw_icon(kind, cx, cy):
    gfx.color(gfx.BLACK)

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

def draw_entry():
    size = gfx.size()
    w = size[0]
    h = size[1]

    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_18)
    title = "SolarWeather"
    gfx.text(center_x(title, w, 10), 40, title)

    gfx.font(gfx.FONT_BOLD_14)
    prompt = "Enter UK postcode"
    gfx.text(center_x(prompt, w, 8), 75, prompt)

    box_w = 300
    if box_w > w - 40:
        box_w = w - 40

    box_x = idiv(w - box_w, 2)
    box_y = idiv(h, 2) - 28

    gfx.rect(box_x, box_y, box_w, 52)

    gfx.font(gfx.FONT_MONO_18)
    gfx.text(box_x + 14, box_y + 34, postcode + "_")

    gfx.font(gfx.FONT_MONO_12)
    footer = "ENTER fetches   ESC quits"
    gfx.text(center_x(footer, w, 7), h - 24, footer)

    gfx.refresh()

def draw_loading():
    size = gfx.size()
    w = size[0]
    h = size[1]

    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_18)
    text = "Fetching weather..."
    gfx.text(center_x(text, w, 10), idiv(h, 2) - 10, text)

    gfx.font(gfx.FONT_MONO_14)
    value = postcode.upper()
    gfx.text(center_x(value, w, 8), idiv(h, 2) + 20, value)

    gfx.refresh()

def draw_error(message):
    size = gfx.size()
    w = size[0]
    h = size[1]

    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_18)
    gfx.text(10, 35, "Weather error")

    gfx.font(gfx.FONT_MONO_12)

    text = str(message)
    max_chars = idiv(w - 20, 7)
    if max_chars < 20:
        max_chars = 20

    y = 65

    while len(text) > 0 and y < h - 45:
        line = text[:max_chars]
        text = text[max_chars:]
        gfx.text(10, y, line)
        y = y + 16

    gfx.text(10, h - 20, "N new postcode   ESC quit")
    gfx.refresh()

def draw_weather(data):
    size = gfx.size()
    w = size[0]
    h = size[1]

    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_18)
    gfx.text(10, 25, data["postcode"])

    location = data["district"]
    if location == "":
        location = data["region"]

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 44, location)

    icon_x = idiv(w, 4)
    icon_y = 110
    draw_icon(condition_type(data["code"]), icon_x, icon_y)

    text_x = idiv(w, 2)

    gfx.font(gfx.FONT_BOLD_18)
    gfx.text(text_x, 92, number_text(data["temperature"], " C"))

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(text_x, 116, weather_label(data["code"]))

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(text_x, 136, "Feels " + number_text(data["feels"], " C"))

    gfx.line(10, 160, w - 10, 160)

    col = idiv(w, 3)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(12, 190, "Precip")
    gfx.font(gfx.FONT_MONO_14)
    gfx.text(12, 212, decimal_text(data["precipitation"], " mm"))

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(col + 12, 190, "Wind")
    gfx.font(gfx.FONT_MONO_14)
    wind_text = number_text(data["wind"], " mph")
    wind_text = wind_text + " " + compass(data["wind_dir"])
    gfx.text(col + 12, 212, wind_text)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text((col * 2) + 12, 190, "Humidity")
    gfx.font(gfx.FONT_MONO_14)
    gfx.text((col * 2) + 12, 212, number_text(data["humidity"], "%"))

    gfx.font(gfx.FONT_MONO_12)
    bottom = "Gust " + number_text(data["gust"], " mph")
    bottom = bottom + "  Cloud " + number_text(data["cloud"], "%")
    gfx.text(10, h - 38, bottom)

    gfx.text(10, h - 18, "R refresh   N new postcode   ESC quit")
    gfx.refresh()

def fetch_current():
    global weather
    global error_message
    global last_postcode

    draw_loading()

    try:
        weather = fetch_weather(postcode)
        last_postcode = postcode
        error_message = ""
        return True
    except Exception as exc:
        weather = None
        error_message = str(exc)
        return False

def edit_key(key):
    global postcode

    if key == KEY_ENTER or key == KEY_LF:
        if len(postcode.strip()) >= 5:
            return "fetch"
        return ""

    if key == KEY_BACKSPACE or key == KEY_DELETE:
        postcode = postcode[:-1]
        return "redraw"

    if key == gfx.KEY_ESCAPE:
        return "quit"

    if key is not None:
        if key >= 32 and key <= 126:
            if len(postcode) < 9:
                ch = chr(key).upper()
                if ch == " " or ch.isalnum():
                    postcode = postcode + ch
                    return "redraw"

    return ""

def main():
    gfx_started = False
    
    try:
        gfx.begin()
        gfx_started = True
    
        if not load_requests():
            draw_error("HTTP module missing: urequests/requests unavailable")
            while not solaros.should_exit():
                key = gfx.getch(250)
                if key == gfx.KEY_ESCAPE or key == KEY_ENTER or key == KEY_LF:
                    break
        else:
            draw_entry()
            mode = "entry"
    
            while not solaros.should_exit():
                key = gfx.getch(100)
    
                if mode == "entry":
                    action = edit_key(key)
    
                    if action == "quit":
                        break
    
                    if action == "redraw":
                        draw_entry()
    
                    if action == "fetch":
                        if fetch_current():
                            mode = "weather"
                            draw_weather(weather)
                        else:
                            mode = "error"
                            draw_error(error_message)
    
                elif mode == "weather":
                    if key == gfx.KEY_ESCAPE:
                        break
    
                    if key == KEY_R or key == KEY_R_UP:
                        postcode = last_postcode
    
                        if fetch_current():
                            draw_weather(weather)
                        else:
                            mode = "error"
                            draw_error(error_message)
    
                    if key == KEY_N or key == KEY_N_UP:
                        postcode = ""
                        mode = "entry"
                        draw_entry()
    
                elif mode == "error":
                    if key == gfx.KEY_ESCAPE:
                        break
    
                    if key == KEY_N or key == KEY_N_UP:
                        postcode = ""
                        mode = "entry"
                        draw_entry()
    
    except Exception as exc:
        message = "SolarWeather fatal: " + str(exc)
    
        try:
            solaros.clipboard.set(message.encode())
        except Exception:
            pass
    
        if gfx_started:
            try:
                draw_error(message)
                while not solaros.should_exit():
                    key = gfx.getch(250)
                    if key == gfx.KEY_ESCAPE or key == KEY_ENTER or key == KEY_LF:
                        break
            except Exception:
                pass
    
    finally:
        if gfx_started:
            try:
                gfx.end()
            except Exception:
                pass

main()
