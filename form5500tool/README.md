# form5500 — DOL Form 5500 Research Toolkit

A lean Python CLI for analyzing US DOL EBSA Form 5500 data: bulk data ingestion, broker timelines, prospect lists, change detection, and EFAST2 live search.

## Features

* **Bulk data → DuckDB.** Incremental download of DOL EBSA FOIA "Latest" datasets (Form 5500, 5500-SF, Schedules A, A Part I, C and all C parts, D, G, H, I, R, SB, MB, …). Loading is layout-tolerant: every column is stored as VARCHAR, years are unioned by column name, new columns are added automatically, and the layout `.txt` files shipped in the zips are kept in `_layouts`.
* **Query** by EIN, fuzzy sponsor name, state/city, size, broker, or carrier.
* **Broker-of-record timelines** (Schedule A Part I plus broker/consultant rows on Schedule C), alias-based broker grouping, year-over-year **change detection**, and **prospect lists** (all plans where broker X appears; plans whose primary broker changed; filters for state and size).
* **Company reports**: PDF + Excel + CSVs + charts covering plans, filing details, funding codes, signer timeline, broker timeline and changes, carriers and premiums, Schedule C providers, Schedule H financials, a glossary, and caveats.
* **EFAST2 live search** (the backend used by the public 5500Search UI) and **filing PDF download**. This includes the newest filings that are not yet in the bulk data.
* **Watch mode** for a weekly cron: finds new filings for a watchlist, downloads their PDFs, and writes a JSON diff (exit code 10 when something is new).
* **Address redaction**: Broker/agent street addresses are redacted by default in exports to protect personal information.
* **Optional FastAPI REST API.**

## Install

```bash
pip install -e ".[api,test]"          # Python >= 3.10; pdftotext (poppler) is optional
```

Default storage is under `~/.form5500/` (`raw/`, `form5500.duckdb`, `filings/`). Override with `--db`, `--raw-dir`, or the env vars `FORM5500_DB`, `FORM5500_RAW`, `FORM5500_HOME`.

## Quick Start

```bash
# Ingest data (download + load into DuckDB)
form5500 ingest --years 2024                      # one year (fast, recommended for testing)
form5500 ingest --years 2009-2025                 # all years (comprehensive)
form5500 ingest --years 2024 --datasets all       # every DOL dataset for one year
form5500 status                                   # show what's loaded

# Company lookup (by EIN or name)
form5500 company 95-3954565                       # Herbalife by EIN
form5500 company "Herbalife International"        # or by name
form5500 search "Herbalife International" --state CA

# Schedule A (insurance contracts, premiums, commissions by broker)
form5500 schedule-a 953954565                     # carriers, premiums, commissions/fees
form5500 schedule-a 953954565 --year 2024

# Broker commands
form5500 brokers 953954565                        # broker-of-record timeline + changes
form5500 timeline 953954565                       # year-by-year broker + signer combined
form5500 broker "PETER C FOY" --year 2024         # all clients of a broker (book)
form5500 book "HUB INTERNATIONAL" --state CA --min-participants 500

# Carrier lookup
form5500 carrier "EVEREST REINSURANCE" --year 2024

# Broker changes / market movers
form5500 changes 953954565                        # changes for one company
form5500 movers --year 2024 --state CA --min-participants 1000
form5500 movers --year 2024 --from-broker "Gallagher" --to-broker "Marsh"

# Geographic/size filtering
form5500 plans --state CA --city TORRANCE --min-participants 1000 --welfare

# Full company report (PDF + Excel + CSVs + charts)
form5500 report 953954565 --efast --pdfs --out-dir reports/

# EFAST2 live search (includes filings not yet in bulk data)
form5500 efast --ein 953954565                    # search by EIN
form5500 efast --sponsor "EDF Renewables"         # search by sponsor name
form5500 efast --ein 521714774 --download filings/edf   # download filing PDFs

# Export to CSV/Excel
form5500 export --query "select * from sch_a where ein='953954565'" --csv export.csv
form5500 export --query filings --xlsx all_filings.xlsx

# Show dataset layout from DOL zips
form5500 layout F_SCH_A --year 2024

# REST API
form5500 serve --port 8787   # /company/{ein}, /brokers/{ein}, /search/broker, /efast/search …
```

### Watch Mode (Weekly Cron)

`watchlist.json`:
```json
{"eins": ["953954565", {"ein": "521714774", "label": "EDF power solutions"}]}
```

```cron
0 7 * * MON  cd ~/f5500 && form5500 watch watchlist.json --json-out new_filings.json || true
0 8 1 * *    cd ~/f5500 && form5500 ingest --years 2025-2026   # monthly bulk refresh
```

The first run only records a baseline. Later runs report filings that are new since then (exit code 10 when new filings found).

## Commands Reference

| Command | Description |
|---------|-------------|
| `ingest --years` | Download DOL FOIA data + load into DuckDB (incremental, idempotent) |
| `update --years` | Same as ingest |
| `download --years` | Only download zips (no load) |
| `load --years` | Only load already-downloaded zips |
| `status` | Show what years/datasets are loaded |
| `company <EIN\|name>` | All plans per year: plan name/number, participants, assets, signer name/date, filing PDF link |
| `search <name>` | Fuzzy sponsor name search |
| `schedule-a <EIN>` | Schedule A: carriers, policy type, premiums, commissions/fees by broker per year, totals |
| `brokers <EIN>` | Broker-of-record timeline from Sch A Part I and Sch C service providers |
| `timeline <EIN>` | Year-by-year broker + signer combined |
| `broker <name>` / `book <name>` | All clients of a broker in a year with premiums/commissions |
| `carrier <name>` | Plans with a specific insurance carrier |
| `changes <EIN>` | Broker changes for one company |
| `movers --state --year` | Plans whose broker changed year over year (market-wide prospects) |
| `plans --state --city` | Filter plans by geography/size |
| `report <EIN>` | Full company report (PDF + Excel + CSVs + charts) |
| `export --csv/--xlsx` | Export query results to CSV or Excel |
| `efast --ein/--sponsor` | EFAST2 live search (includes newest filings) |
| `watch <watchlist.json>` | Detect new filings vs last run |
| `serve` | Run REST API |
| `layout <dataset>` | Show DOL layout text shipped in zips |

