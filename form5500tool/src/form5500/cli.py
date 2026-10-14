"""form5500 command-line interface."""
import argparse, json, re, sys
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

def _redact_address(df, cols=None):
    """Redact street addresses from broker/agent columns in exports (preserve city/state)."""
    addr_cols = cols or [c for c in df.columns if any(x in c.lower() for x in ("address", "addr", "street"))]
    for c in addr_cols:
        if c in df.columns:
            df = df.drop(columns=[c])
    return df

def _show(df, args, redact=False):
    if redact and getattr(args, "redact_addresses", True):
        df = _redact_address(df.copy())
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
    
    # Data ingestion commands
    p = sp.add_parser("download", help="incremental download of DOL FOIA zips")
    p.add_argument("--years", required=True); p.add_argument("--datasets", default="core", help="core|all|comma list")
    p.add_argument("--force", action="store_true"); p.add_argument("--no-check-remote", action="store_true")
    p = sp.add_parser("load", help="load downloaded zips into DuckDB (incremental)")
    p.add_argument("--years", required=True); p.add_argument("--datasets", default="core"); p.add_argument("--force", action="store_true")
    p = sp.add_parser("update", help="download + load"); p.add_argument("--years", required=True); p.add_argument("--datasets", default="core")
    p = sp.add_parser("ingest", help="download + load (alias for update)"); p.add_argument("--years", required=True); p.add_argument("--datasets", default="core")
    sp.add_parser("status", help="what is loaded")
    p = sp.add_parser("layout", help="show DOL layout text shipped in zips"); p.add_argument("dataset"); p.add_argument("--year", type=int)
    
    # Company/plan queries
    p = sp.add_parser("company", help="filings for an EIN or company name"); p.add_argument("identifier", help="EIN (with or without dash) or company name")
    p.add_argument("--out")
    p = sp.add_parser("search", help="fuzzy sponsor name search"); p.add_argument("name"); p.add_argument("--state"); p.add_argument("--city")
    p.add_argument("--limit", type=int, default=25); p.add_argument("--out")
    p = sp.add_parser("plans", help="filter plans by geography/size"); p.add_argument("--state"); p.add_argument("--city"); p.add_argument("--year", type=int)
    p.add_argument("--min-participants", type=int); p.add_argument("--max-participants", type=int); p.add_argument("--welfare", action="store_true")
    p.add_argument("--limit", type=int, default=500); p.add_argument("--out")
    
    # Schedule A (insurance contracts)
    p = sp.add_parser("schedule-a", help="Schedule A insurance contracts for an EIN: carriers, premiums, commissions/fees by year")
    p.add_argument("ein"); p.add_argument("--year", type=int); p.add_argument("--out"); p.add_argument("--no-redact", action="store_true", help="include broker addresses")
    
    # Broker commands
    p = sp.add_parser("broker", help="plans where a broker appears (prospect list / book)"); p.add_argument("name"); p.add_argument("--year", type=int)
    p.add_argument("--state"); p.add_argument("--min-participants", type=int); p.add_argument("--limit", type=int, default=2000); p.add_argument("--out")
    p.add_argument("--no-redact", action="store_true", help="include broker addresses")
    p = sp.add_parser("book", help="all clients of a broker in a year with premiums/commissions (alias for broker)")
    p.add_argument("name"); p.add_argument("--year", type=int); p.add_argument("--state"); p.add_argument("--min-participants", type=int)
    p.add_argument("--limit", type=int, default=2000); p.add_argument("--out"); p.add_argument("--no-redact", action="store_true")
    p = sp.add_parser("brokers", help="broker-of-record timeline + changes for an EIN"); p.add_argument("ein"); p.add_argument("--pn"); p.add_argument("--out")
    p.add_argument("--no-redact", action="store_true", help="include broker addresses")
    p = sp.add_parser("carrier", help="plans with a carrier"); p.add_argument("name"); p.add_argument("--year", type=int); p.add_argument("--state")
    p.add_argument("--limit", type=int, default=2000); p.add_argument("--out")
    
    # Timeline and changes
    p = sp.add_parser("timeline", help="year-by-year broker + signer timeline for an EIN"); p.add_argument("ein"); p.add_argument("--pn"); p.add_argument("--out")
    p.add_argument("--no-redact", action="store_true", help="include broker addresses")
    p = sp.add_parser("changes", help="print broker changes table (no duplication)"); p.add_argument("ein", nargs="?", help="EIN (if omitted, use --year for market-wide)")
    p.add_argument("--year", type=int); p.add_argument("--state"); p.add_argument("--min-participants", type=int)
    p.add_argument("--from-broker"); p.add_argument("--to-broker"); p.add_argument("--limit", type=int, default=5000); p.add_argument("--out")
    p = sp.add_parser("movers", help="plans whose broker changed year over year"); p.add_argument("--year", type=int, required=True)
    p.add_argument("--state"); p.add_argument("--min-participants", type=int); p.add_argument("--from-broker"); p.add_argument("--to-broker")
    p.add_argument("--limit", type=int, default=5000); p.add_argument("--out")
    
    # Reports and export
    p = sp.add_parser("report", help="full company report (PDF+Excel+CSV)"); p.add_argument("ein"); p.add_argument("--out-dir", default=".")
    p.add_argument("--efast", action="store_true", help="include EFAST2 live index"); p.add_argument("--pdfs", action="store_true", help="also download filing PDFs")
    p = sp.add_parser("export", help="export query results to CSV or Excel"); p.add_argument("--csv", metavar="FILE", help="output CSV file")
    p.add_argument("--xlsx", metavar="FILE", help="output Excel file"); p.add_argument("--query", help="SQL query or table name")
    p.add_argument("--no-redact", action="store_true", help="include addresses in export")
    
    # EFAST2 live
    p = sp.add_parser("efast", help="EFAST2 live search"); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ein"); g.add_argument("--sponsor"); g.add_argument("--ack"); g.add_argument("--query")
    p.add_argument("--download", metavar="DIR"); p.add_argument("--out")
    
    # Watch mode
    p = sp.add_parser("watch", help="diff new EFAST2 filings for a watchlist JSON"); p.add_argument("watchlist"); p.add_argument("--state")
    p.add_argument("--no-download", action="store_true"); p.add_argument("--out-dir"); p.add_argument("--json-out")
    
    # API server
    p = sp.add_parser("serve", help="run REST API"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8787)
    a = ap.parse_args(argv)

    ds = lambda s: config.CORE if s == "core" else config.DATASETS if s == "all" else s.split(",")
    
    # Handle ingest as alias for update
    if a.cmd == "ingest":
        a.cmd = "update"
    
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
    
    # Set redact flag (default True unless --no-redact)
    a.redact_addresses = not getattr(a, "no_redact", False)
    
    if a.cmd == "status":
        for n, ys, rows in db.status(con): print(f"{n:28} {rows:>12,}  years {ys}")
    elif a.cmd == "layout":
        q = "select dataset, year, file, text from _layouts where dataset=?" + (" and year=?" if a.year else "") + " order by year desc limit 1"
        r = con.execute(q, [a.dataset] + ([a.year] if a.year else [])).fetchone(); print(r[3] if r else "(no layout stored)")
    elif a.cmd == "company":
        # Support both EIN and company name
        ident = a.identifier.replace("-", "")
        if ident.isdigit() and len(ident) == 9:
            _show(query.by_ein(con, ident), a)
        else:
            _show(query.search_sponsor(con, a.identifier, limit=50), a)
    elif a.cmd == "search": _show(query.search_sponsor(con, a.name, a.state, a.city, a.limit), a)
    elif a.cmd == "plans": _show(query.plans(con, a.state, a.city, a.min_participants, a.max_participants, a.year, a.welfare, a.limit), a)
    elif a.cmd == "schedule-a":
        df = query.schedule_a(con, a.ein, a.year)
        _show(df, a, redact=True)
        # Print yearly totals
        if not df.empty:
            print("\nYearly totals:")
            totals = df.groupby("DATASET_YEAR").agg({
                "premium": "sum", "comm_total": "sum", "fees_total": "sum"
            }).reset_index()
            totals.columns = ["year", "total_premium", "total_commissions", "total_fees"]
            _show(totals, argparse.Namespace(out=None, redact_addresses=False))
    elif a.cmd in ("broker", "book"):
        _show(query.by_broker(con, a.name, a.year, a.state, a.min_participants, a.limit), a, redact=True)
    elif a.cmd == "carrier": _show(query.by_carrier(con, a.name, a.year, a.state, a.limit), a)
    elif a.cmd == "brokers":
        tl = brokers.timeline(con, a.ein, a.pn)
        _show(tl, a, redact=True)
        print("\nChanges:")
        _show(brokers.changes(tl), argparse.Namespace(out=None, redact_addresses=False))
    elif a.cmd == "timeline":
        df = query.combined_timeline(con, a.ein, a.pn)
        _show(df, a, redact=True)
    elif a.cmd == "changes":
        if a.ein:
            # Single company changes
            tl = brokers.timeline(con, a.ein)
            _show(brokers.changes(tl), a)
        elif a.year:
            # Market-wide changes
            _show(query.broker_changes_market(con, a.year, a.state, a.min_participants, a.from_broker, a.to_broker, a.limit), a)
        else:
            print("Error: provide either an EIN or --year for market-wide changes")
            sys.exit(1)
    elif a.cmd == "movers":
        _show(query.broker_changes_market(con, a.year, a.state, a.min_participants, a.from_broker, a.to_broker, a.limit), a)
    elif a.cmd == "export":
        if a.query:
            if a.query.upper().startswith("SELECT"):
                df = con.execute(a.query).df()
            else:
                df = con.execute(f"select * from {a.query}").df()
        else:
            print("Error: --query required"); sys.exit(1)
        if not getattr(a, "no_redact", False):
            df = _redact_address(df)
        if a.csv:
            df.to_csv(a.csv, index=False); print(f"wrote {a.csv} ({len(df)} rows)")
        elif a.xlsx:
            df.to_excel(a.xlsx, index=False); print(f"wrote {a.xlsx} ({len(df)} rows)")
        else:
            _show(df, a)
    elif a.cmd == "report":
        from . import report
        ef = efast.search(ein=a.ein) if a.efast or a.pdfs else None
        out = report.build(con, a.ein, Path(a.out_dir) / f"report_{a.ein}", efast_df=ef)
        if a.pdfs and ef is not None: efast.download_pdfs(ef, out / "filings")
        print(f"report written to {out}")

if __name__ == "__main__":
    main()
