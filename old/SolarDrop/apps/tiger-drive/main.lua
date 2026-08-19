-- Tiger Drive - original polyphonic chiptune for SolarOS
-- Inspired by the general feel of punchy 80s arena-rock riffs.
-- Uses the same synth API pattern proven to work in SunTracker v0.4.
--
-- Controls:
--   SPACE  play / stop
--   R      restart
--   + / -  tempo
--   ESC    quit

local gfx = solaros.gfx
local synth = solaros.synth

local KEY_SPACE = 32
local KEY_PLUS = 43
local KEY_EQUALS = 61
local KEY_MINUS = 45
local KEY_R = 114

local bpm = 110
local playing = false
local step = 1

local function midi_to_freq(midi)
    return math.floor(440 * (2 ^ ((midi - 69) / 12)) + 0.5)
end

local function configure_synth()
    synth.configure("square", 4, 70, 68, 110)
    synth.configure_oscillator2("square", 0, 7, 28)
    synth.configure_performance(true, 0)
end

-- Each step can contain up to 4 simultaneous notes.
-- Short, repeated power-chord stabs + bass movement.
local pattern = {
    {45, 57, 64, nil},  -- A2 A3 E4
    {45, 57, 64, nil},
    {nil, nil, nil, nil},
    {45, 57, 64, nil},

    {43, 55, 62, nil},  -- G2 G3 D4
    {43, 55, 62, nil},
    {nil, nil, nil, nil},
    {43, 55, 62, nil},

    {41, 53, 60, nil},  -- F2 F3 C4
    {41, 53, 60, nil},
    {nil, nil, nil, nil},
    {43, 55, 62, nil},

    {45, 57, 64, nil},
    {45, 57, 64, 69},   -- add A4 for lift
    {nil, nil, nil, nil},
    {45, 57, 64, nil},

    -- second half: bass pushes upward
    {45, 57, 64, nil},
    {47, 59, 64, nil},
    {48, 60, 67, nil},
    {47, 59, 64, nil},

    {45, 57, 64, nil},
    {43, 55, 62, nil},
    {41, 53, 60, nil},
    {43, 55, 62, nil},

    {45, 57, 64, nil},
    {45, 57, 69, nil},
    {48, 60, 67, nil},
    {50, 62, 69, nil},

    {52, 64, 71, nil},
    {50, 62, 69, nil},
    {48, 60, 67, nil},
    {45, 57, 64, 69},
}

local function step_ms()
    -- 8th-note pulse
    return math.floor((60000 / bpm) / 2)
end

local function play_step(index)
    synth.all_notes_off()

    local chord = pattern[index]
    for i = 1, #chord do
        local note = chord[i]
        if note ~= nil then
            synth.note_on(midi_to_freq(note), 105)
        end
    end
end

local function draw()
    local w, h = gfx.size()

    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(8, 18, "Tiger Drive")

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(8, 36, "BPM " .. tostring(bpm) ..
        "   " .. (playing and "PLAY" or "STOP"))

    gfx.text(8, 58, "Polyphonic 80s-style chiptune")
    gfx.text(8, 78, "Step " .. tostring(step) .. "/" .. tostring(#pattern))

    local bar = ""
    for i = 1, 16 do
        if i == ((step - 1) % 16) + 1 then
            bar = bar .. "#"
        else
            bar = bar .. "."
        end
    end

    gfx.text(8, 100, bar)
    gfx.text(8, h - 12, "SPACE play  R restart  +/- BPM  ESC quit")
    gfx.refresh()
end

local gfx_started = false

local ok, err = pcall(function()
    gfx.begin()
    gfx_started = true

    configure_synth()
    draw()

    while not solaros.should_exit() do
        if playing then
            play_step(step)
            draw()

            local remaining = step_ms()
            while remaining > 0 and playing do
                local chunk = math.min(remaining, 25)
                local key = gfx.getch(chunk)

                if key == gfx.KEY_ESCAPE then
                    return
                elseif key == KEY_SPACE then
                    playing = false
                    synth.all_notes_off()
                    draw()
                elseif key == KEY_R then
                    step = 1
                    synth.all_notes_off()
                    draw()
                elseif key == KEY_PLUS or key == KEY_EQUALS then
                    bpm = math.min(180, bpm + 5)
                    draw()
                elseif key == KEY_MINUS then
                    bpm = math.max(70, bpm - 5)
                    draw()
                end

                remaining = remaining - chunk
            end

            if playing then
                step = step + 1
                if step > #pattern then
                    step = 1
                end
            end
        else
            local key = gfx.getch(50)

            if key == gfx.KEY_ESCAPE then
                return
            elseif key == KEY_SPACE then
                playing = true
                step = 1
                draw()
            elseif key == KEY_R then
                step = 1
                draw()
            elseif key == KEY_PLUS or key == KEY_EQUALS then
                bpm = math.min(180, bpm + 5)
                draw()
            elseif key == KEY_MINUS then
                bpm = math.max(70, bpm - 5)
                draw()
            end
        end
    end
end)

pcall(synth.all_notes_off)
pcall(synth.stop)

if gfx_started then
    pcall(function()
        gfx["end"]()
    end)
end

if not ok then
    local message = "Tiger Drive error: " .. tostring(err)
    pcall(solaros.clipboard.set, message)
    print(message)
end
