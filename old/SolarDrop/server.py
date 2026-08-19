#!/usr/bin/env python3
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import sys
import urllib.parse
import zipfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8080
BASE_URL = "http://192.168.1.172:8080"
ROOT = Path(__file__).resolve().parent
APPS = ROOT / "apps"
DIST = ROOT / "dist"
PACKAGES = DIST / "packages"

CATEGORIES = [
    {"id": "music", "order": 10, "title": "Music"},
    {"id": "utilities", "order": 20, "title": "Utilities"},
    {"id": "development", "order": 30, "title": "Development"},
    {"id": "examples", "order": 40, "title": "Examples"},
]

def slugify(name):
    name = Path(name).stem.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name or "app"

def display_name(app_id):
    return " ".join(p.capitalize() for p in app_id.split("-"))

def bump_patch(version):
    try:
        a, b, c = [int(x) for x in version.split(".")]
        return f"{a}.{b}.{c+1}"
    except Exception:
        return "1.0.0"

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def make_package(app_dir, manifest):
    app_id = manifest["id"]
    version = manifest["version"]
    out_dir = PACKAGES / app_id / version
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{app_id}-{version}.sopkg"

    # Ordinary ZIP, matching SolarOS Playground's package concept.
    # Store files at archive root so "entry" resolves directly.
    with zipfile.ZipFile(out_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(app_dir.iterdir(), key=lambda p: p.name):
            if path.is_file():
                zf.write(path, path.name)

    return out_file

def build_catalog():
    PACKAGES.mkdir(parents=True, exist_ok=True)
    catalog_apps = []

    for app_dir in sorted(APPS.iterdir() if APPS.exists() else []):
        if not app_dir.is_dir():
            continue
        mf = app_dir / "manifest.json"
        if not mf.exists():
            continue
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Skipping {app_dir.name}: bad manifest: {e}")
            continue

        entry = app_dir / manifest.get("entry", "")
        if not entry.exists():
            print(f"Skipping {app_dir.name}: entry file missing")
            continue

        package = make_package(app_dir, manifest)
        rel = package.relative_to(DIST).as_posix()

        item = dict(manifest)
        item["archive"] = rel
        item["sha256"] = sha256_file(package)
        item["size"] = package.stat().st_size
        catalog_apps.append(item)

    catalog = {
        "apps": catalog_apps,
        "categories": CATEGORIES,
        "repository": {"id": "solardrop", "name": "SolarDrop"},
        "schema": "solaros.playground.catalog",
        "schema_version": 1,
    }
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )
    return catalog

