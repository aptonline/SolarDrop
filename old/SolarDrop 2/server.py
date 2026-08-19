#!/usr/bin/env python3
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
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
REMOTE = DIST / "remote"
SOURCES_FILE = ROOT / "sources.json"

LOCAL_CATEGORIES = [
    {"id": "music", "order": 15, "title": "Music"},
    {"id": "utilities", "order": 20, "title": "Utilities"},
    {"id": "development", "order": 40, "title": "Development"},
    {"id": "examples", "order": 50, "title": "Examples"},
]

DEFAULT_SOURCES = {
    "sources": [
        {
            "id": "official",
            "name": "SolarOS Playground",
            "url": "https://github.com/nilseuropa/solar_os_playground",
            "enabled": True,
        }
    ]
}

def json_load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def json_save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

def ensure_sources():
    if not SOURCES_FILE.exists():
        json_save(SOURCES_FILE, DEFAULT_SOURCES)

def load_sources():
    ensure_sources()
    data = json_load(SOURCES_FILE, DEFAULT_SOURCES)
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    return sources

def save_sources(sources):
    json_save(SOURCES_FILE, {"sources": sources})

def safe_id(value):
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "source"

def slugify(name):
    return safe_id(Path(name).stem)

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

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def normalize_catalog_url(url):
    url = url.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(url)

    if parsed.netloc.lower() == "github.com":
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            return f"https://raw.githubusercontent.com/{owner}/{repo}/main/dist/catalog.json"

    if url.endswith(".json"):
        return url

    return url + "/dist/catalog.json"

def request_bytes(url, timeout=12):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SolarDrop/2.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()

def resolve_archive_url(catalog_url, archive):
    return urllib.parse.urljoin(catalog_url, archive)

