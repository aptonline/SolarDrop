# SolarDrop Multi-Source

SolarDrop is a local SolarOS Playground aggregator.

It combines:

- apps uploaded locally from your Mac;
- the official SolarOS Playground;
- any number of additional compatible Playground repositories/catalogs.

SolarOS itself still sees one catalog:

```text
http://<detected-ip>:8080/dist/catalog.json
```

## Start

Double-click **Start SolarDrop.command** or:

```bash
cd SolarDrop
python3 server.py
```

Open:

```text
http://<detected-ip>:8080
```

## Add sources

Use the **Remote sources** section in the web UI.

Accepted forms include:

```text
https://github.com/nilseuropa/solar_os_playground
https://github.com/another-user/their-playground
https://example.com/path/dist/catalog.json
```

SolarDrop downloads each catalog and mirrors its `.sopkg` files locally.

### Duplicate app IDs

Precedence is:

1. local SolarDrop apps;
2. the first enabled remote source;
3. later remote sources.

So a local app can intentionally override a community app with the same ID.

## SolarOS setup

Run once:

```text
playground source http://<detected-ip>:8080/dist/catalog.json
playground storage sd
playground refresh
```

When you change sources or upload/update apps:

1. click **Refresh all** in SolarDrop;
2. run `playground refresh` on SolarOS.

## Source configuration

Sources are stored in:

```text
sources.json
```

The official SolarOS Playground is included by default.

Remote packages are cached in:

```text
dist/remote/
```

If a source is temporarily unavailable, SolarDrop will use its cached catalog/packages where possible.

## Security

Playground apps are not sandboxed. Only add sources you trust.
SolarDrop itself has no authentication and is intended for a trusted home LAN.

## Local app management

Local Lua/Python apps now have a **Remove** button in the merged-apps table. Removing an app deletes its local source folder and generated local packages, then rebuilds the combined catalog. Remote-source apps are read-only.

The merged-apps table can also be filtered by **Category** and **Type** (`lua`/`python`) and sorted by **Name**, **Category**, **Type**, or **Version**, ascending or descending. These controls affect only the web view; the Playground catalog remains valid and unchanged in structure.

## App list controls

The web UI can search local/remote apps and filter by category and runtime, then sort the results.

## Theme

Click the sun icon beside the SolarDrop title to switch to dark mode. In dark mode it becomes a moon icon; click again to return to light mode. The browser remembers the selected theme.

## Automatic IP detection

SolarDrop now detects the Mac's active LAN IPv4 address each time it starts and
uses it for the Web UI and generated Playground catalog URL. No IP address is
hard-coded.

The detected address is printed at startup, for example:

```text
Web UI:  http://192.168.1.172:8080/
Catalog: http://192.168.1.172:8080/dist/catalog.json
```

If detection fails, SolarDrop falls back to `127.0.0.1`.

## Mobile layout

The SolarDrop web UI is responsive: controls stack on narrow screens, touch targets are enlarged, and app/source tables can be swiped horizontally on phones.