### Address Redaction

By default, broker/agent street addresses are **redacted** from exports to protect personal information. Use `--no-redact` to include addresses:

```bash
form5500 broker "HUB" --year 2024 --out hub_book.csv              # addresses redacted
form5500 broker "HUB" --year 2024 --out hub_book.csv --no-redact  # addresses included
```

## Data Model (DuckDB)

Raw tables (one per DOL dataset, all VARCHAR, plus `DATASET_YEAR`): `F_5500`, `F_5500_SF`, `F_SCH_A`, `F_SCH_A_PART1`, `F_SCH_C_PART1_ITEM2`, …

| View | Contents |
|------|----------|
| `filings` | 5500 + 5500-SF normalized: ack_id, year, form, ein, pn, sponsor, plan, city/state, participants, plan codes, funding/benefit arrangement flags, signers, received date |
| `sch_a` | Schedule A contracts: carrier, EIN/NAIC, contract, covered persons, premium (charges paid, else experience-rated earned premium), commission/fee totals, benefit flags |
| `sch_a_brokers` | Schedule A Part I brokers joined to contract and sponsor: commission, fees, fee text, address |
| `sch_c_providers` | Schedule C Part I item 2 providers: relation, direct/indirect compensation |
| `sch_h` | Schedule H joined to sponsor |

**Join key:** `ACK_ID` (+ `FORM_ID` for Schedule A ↔ Part I).

**Broker grouping** lives in `form5500.config.BROKER_ALIASES`. Add your own entries as `PATTERN=Group` lines in `~/.form5500/broker_aliases.txt`.

## EFAST2 PDF URL Construction

Filing PDFs are stored on S3 at:
```
https://efast2-filings-public.s3.amazonaws.com/prd{pdfpath}
```

The `pdfpath` is returned by EFAST2 search results. For example:
```
/2025/07/31/20250731131041NAL0002599987001.pdf
```

The CLI constructs these URLs automatically when downloading PDFs.

## Data Caveats

* **Welfare plans** file only if they have 100+ participants OR a trust; smaller fully-insured plans are exempt.
* **Government and church plans** are exempt from ERISA filing requirements.
* **Schedule A** does not split employer vs employee premium contributions—only total charges/premium is reported.
* **Schedule C** covers only service providers paid >= $5,000 (direct or indirect compensation).
* **Self-funded plans** do not report claims data on Schedule A—only stop-loss insurance appears there. ASO fees appear on Schedule C.
* **"Latest" datasets** hold the most recent filing per plan year; the newest year is partial until DOL's monthly update.
* **Broker grouping** is heuristic—based on name normalization and an alias list. Names may merge or split imperfectly.
* **EFAST2 search** is the public UI's undocumented backend; it could change without notice.

## Verification (Tests)

```bash
FORM5500_DB=/path/to/form5500.duckdb pytest -q        # with network
FORM5500_DB=/path/to/form5500.duckdb pytest -q --no-network  # skip EFAST2 tests
```

Tests check results verified by hand:

* **Herbalife (EIN 953954565)**: Plans 001 and 501. PCF/Peter C. Foy first appears in 2011 (predecessor: TBG Danco) and is the primary welfare broker 2013–2024. PY2024 Schedule A premium/charges total **$10,515,552**. Foy's Schedule C indirect compensation in 2024 was **$330,363**. The plan administrator signer for 2016–2024 is Himaya Veazie.
* **EDF Renewables (EIN 521714774, PN 501)**: HUB International is the primary broker every year from 2012; PCF does not appear.
* **EFAST2**: Herbalife has 35+ filings including PY2025, which is not yet in bulk data. Watch mode detects new filings.

## How a Cloud Agent Should Use This

1. **Install**: `pip install -e .` in the form5500tool directory
2. **Ingest data** for years of interest: `form5500 ingest --years 2023-2024` (start lean; add more years as needed)
3. **Look up a company**: `form5500 company <EIN>` or `form5500 search "<company name>"`
4. **Get broker timeline**: `form5500 brokers <EIN>` shows Schedule A Part I + Schedule C broker data with change detection
5. **Get Schedule A details**: `form5500 schedule-a <EIN>` for insurance contracts, premiums, commissions
6. **Export data**: Use `--out file.csv` or `--out file.xlsx` on most commands
7. **For newest filings**: Use `form5500 efast --ein <EIN>` which queries the live EFAST2 index
8. **Generate reports**: `form5500 report <EIN> --efast --out-dir reports/` for comprehensive PDF+Excel

**Tips**:
* EINs can be with or without dash (95-3954565 or 953954565)
* Use `--no-redact` if you need broker street addresses
* The DuckDB file is at `~/.form5500/form5500.duckdb` by default
* For SQL queries: `form5500 export --query "SELECT * FROM sch_a WHERE ein='...'"`

## Prior Art

This borrows from: jdcalvin/form5500 (Go → Postgres loader), coreymichaud/benefits-market-intelligence (DuckDB medallion pipeline), aadibhantihike/Form5500-OpenSearch (broker-name normalization, FastAPI + SQLite), jeffrobot494/labor-scraper (EFAST2 PDF parsing), pipeworx-io/mcp-form5500 (EFAST2 search wrapper), IAR wiki notes (use the `www.askebsa` host).
