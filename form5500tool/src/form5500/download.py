"""Incremental download of DOL EBSA FOIA Form 5500 'Latest' datasets."""
import json, shutil, time
from pathlib import Path
import requests
from . import config

def url_for(name, year):
    return config.FOIA_URL.format(name=name, year=year)

def local_path(raw_dir, name, year):
    raw_dir = Path(raw_dir)
    for cand in (f"{name}_{year}_latest.zip", f"{name}_{year}_Latest.zip"):
        if (raw_dir / cand).exists():
            return raw_dir / cand
    return raw_dir / f"{name}_{year}_latest.zip"

def _manifest(raw_dir):
    p = Path(raw_dir) / "manifest.json"
    return p, (json.loads(p.read_text()) if p.exists() else {})

def head(name, year, session=None):
    s = session or requests
    r = s.head(url_for(name, year), headers=config.UA, allow_redirects=True, timeout=60)
    if r.status_code != 200:
        return None
    return {"size": int(r.headers.get("content-length", 0) or 0), "last_modified": r.headers.get("last-modified")}

def download(datasets, years, raw_dir=config.RAW_DIR, force=False, check_remote=True, log=print):
    """Download zips if missing or if the remote size/Last-Modified changed. Returns list of (name, year, path, status)."""
    raw_dir = Path(raw_dir); raw_dir.mkdir(parents=True, exist_ok=True)
    mpath, man = _manifest(raw_dir)
    out = []
    s = requests.Session()
    for y in years:
        for n in datasets:
            key = f"{n}:{y}"
            p = local_path(raw_dir, n, y)
            info = None
            if check_remote or not p.exists():
                try:
                    info = head(n, y, s)
                except requests.RequestException as e:
                    log(f"  ! HEAD failed {key}: {e}"); out.append((n, y, p, "error")); continue
                if info is None:
                    man[key] = {"missing": True, "checked": time.time()}
                    out.append((n, y, None, "missing")); continue
            fresh = p.exists() and p.stat().st_size > 0 and not force and (
                info is None or info["size"] in (0, p.stat().st_size))
            if fresh:
                man.setdefault(key, {}).update({"path": str(p), "size": p.stat().st_size})
                out.append((n, y, p, "cached")); continue
            tmp = p.with_suffix(".part")
            log(f"  downloading {key} ...")
            with s.get(url_for(n, y), headers=config.UA, stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            shutil.move(tmp, p)
            man[key] = {"path": str(p), "size": p.stat().st_size, "last_modified": (info or {}).get("last_modified"),
                        "downloaded": time.time()}
            out.append((n, y, p, "downloaded"))
            mpath.write_text(json.dumps(man, indent=1))
    mpath.write_text(json.dumps(man, indent=1))
    return out
