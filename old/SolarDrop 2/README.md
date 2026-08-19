# SolarDrop Multi-Source

SolarDrop is a local SolarOS Playground aggregator.

It combines:

- apps uploaded locally from your Mac;
- the official SolarOS Playground;
- any number of additional compatible Playground repositories/catalogs.

SolarOS itself still sees one catalog:

```text
http://192.168.1.172:8080/dist/catalog.json
```

## Start

Double-click **Start SolarDrop.command** or:

```bash
cd SolarDrop
python3 server.py
```

Open:

```text
http://192.168.1.172:8080
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
playground source http://192.168.1.172:8080/dist/catalog.json
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
