"""Watch mode: diff EFAST2 filings for a watchlist of EINs against saved state. Suitable for a weekly cron."""
import json, datetime as dt
from pathlib import Path
from . import efast, config

def run(watchlist_path, state_path=None, download=True, out_dir=None, log=print):
    wl = json.loads(Path(watchlist_path).read_text())  # {"eins": ["953954565", ...]} or [{"ein":..., "label":...}]
    items = (wl.get("eins") or wl.get("companies") or []) if isinstance(wl, dict) else wl
    items = [i if isinstance(i, dict) else {"ein": str(i)} for i in items]
    state_path = Path(state_path or Path(watchlist_path).with_suffix(".state.json"))
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    report = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "new": []}
    for it in items:
        ein = str(it["ein"]).replace("-", "")
        df = efast.search(ein=ein)
        seen = set(state.get(ein, []))
        new = df[~df.ack_id.isin(seen)] if not df.empty else df
        if seen and not new.empty or (not seen and it.get("report_initial")):
            for _, r in new.iterrows():
                report["new"].append({"ein": ein, "label": it.get("label"), "ack_id": r.ack_id, "plan_year": r.planyear, "pn": r.pn,
                                      "sponsor": r.plansponsor, "plan": r.planname, "received": r.datereceived, "pdf": efast.pdf_url(r.pdfpath) if r.pdfpath else None})
            if download and not new.empty:
                efast.download_pdfs(new, out_dir or (config.FILINGS_DIR / ein), log=log)
        state[ein] = sorted(seen | set(df.ack_id)) if not df.empty else sorted(seen)
        log(f"  {ein}: {len(df)} filings, {len(new) if seen else 0} new")
    state_path.write_text(json.dumps(state, indent=1))
    return report