def install_uploaded(filename, data, category="development"):
    ext = Path(filename).suffix.lower()
    if ext not in (".lua", ".py"):
        raise ValueError("Only .lua and .py files are supported")

    app_id = slugify(filename)
    runtime = "lua" if ext == ".lua" else "python"
    app_dir = APPS / app_id
    app_dir.mkdir(parents=True, exist_ok=True)

    existing = {}
    mf_path = app_dir / "manifest.json"
    if mf_path.exists():
        try:
            existing = json.loads(mf_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    version = bump_patch(existing.get("version", "0.0.0"))
    entry_name = "main" + ext
    (app_dir / entry_name).write_bytes(data)

    requires = []
    min_solaros = "4.4.0"
    # Conservative defaults for likely graphical/audio Lua apps.
    lowered = data.lower()
    if b"gfx." in lowered or b"solaros.gfx" in lowered:
        requires.append("gfx")
    if b"synth." in lowered or b"solaros.synth" in lowered or b"audio." in lowered:
        requires.append("audio")
        min_solaros = "4.6.9"

    manifest = {
        "id": app_id,
        "name": existing.get("name", display_name(app_id)),
        "version": version,
        "runtime": runtime,
        "entry": entry_name,
        "category": category if category in {c["id"] for c in CATEGORIES} else "development",
        "description": existing.get("description", f"Local SolarDrop app: {display_name(app_id)}."),
        "author": existing.get("author", "Ade"),
        "min_solaros": existing.get("min_solaros", min_solaros),
        "tags": existing.get("tags", ["local", runtime]),
        "requires": existing.get("requires", requires),
    }
    mf_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    build_catalog()
    return manifest

def page(catalog):
    rows = []
    for app in catalog["apps"]:
        rows.append(
            f"<tr><td><b>{html.escape(app['name'])}</b><br><code>{html.escape(app['id'])}</code></td>"
            f"<td>{html.escape(app['runtime'])}</td>"
            f"<td>{html.escape(app['version'])}</td>"
            f"<td>{html.escape(app['category'])}</td>"
            f"<td>{html.escape(app.get('description',''))}</td></tr>"
        )
    rows_html = "\n".join(rows) or "<tr><td colspan=5>No apps yet.</td></tr>"
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>SolarDrop</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font:16px system-ui,-apple-system,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;background:#f5f5f5;color:#111}}
.card{{background:white;border:1px solid #ddd;border-radius:14px;padding:22px;margin:18px 0}}
h1{{margin-bottom:4px}} code{{background:#eee;padding:2px 5px;border-radius:4px}}
table{{width:100%;border-collapse:collapse}} td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}
button{{font:inherit;padding:10px 16px}} input,select{{font:inherit}}
.drop{{border:2px dashed #888;border-radius:12px;padding:32px;text-align:center}}
.small{{color:#555;font-size:14px}}
</style>
</head>
<body>
<h1>☀ SolarDrop</h1>
<p>Local SolarOS Playground at <code>{BASE_URL}</code></p>
<div class="card">
<h2>Add an app</h2>
<form id="upload">
<div class="drop">
<input id="file" type="file" accept=".lua,.py" required>
&nbsp;
<select id="category">
<option>development</option><option>music</option><option>utilities</option><option>examples</option>
</select>
&nbsp;
<button>Upload & package</button>
</div>
</form>
<p id="status" class="small">Uploading the same filename automatically increments its patch version.</p>
</div>
<div class="card">
<h2>SolarOS setup</h2>
<p>Run these once on SolarOS:</p>
<pre>playground source {BASE_URL}/dist/catalog.json
playground storage sd
playground refresh</pre>
<p>Then install/run, for example:</p>
<pre>playground install suntracker
playground run suntracker</pre>
</div>
<div class="card">
<h2>Apps</h2>
<table><thead><tr><th>App</th><th>Runtime</th><th>Version</th><th>Category</th><th>Description</th></tr></thead>
<tbody>{rows_html}</tbody></table>
</div>
<script>
document.getElementById('upload').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const f=document.getElementById('file').files[0];
  const cat=document.getElementById('category').value;
  const s=document.getElementById('status');
  if(!f) return;
  s.textContent='Uploading '+f.name+'…';
  const q=new URLSearchParams({{filename:f.name,category:cat}});
  const r=await fetch('/api/upload?'+q, {{method:'POST', body:await f.arrayBuffer()}});
  const t=await r.text();
  s.textContent=t;
  if(r.ok) setTimeout(()=>location.reload(),500);
}});
</script>
</body>
</html>"""

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Serve relative to SolarDrop root regardless of current working directory.
        parsed = urllib.parse.urlsplit(path)
        rel = urllib.parse.unquote(parsed.path).lstrip("/")
        return str((ROOT / rel).resolve())

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/":
            catalog = build_catalog()
            body = page(catalog).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/catalog":
            body = json.dumps(build_catalog(), indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != "/api/upload":
            self.send_error(404)
            return
        q = urllib.parse.parse_qs(parsed.query)
        filename = q.get("filename", [""])[0]
        category = q.get("category", ["development"])[0]
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1024 * 1024:
            self.send_error(400, "File must be 1 byte to 1 MiB")
            return
        data = self.rfile.read(length)
        try:
            manifest = install_uploaded(filename, data, category)
            msg = f"Added {manifest['id']} {manifest['version']}. Run 'playground refresh' on SolarOS."
            body = msg.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(400, str(e))

if __name__ == "__main__":
    APPS.mkdir(parents=True, exist_ok=True)
    build_catalog()
    print("SolarDrop")
    print(f"Web UI:     {BASE_URL}/")
    print(f"Catalog:    {BASE_URL}/dist/catalog.json")
    print("")
    print("SolarOS one-time setup:")
    print(f"  playground source {BASE_URL}/dist/catalog.json")
    print("  playground storage sd")
    print("  playground refresh")
    print("")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nSolarDrop stopped.")
