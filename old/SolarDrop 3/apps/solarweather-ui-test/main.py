# SolarWeather UI test for SolarOS
# Deliberately mirrors examples/python/snake.py style.

import solaros

gfx = solaros.gfx

KEY_ENTER = 13
KEY_LF = 10
KEY_BACKSPACE = 8
KEY_SPACE = 32
KEY_Q = 113

def idiv(a, b):
    q = 0
    while a >= b:
        a = a - b
        q = q + 1
    return q

def positive(value):
    if value < 0:
        return 0
    return value

def draw_sun(cx, cy):
    gfx.fill_circle(cx, cy, 22)
    gfx.line(cx, cy - 38, cx, cy - 30)
    gfx.line(cx, cy + 30, cx, cy + 38)
    gfx.line(cx - 38, cy, cx - 30, cy)
    gfx.line(cx + 30, cy, cx + 38, cy)

def draw_cloud(cx, cy):
    gfx.fill_circle(cx - 18, cy, 13)
    gfx.fill_circle(cx, cy - 8, 18)
    gfx.fill_circle(cx + 20, cy, 13)
    gfx.fill_rect(cx - 30, cy, 60, 18)

def draw(w, h, postcode):
    gfx.clear(gfx.WHITE)

    gfx.color(gfx.BLACK)
    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 18, "SolarWeather")

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 38, "Enter UK postcode:")

    box_w = w - 40
    if box_w > 300:
        box_w = 300

    box_x = idiv(w - box_w, 2)
    box_y = 58

    gfx.rect(box_x, box_y, box_w, 38)

    gfx.font(gfx.FONT_MONO_14)
    gfx.text(box_x + 10, box_y + 25, postcode + "_")

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 120, "Graphics test")

    draw_sun(idiv(w, 3), 180)
    draw_cloud(idiv(w, 3) * 2, 180)

    gfx.text(10, h - 10, "Type postcode, Enter tests, ESC quits")

    gfx.refresh()

def draw_result(w, h, postcode):
    gfx.clear(gfx.WHITE)

    gfx.color(gfx.BLACK)
    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 18, "SolarWeather")

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 45, "Postcode accepted:")
    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(10, 68, postcode)

    draw_sun(idiv(w, 2), 135)

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(10, 205, "UI test succeeded")
    gfx.text(10, h - 10, "Space returns, ESC quits")

    gfx.refresh()

def main():
    gfx.begin()

    w, h = gfx.size()
    postcode = ""
    result_screen = False

    draw(w, h, postcode)

    while not solaros.should_exit():
        key = gfx.getch(100)

        if key == gfx.KEY_ESCAPE or key == KEY_Q:
            break

        if result_screen:
            if key == KEY_SPACE:
                result_screen = False
                draw(w, h, postcode)
            continue

        if key == KEY_BACKSPACE:
            if len(postcode) > 0:
                postcode = postcode[:-1]
                draw(w, h, postcode)
            continue

        if key == KEY_ENTER or key == KEY_LF:
            result_screen = True
            draw_result(w, h, postcode)
            continue

        if key != None:
            if key >= 32 and key <= 126:
                if len(postcode) < 9:
                    ch = chr(key)
                    postcode = postcode + ch
                    draw(w, h, postcode)

    gfx.end()

main()