def make_local_package(app_dir, manifest):
    app_id = manifest["id"]
    version = manifest["version"]
    out_dir = PACKAGES / app_id / version
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{app_id}-{version}.sopkg"

    with zipfile.ZipFile(out_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(app_dir.iterdir(), key=lambda p: p.name):
            if path.is_file():
                zf.write(path, path.name)

    return out_file

def build_local_apps():
    apps = []
    for app_dir in sorted(APPS.iterdir() if APPS.exists() else []):
        if not app_dir.is_dir():
            continue

        manifest_path = app_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        manifest = json_load(manifest_path, {})
        if not manifest:
            continue

        entry = app_dir / manifest.get("entry", "")
        if not entry.exists():
            print(f"Skipping local {app_dir.name}: missing entry")
            continue

        package = make_local_package(app_dir, manifest)
        item = dict(manifest)
        item["archive"] = package.relative_to(DIST).as_posix()
        item["sha256"] = sha256_file(package)
        item["size"] = package.stat().st_size
        item["_solardrop_source"] = "local"
        apps.append(item)

    return apps

def mirror_remote_source(source):
    source_id = safe_id(source.get("id", "source"))
    source_name = source.get("name", source_id)
    catalog_url = normalize_catalog_url(source.get("url", ""))

    if not catalog_url:
        raise ValueError("source URL is empty")

    raw = request_bytes(catalog_url)
    catalog = json.loads(raw.decode("utf-8"))

    if catalog.get("schema") != "solaros.playground.catalog":
        raise ValueError("not a SolarOS Playground catalog")

    out_apps = []
    source_root = REMOTE / source_id
    source_root.mkdir(parents=True, exist_ok=True)

    for app in catalog.get("apps", []):
        archive = app.get("archive")
        app_id = app.get("id")
        version = app.get("version")
        expected_sha = app.get("sha256")
        expected_size = app.get("size")

        if not archive or not app_id or not version:
            continue

        archive_url = resolve_archive_url(catalog_url, archive)
        target_dir = source_root / "packages" / safe_id(app_id) / str(version)
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = Path(urllib.parse.urlsplit(archive).path).name
        if not filename:
            filename = f"{safe_id(app_id)}-{version}.sopkg"
        target = target_dir / filename

        valid_cache = False
        if target.exists():
            if expected_size is not None and target.stat().st_size != int(expected_size):
                valid_cache = False
            elif expected_sha and sha256_file(target) != expected_sha:
                valid_cache = False
            else:
                valid_cache = True

        if not valid_cache:
            package_data = request_bytes(archive_url)
            if expected_size is not None and len(package_data) != int(expected_size):
                raise ValueError(f"{app_id}: package size mismatch")
            if expected_sha and sha256_bytes(package_data) != expected_sha:
                raise ValueError(f"{app_id}: package SHA-256 mismatch")
            target.write_bytes(package_data)

        item = dict(app)
        item["archive"] = target.relative_to(DIST).as_posix()
        item["size"] = target.stat().st_size
        item["sha256"] = sha256_file(target)
        item["_solardrop_source"] = source_id
        item["_solardrop_source_name"] = source_name
        out_apps.append(item)

    return {
        "source": source,
        "catalog_url": catalog_url,
        "repository": catalog.get("repository", {}),
        "categories": catalog.get("categories", []),
        "apps": out_apps,
    }

def cached_remote_source(source):
    source_id = safe_id(source.get("id", "source"))
    source_name = source.get("name", source_id)
    source_root = REMOTE / source_id
    meta_path = source_root / "cache.json"
    if not meta_path.exists():
        return None

    cache = json_load(meta_path, None)
    if not cache:
        return None

    apps = []
    for app in cache.get("apps", []):
        rel = app.get("archive", "")
        target = DIST / rel
        if target.exists():
            apps.append(app)

    return {
        "source": source,
        "catalog_url": cache.get("catalog_url", ""),
        "repository": cache.get("repository", {}),
        "categories": cache.get("categories", []),
        "apps": apps,
    }

def save_remote_cache(result):
    source_id = safe_id(result["source"].get("id", "source"))
    source_root = REMOTE / source_id
    source_root.mkdir(parents=True, exist_ok=True)
    json_save(source_root / "cache.json", {
        "catalog_url": result["catalog_url"],
        "repository": result["repository"],
        "categories": result["categories"],
        "apps": result["apps"],
    })

def fetch_sources():
    results = []
    statuses = []

    for source in load_sources():
        if not source.get("enabled", True):
            statuses.append({
                "id": source.get("id", ""),
                "name": source.get("name", ""),
                "ok": False,
                "disabled": True,
                "message": "disabled",
                "apps": 0,
            })
            continue

        try:
            result = mirror_remote_source(source)
            save_remote_cache(result)
            results.append(result)
            statuses.append({
                "id": source.get("id", ""),
                "name": source.get("name", ""),
                "ok": True,
                "disabled": False,
                "message": "updated",
                "apps": len(result["apps"]),
            })
        except Exception as exc:
            cached = cached_remote_source(source)
            if cached:
                results.append(cached)
                statuses.append({
                    "id": source.get("id", ""),
                    "name": source.get("name", ""),
                    "ok": False,
                    "disabled": False,
                    "message": f"offline/error; using cache: {exc}",
                    "apps": len(cached["apps"]),
                })
            else:
                statuses.append({
                    "id": source.get("id", ""),
                    "name": source.get("name", ""),
                    "ok": False,
                    "disabled": False,
                    "message": str(exc),
                    "apps": 0,
                })

    return results, statuses

def merge_catalog(refresh_remote=False):
    PACKAGES.mkdir(parents=True, exist_ok=True)
    REMOTE.mkdir(parents=True, exist_ok=True)

    local_apps = build_local_apps()

    if refresh_remote:
        remote_results, statuses = fetch_sources()
        json_save(DIST / "source-status.json", statuses)
    else:
        remote_results = []
        statuses = json_load(DIST / "source-status.json", [])
        for source in load_sources():
            if source.get("enabled", True):
                cached = cached_remote_source(source)
                if cached:
                    remote_results.append(cached)

    # Precedence:
    # 1. local apps
    # 2. earlier source in sources.json
    # Duplicate IDs from later sources are ignored.
    merged = {}
    for app in local_apps:
        merged[app["id"]] = app

    for result in remote_results:
        for app in result["apps"]:
            if app["id"] not in merged:
                merged[app["id"]] = app

    categories = {}
    for cat in LOCAL_CATEGORIES:
        categories[cat["id"]] = dict(cat)

    for result in remote_results:
        for cat in result.get("categories", []):
            cat_id = cat.get("id")
            if cat_id and cat_id not in categories:
                categories[cat_id] = dict(cat)

    apps_out = []
    for app in merged.values():
        clean = {k: v for k, v in app.items() if not k.startswith("_solardrop_")}
        apps_out.append(clean)

    apps_out.sort(key=lambda a: (a.get("category", ""), a.get("name", a.get("id", ""))))

    catalog = {
        "apps": apps_out,
        "categories": sorted(categories.values(), key=lambda c: (c.get("order", 999), c.get("title", ""))),
        "repository": {"id": "solardrop-aggregate", "name": "SolarDrop Aggregate"},
        "schema": "solaros.playground.catalog",
        "schema_version": 1,
    }

    DIST.mkdir(parents=True, exist_ok=True)
    json_save(DIST / "catalog.json", catalog)
    return catalog, statuses

def install_uploaded(filename, data, category="development"):
    ext = Path(filename).suffix.lower()
    if ext not in (".lua", ".py"):
        raise ValueError("Only .lua and .py files are supported")

    app_id = slugify(filename)
    runtime = "lua" if ext == ".lua" else "python"
    app_dir = APPS / app_id
    app_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = app_dir / "manifest.json"
    existing = json_load(manifest_path, {})

    version = bump_patch(existing.get("version", "0.0.0"))
    entry_name = "main" + ext
    (app_dir / entry_name).write_bytes(data)

    requires = []
    min_solaros = "4.4.0"
    lowered = data.lower()

    if b"gfx." in lowered or b"solaros.gfx" in lowered:
        requires.append("gfx")
    if b"synth." in lowered or b"solaros.synth" in lowered or b"audio." in lowered:
        requires.append("audio")
        min_solaros = "4.6.9"

    valid_categories = {c["id"] for c in LOCAL_CATEGORIES}
    if category not in valid_categories:
        category = "development"

    manifest = {
        "id": app_id,
        "name": existing.get("name", display_name(app_id)),
        "version": version,
        "runtime": runtime,
        "entry": entry_name,
        "category": category,
        "description": existing.get("description", f"Local SolarDrop app: {display_name(app_id)}."),
        "author": existing.get("author", "Ade"),
        "min_solaros": existing.get("min_solaros", min_solaros),
        "tags": existing.get("tags", ["local", runtime]),
        "requires": existing.get("requires", requires),
    }

    json_save(manifest_path, manifest)
    merge_catalog(refresh_remote=False)
    return manifest

def add_source(name, url):
    if not url.strip():
        raise ValueError("URL is required")

    sources = load_sources()
    source_id = safe_id(name or urllib.parse.urlsplit(url).netloc or "source")

    existing_ids = {s.get("id") for s in sources}
    base = source_id
    n = 2
    while source_id in existing_ids:
        source_id = f"{base}-{n}"
        n += 1

    source = {
        "id": source_id,
        "name": name.strip() or source_id,
        "url": url.strip(),
        "enabled": True,
    }
    sources.append(source)
    save_sources(sources)
    return source

def delete_source(source_id):
    sources = load_sources()
    source_id = safe_id(source_id)
    kept = [s for s in sources if safe_id(s.get("id", "")) != source_id]
    if len(kept) == len(sources):
        raise ValueError("Source not found")
    save_sources(kept)
    shutil.rmtree(REMOTE / source_id, ignore_errors=True)
    merge_catalog(refresh_remote=False)

def toggle_source(source_id):
    sources = load_sources()
    source_id = safe_id(source_id)
    found = False
    for source in sources:
        if safe_id(source.get("id", "")) == source_id:
            source["enabled"] = not source.get("enabled", True)
            found = True
            break
    if not found:
        raise ValueError("Source not found")
    save_sources(sources)
    merge_catalog(refresh_remote=False)

def source_status_map(statuses):
    return {safe_id(s.get("id", "")): s for s in statuses}

def page(catalog, statuses):
    status_map = source_status_map(statuses)

    source_rows = []
    for source in load_sources():
        sid = safe_id(source.get("id", ""))
        st = status_map.get(sid, {})
        state = "disabled" if not source.get("enabled", True) else st.get("message", "not refreshed")
        apps = st.get("apps", 0)
        checked = "checked" if source.get("enabled", True) else ""
        source_rows.append(
            "<tr>"
            f"<td><b>{html.escape(source.get('name', sid))}</b><br><code>{html.escape(sid)}</code></td>"
            f"<td class='url'>{html.escape(source.get('url',''))}</td>"
            f"<td>{apps}</td>"
            f"<td>{html.escape(str(state))}</td>"
            "<td>"
            f"<button onclick=\"postAction('/api/source/toggle?id={urllib.parse.quote(sid)}')\">"
            f"{'Disable' if checked else 'Enable'}</button> "
            f"<button class='danger' onclick=\"if(confirm('Remove source?'))postAction('/api/source/delete?id={urllib.parse.quote(sid)}')\">Remove</button>"
            "</td></tr>"
        )

    if not source_rows:
        source_rows.append("<tr><td colspan='5'>No remote sources configured.</td></tr>")

    app_rows = []
    for app in catalog.get("apps", []):
        app_rows.append(
            "<tr>"
            f"<td><b>{html.escape(app.get('name',app.get('id','')))}</b><br><code>{html.escape(app.get('id',''))}</code></td>"
            f"<td>{html.escape(app.get('runtime',''))}</td>"
            f"<td>{html.escape(app.get('version',''))}</td>"
            f"<td>{html.escape(app.get('category',''))}</td>"
            f"<td>{html.escape(app.get('description',''))}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>SolarDrop</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font:16px system-ui,-apple-system,sans-serif;max-width:1100px;margin:35px auto;padding:0 20px;background:#f5f5f5;color:#111}}
.card{{background:white;border:1px solid #ddd;border-radius:14px;padding:22px;margin:18px 0}}
h1{{margin-bottom:4px}} code{{background:#eee;padding:2px 5px;border-radius:4px}}
table{{width:100%;border-collapse:collapse}} td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}
button{{font:inherit;padding:8px 12px}} input,select{{font:inherit;padding:7px}}
.drop{{border:2px dashed #888;border-radius:12px;padding:24px;text-align:center}}
.small{{color:#555;font-size:14px}} .url{{word-break:break-all;max-width:360px}}
.danger{{color:#8b0000}} .row{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.row input[type=text]{{min-width:240px;flex:1}}
pre{{white-space:pre-wrap}}
</style>
</head>
<body>
<h1>☀ SolarDrop</h1>
<p>Aggregate Playground source at <code>{BASE_URL}/dist/catalog.json</code></p>

<div class="card">
<h2>Remote sources</h2>
<form id="sourceForm" class="row">
<input id="sourceName" type="text" placeholder="Name, e.g. Official">
<input id="sourceUrl" type="text" placeholder="GitHub repo or catalog.json URL" required>
<button>Add source</button>
<button type="button" onclick="postAction('/api/sources/refresh')">Refresh all</button>
</form>
<p class="small">Local apps always win duplicate IDs. Earlier remote sources win over later ones.</p>
<table>
<thead><tr><th>Source</th><th>URL</th><th>Apps</th><th>Status</th><th>Actions</th></tr></thead>
<tbody>{''.join(source_rows)}</tbody>
</table>
</div>

<div class="card">
<h2>Add a local app</h2>
<form id="upload">
<div class="drop">
<input id="file" type="file" accept=".lua,.py" required>
<select id="category">
<option>development</option><option>music</option><option>utilities</option><option>examples</option>
</select>
<button>Upload & package</button>
</div>
</form>
<p id="status" class="small">Uploading the same filename increments its patch version.</p>
</div>

<div class="card">
<h2>SolarOS setup</h2>
<pre>playground source {BASE_URL}/dist/catalog.json
playground storage sd
playground refresh</pre>
<p>After changing sources or uploading apps, click <b>Refresh all</b> here, then run <code>playground refresh</code> on SolarOS.</p>
</div>

<div class="card">
<h2>Merged apps ({len(catalog.get('apps', []))})</h2>
<table>
<thead><tr><th>App</th><th>Runtime</th><th>Version</th><th>Category</th><th>Description</th></tr></thead>
<tbody>{''.join(app_rows) or "<tr><td colspan='5'>No apps.</td></tr>"}</tbody>
</table>
</div>

<script>
async function postAction(url, body=null) {{
  const opts={{method:'POST'}};
  if(body!==null) opts.body=body;
  const r=await fetch(url,opts);
  const t=await r.text();
  if(!r.ok) alert(t); else location.reload();
}}

document.getElementById('sourceForm').addEventListener('submit', async (e)=>{{
  e.preventDefault();
  const q=new URLSearchParams({{
    name:document.getElementById('sourceName').value,
    url:document.getElementById('sourceUrl').value
  }});
  await postAction('/api/source/add?'+q);
}});

document.getElementById('upload').addEventListener('submit', async (e)=>{{
  e.preventDefault();
  const f=document.getElementById('file').files[0];
  const cat=document.getElementById('category').value;
  const s=document.getElementById('status');
  if(!f)return;
  s.textContent='Uploading '+f.name+'…';
  const q=new URLSearchParams({{filename:f.name,category:cat}});
  const r=await fetch('/api/upload?'+q,{{method:'POST',body:await f.arrayBuffer()}});
  const t=await r.text();
  s.textContent=t;
  if(r.ok)setTimeout(()=>location.reload(),400);
}});
</script>
</body>
</html>"""

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed = urllib.parse.urlsplit(path)
        rel = urllib.parse.unquote(parsed.path).lstrip("/")
        return str((ROOT / rel).resolve())

    def send_text(self, status, text):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)

        if parsed.path == "/":
            catalog, statuses = merge_catalog(refresh_remote=False)
            body = page(catalog, statuses).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/catalog":
            catalog, _ = merge_catalog(refresh_remote=False)
            body = json.dumps(catalog, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if parsed.path == "/api/upload":
                filename = query.get("filename", [""])[0]
                category = query.get("category", ["development"])[0]
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1024 * 1024:
                    raise ValueError("File must be 1 byte to 1 MiB")
                data = self.rfile.read(length)
                manifest = install_uploaded(filename, data, category)
                self.send_text(200, f"Added {manifest['id']} {manifest['version']}")
                return

            if parsed.path == "/api/source/add":
                source = add_source(
                    query.get("name", [""])[0],
                    query.get("url", [""])[0]
                )
                merge_catalog(refresh_remote=True)
                self.send_text(200, f"Added source {source['id']}")
                return

            if parsed.path == "/api/source/delete":
                delete_source(query.get("id", [""])[0])
                self.send_text(200, "Source removed")
                return

            if parsed.path == "/api/source/toggle":
                toggle_source(query.get("id", [""])[0])
                self.send_text(200, "Source toggled")
                return

            if parsed.path == "/api/sources/refresh":
                catalog, statuses = merge_catalog(refresh_remote=True)
                good = sum(1 for s in statuses if s.get("ok"))
                self.send_text(200, f"Refreshed {good}/{len(statuses)} sources; {len(catalog['apps'])} merged apps")
                return

            self.send_error(404)

        except Exception as exc:
            self.send_text(400, str(exc))

if __name__ == "__main__":
    APPS.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    ensure_sources()

    # Build immediately. Remote failures fall back to cache.
    catalog, statuses = merge_catalog(refresh_remote=True)

    print("SolarDrop Multi-Source")
    print(f"Web UI:  {BASE_URL}/")
    print(f"Catalog: {BASE_URL}/dist/catalog.json")
    print(f"Apps:    {len(catalog['apps'])}")
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
