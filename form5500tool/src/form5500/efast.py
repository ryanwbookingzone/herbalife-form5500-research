"""EFAST2 public Form 5500 Search (the same backend the public 5500Search web UI calls) + public filing PDF download.
Covers filings not yet in the bulk datasets (e.g., the current plan year)."""
import json, re, time
from pathlib import Path
import pandas as pd
import requests
from . import config

FIELDS = ["planyear", "pn", "ein", "plansponsor", "planname", "city", "state", "participantsboy", "assetseoy", "datereceived", "pdfpath"]

def _q(term):
    return term.replace('"', '\\"')

def search(ein=None, sponsor=None, plan_name=None, ack_id=None, size=200, raw_query=None):
    """Returns DataFrame of filings. Lucene fields: ein, plansponsor, planname, pn, planyear; ack via id."""
    if raw_query:
        q = raw_query
    elif ack_id:
        q = f"ackid:{ack_id}"
    elif ein:
        q = f"ein:{str(ein).replace('-', '')}"
    elif sponsor:
        q = " AND ".join(f"plansponsor:{_q(t)}" for t in re.findall(r"[A-Za-z0-9]+", sponsor))
    elif plan_name:
        q = " AND ".join(f"planname:{_q(t)}" for t in re.findall(r"[A-Za-z0-9]+", plan_name))
    else:
        raise ValueError("give ein, sponsor, plan_name, ack_id or raw_query")
    rows, start = [], 0
    while True:
        r = requests.get(config.EFAST_SEARCH, params={"q.parser": "lucene", "q": q, "size": size, "start": start},
                         headers=config.UA, timeout=60)
        r.raise_for_status()
        h = r.json().get("hits", {})
        for x in h.get("hit", []):
            d = {"ack_id": x["id"]}; d.update({k: x.get("fields", {}).get(k) for k in FIELDS}); rows.append(d)
        start += size
        if start >= min(h.get("found", 0), 5000) or not h.get("hit"):
            break
    df = pd.DataFrame(rows, columns=["ack_id"] + FIELDS)
    if ack_id and not df.empty:
        df = df[df.ack_id == ack_id]
    return df.sort_values(["ein", "pn", "planyear", "datereceived"]).reset_index(drop=True) if not df.empty else df

def pdf_url(pdfpath):
    return config.EFAST_PDF + pdfpath

def download_pdfs(df, out_dir=config.FILINGS_DIR, skip_existing=True, log=print):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    paths = []
    for _, r in df.iterrows():
        if not r.get("pdfpath"):
            continue
        p = out / f"EIN{r.ein}_PN{r.pn}_PY{r.planyear}_{r.ack_id}.pdf"
        if not (skip_existing and p.exists() and p.stat().st_size > 1000):
            resp = requests.get(pdf_url(r.pdfpath), headers=config.UA, timeout=300)
            if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
                log(f"  ! could not fetch {r.ack_id} ({resp.status_code})"); continue
            p.write_bytes(resp.content); time.sleep(0.2)
        paths.append(p)
    return paths

def signature_names(pdf_path):
    """Extract 'Signature of plan administrator' name/date from the facsimile PDF (requires pdftotext)."""
    import subprocess
    try:
        t = subprocess.run(["pdftotext", "-l", "2", str(pdf_path), "-"], capture_output=True, text=True, timeout=60).stdout
    except FileNotFoundError:
        return None
    m = re.search(r"(\d{2}/\d{2}/\d{4})\s+([A-Z][A-Z .'\-]+?)\s+Signature of plan administrator", t)
    return {"date": m.group(1), "name": m.group(2).strip()} if m else None
