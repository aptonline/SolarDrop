# SolarDrop

Local app delivery for SolarOS using the native Playground catalog.

## Start on the Mac

Double-click **Start SolarDrop.command**, or run:

```bash
cd SolarDrop
python3 server.py
```

Then open:

http://192.168.1.172:8080

Upload `.lua` or `.py` files in the web UI. SolarDrop packages them, calculates SHA-256/size, and regenerates the catalog.

## One-time setup on SolarOS

```text
playground source http://192.168.1.172:8080/dist/catalog.json
playground storage sd
playground refresh
```

Then:

```text
playground search sun
playground install suntracker
playground run suntracker
```

After changing/uploading an app on the Mac:

```text
playground refresh
playground install APP-ID
```

Playground will see the incremented version as an update.

## Direct downloads

SolarDrop also serves ordinary files over HTTP. For example:

```text
curl -o /sdcard/test.lua http://192.168.1.172:8080/apps/suntracker/main.lua
```

The server only listens on your LAN interface and has no authentication. Treat it as a trusted-home-network development tool.
