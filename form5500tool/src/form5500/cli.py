"""form5500 command-line interface."""
import argparse, json, sys
from pathlib import Path
import pandas as pd
from . import brokers, config, db, download, efast, query

def _years(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out

def _show(df, args):
    if getattr(args, "out", None):
        p = Path(args.out)
        (df.to_excel(p, index=False) if p.suffix == ".xlsx" else df.to_csv(p, index=False)); print(f"wrote {p} ({len(df)} rows)")
    else:
        with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 50, "display.max_rows", 500):
            print(df.to_string(index=False) if not df.empty else "(no rows)")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="form5500", description=__doc__)
    ap.add_argument("--db", default=str(config.DB_PATH)); ap.add_argument("--raw-dir", default=str(config.RAW_DIR))
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("download", help="incremental download of DOL FOIA zips")
    p.add_argument("--years", required=True); p.add_argument("--datasets", default="core", help="core|all|comma list")
    p.add_argument("--force", action="store_true"); p.add_argument("--no-check-remote", action="store_true")
    p = sp.add_parser("load", help="load downloaded zips into DuckDB (incremental)")
    p.add_argument("--years", required=True); p.add_argument("--datasets", default="core"); p.add_argument("--force", action="store_true")
    p = sp.add_parser("update", help="download + load"); p.add_argument("--years", required=True); p.add_argument("--datasets", default="core")
    sp.add_parser("status", help="what is loaded")
    p = sp.add_parser("layout", help="show DOL layout text shipped in zips"); p.add_argument("dataset"); p.add_argument("--year", type=int)
    p = sp.add_parser("company", help="filings for an EIN"); p.add_argument("ein"); p.add_argument("--out")
    p = sp.add_parser("search", help="fuzzy sponsor name search"); p.add_argument("name"); p.add_argument("--state"); p.add_argument("--city")
    p.add_argument("--limit", type=int, default=25); p.add_argument("--out")
    p = sp.add_parser("plans", help="filter plans by geography/size"); p.add_argument("--state"); p.add_argument("--city"); p.add_argument("--year", type=int)
    p.add_argument("--min-participants", type=int); p.add_argument("--max-participants", type=int); p.add_argument("--welfare", action="store_true")
    p.add_argument("--limit", type=int, default=500); p.add_argument("--out")
    p = sp.add_parser("broker", help="plans where a broker appears (prospect list)"); p.add_argument("name"); p.add_argument("--year", type=int)
    p.add_argument("--state"); p.add_argument("--min-participants", type=int); p.add_argument("--limit", type=int, default=2000); p.add_argument("--out")
    p = sp.add_parser("carrier", help="plans with a carrier"); p.add_argument("name"); p.add_argument("--year", type=int); p.add_argument("--state")
    p.add_argument("--limit", type=int, default=2000); p.add_argument("--out")
    p = sp.add_parser("brokers", help="broker-of-record timeline + changes for an EIN"); p.add_argument("ein"); p.add_argument("--pn"); p.add_argument("--out")
    p = sp.add_parser("changes", help="market-wide broker-change prospects for a plan year"); p.add_argument("--year", type=int, required=True)
    p.add_argument("--state"); p.add_argument("--min-participants", type=int); p.add_argument("--from-broker"); p.add_argument("--to-broker")
    p.add_argument("--limit", type=int, default=5000); p.add_argument("--out")
    p = sp.add_parser("report", help="full company report (PDF+Excel+CSV)"); p.add_argument("ein"); p.add_argument("--out-dir", default=".")
    p.add_argument("--efast", action="store_true", help="include EFAST2 live index"); p.add_argument("--pdfs", action="store_true", help="also download filing PDFs")
    p = sp.add_parser("efast", help="EFAST2 live search"); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ein"); g.add_argument("--sponsor"); g.add_argument("--ack"); g.add_argument("--query")
    p.add_argument("--download", metavar="DIR"); p.add_argument("--out")
    p = sp.add_parser("watch", help="diff new EFAST2 filings for a watchlist JSON"); p.add_argument("watchlist"); p.add_argument("--state")
    p.add_argument("--no-download", action="store_true"); p.add_argument("--out-dir"); p.add_argument("--json-out")
    p = sp.add_parser("serve", help="run REST API"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8787)
    a = ap.parse_args(argv)

    ds = lambda s: config.CORE if s == "core" else config.DATASETS if s == "all" else s.split(",")
    if a.cmd in ("download", "update"):
        for n, y, pth, st in download.download(ds(a.datasets), _years(a.years), a.raw_dir, force=getattr(a, "force", False),
                                               check_remote=not getattr(a, "no_check_remote", False)):
            if st != "cached": print(f"{st:10} {n} {y}")
    if a.cmd in ("load", "update"):
        con = db.connect(a.db); db.load(con, ds(a.datasets), _years(a.years), a.raw_dir, force=getattr(a, "force", False)); return
    if a.cmd == "download": return
    if a.cmd == "serve":
        import os, uvicorn; os.environ["FORM5500_DB"] = a.db; uvicorn.run("form5500.api:app", host=a.host, port=a.port); return
    if a.cmd == "efast":
        df = efast.search(ein=a.ein, sponsor=a.sponsor, ack_id=a.ack, raw_query=a.query)
        if a.download: print("\n".join(map(str, efast.download_pdfs(df, a.download))))
        return _show(df, a)
    if a.cmd == "watch":
        from . import watch
        rep = watch.run(a.watchlist, a.state, download=not a.no_download, out_dir=a.out_dir)
        js = json.dumps(rep, indent=1, default=str)
        (Path(a.json_out).write_text(js) if a.json_out else print(js)); sys.exit(0 if not rep["new"] else 10)
    con = db.connect(a.db, read_only=True)
    if a.cmd == "status":
        for n, ys, rows in db.status(con): print(f"{n:28} {rows:>12,}  years {ys}")
    elif a.cmd == "layout":
        q = "select dataset, year, file, text from _layouts where dataset=?" + (" and year=?" if a.year else "") + " order by year desc limit 1"
        r = con.execute(q, [a.dataset] + ([a.year] if a.year else [])).fetchone(); print(r[3] if r else "(no layout stored)")
    elif a.cmd == "company": _show(query.by_ein(con, a.ein), a)
    elif a.cmd == "search": _show(query.search_sponsor(con, a.name, a.state, a.city, a.limit), a)
    elif a.cmd == "plans": _show(query.plans(con, a.state, a.city, a.min_participants, a.max_participants, a.year, a.welfare, a.limit), a)
    elif a.cmd == "broker": _show(query.by_broker(con, a.name, a.year, a.state, a.min_participants, a.limit), a)
    elif a.cmd == "carrier": _show(query.by_carrier(con, a.name, a.year, a.state, a.limit), a)
    elif a.cmd == "brokers":
        tl = brokers.timeline(con, a.ein, a.pn); _show(tl, a); print("\nChanges:"); _show(brokers.changes(tl), argparse.Namespace(out=None))
    elif a.cmd == "changes": _show(query.broker_changes_market(con, a.year, a.state, a.min_participants, a.from_broker, a.to_broker, a.limit), a)
    elif a.cmd == "report":
        from . import report
        ef = efast.search(ein=a.ein) if a.efast or a.pdfs else None
        out = report.build(con, a.ein, Path(a.out_dir) / f"report_{a.ein}", efast_df=ef)
        if a.pdfs and ef is not None: efast.download_pdfs(ef, out / "filings")
        print(f"report written to {out}")

if __name__ == "__main__":
    main()
