-- SunTracker v0.4 compatibility build
-- Uses only synth calls already proven by the working synth test.
-- Any fatal error is copied to the SolarOS clipboard.
--
-- After a failure, run this tiny Lua command/script to retrieve it:
--   print(solaros.clipboard.get())
--
-- Controls:
--   SPACE  play / stop
--   R      restart demo
--   + / -  tempo
--   ESC    quit

local gfx = solaros.gfx
local synth = solaros.synth

local KEY_SPACE = 32
local KEY_PLUS = 43
local KEY_EQUALS = 61
local KEY_MINUS = 45
local KEY_R = 114

local bpm = 120
local playing = false
local row = 1

-- Four-note demo pattern. false/nil means no note in that slot.
-- MIDI note values are converted to Hz immediately before playback.
local song = {
    {60, 64, 67, 72}, -- C
    {62, 65, 69, 74}, -- Dm
    {64, 67, 71, 76}, -- Em
    {60, 64, 67, 72}, -- C

    {57, 60, 64, 69}, -- Am
    {55, 59, 62, 67}, -- G
    {53, 57, 60, 65}, -- F
    {55, 59, 62, 67}, -- G

    {60, 64, 67, 72}, -- C
    {64, 67, 71, 76}, -- Em
    {65, 69, 72, 77}, -- F
    {67, 71, 74, 79}, -- G

    {57, 60, 64, 69}, -- Am
    {53, 57, 60, 65}, -- F
    {55, 59, 62, 67}, -- G
    {60, 64, 67, 72}, -- C
}

local NOTE_NAMES = {
    "C-", "C#", "D-", "D#", "E-", "F-",
    "F#", "G-", "G#", "A-", "A#", "B-"
}

local function midi_to_freq(midi)
    return math.floor(440 * (2 ^ ((midi - 69) / 12)) + 0.5)
end

local function midi_name(midi)
    local n = NOTE_NAMES[(midi % 12) + 1]
    local oct = math.floor(midi / 12) - 1
    return n .. tostring(oct)
end

local function step_ms()
    -- one tracker row = one eighth note
    return math.floor((60000 / bpm) / 2)
end

local function configure_synth()
    -- EXACTLY the calls/shape used by the working synth test.
    synth.configure("square", 5, 80, 65, 140)
    synth.configure_oscillator2("square", 0, 7, 25)
    synth.configure_performance(true, 0)
end

local function play_row(index)
    -- Compatibility approach: clear the whole chord and retrigger it.
    -- Avoids relying on note_off() until the basic tracker is confirmed.
    synth.all_notes_off()

    local chord = song[index]
    for i = 1, 4 do
        local note = chord[i]
        if note ~= nil and note ~= false then
            synth.note_on(midi_to_freq(note), 100)
        end
    end
end

local function draw()
    local w, h = gfx.size()

    gfx.clear(gfx.WHITE)
    gfx.color(gfx.BLACK)

    gfx.font(gfx.FONT_BOLD_14)
    gfx.text(8, 18, "SunTracker v0.4")

    gfx.font(gfx.FONT_MONO_12)
    gfx.text(8, 36, "BPM " .. tostring(bpm) ..
        "   " .. (playing and "PLAY" or "STOP"))

    gfx.text(8, 56, "ROW   CH1  CH2  CH3  CH4")

    local y = 74
    local first = row - 3
    if first < 1 then first = 1 end
    if first > #song - 7 then first = math.max(1, #song - 7) end

    for r = first, math.min(first + 7, #song) do
        local prefix = " "
        if r == row then prefix = ">" end

        local line = prefix .. string.format("%02d", r - 1)
        for ch = 1, 4 do
            line = line .. "  " .. midi_name(song[r][ch])
        end

        gfx.text(8, y, line)
        y = y + 14
    end

    gfx.text(8, h - 12, "SPACE play  R restart  +/- BPM  ESC quit")
    gfx.refresh()
end

local gfx_started = false

local ok, err = pcall(function()
    -- gfx.begin is INSIDE pcall in this diagnostic build.
    gfx.begin()
    gfx_started = true

    configure_synth()
    draw()

    while not solaros.should_exit() do
        if playing then
            play_row(row)
            draw()

            -- Let gfx.getch provide the row timing, just as the official
            -- Snake example uses timed getch polling.
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
                    row = 1
                    synth.all_notes_off()
                    draw()
                elseif key == KEY_PLUS or key == KEY_EQUALS then
                    bpm = math.min(240, bpm + 5)
                    draw()
                elseif key == KEY_MINUS then
                    bpm = math.max(40, bpm - 5)
                    draw()
                end

                remaining = remaining - chunk
            end

            if playing then
                row = row + 1
                if row > #song then
                    row = 1
                end
            end
        else
            local key = gfx.getch(50)

            if key == gfx.KEY_ESCAPE then
                return
            elseif key == KEY_SPACE then
                playing = true
                row = 1
                draw()
            elseif key == KEY_R then
                row = 1
                draw()
            elseif key == KEY_PLUS or key == KEY_EQUALS then
                bpm = math.min(240, bpm + 5)
                draw()
            elseif key == KEY_MINUS then
                bpm = math.max(40, bpm - 5)
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
    local message = "SunTracker v0.4 error: " .. tostring(err)

    -- Keep the error somewhere that survives the foreground app closing.
    pcall(solaros.clipboard.set, message)

    -- Also print it in case the invoking terminal is visible.
    print(message)
end
