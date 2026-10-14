# form5500 — DOL Form 5500 research toolkit

Local, reproducible Form 5500 intelligence for benefits-broker prospecting and plan research:

* **Bulk data → DuckDB.** Incremental download of every DOL EBSA FOIA "Latest" dataset (Form 5500, 5500-SF, Schedules A, A Part I, C and all C parts, D, G, H, I, R, SB, MB, …). Loading is layout-tolerant: every column is stored as VARCHAR, years are unioned by column name, new columns are added automatically, and the layout `.txt` files shipped in the zips are kept in `_layouts`. Mixed latin-1/cp1252 bytes are handled.
* **Query** by EIN, fuzzy sponsor name, state/city, size, broker, or carrier.
* **Broker-of-record timelines** (Schedule A Part I plus broker/consultant rows on Schedule C), alias-based broker grouping, year-over-year **change detection**, and **prospect lists** (all plans where broker X appears; plans whose primary broker changed; filters for state and size).
* **Company report**: PDF + Excel + CSVs + charts. Covers plans, filing details, funding codes, signer timeline, broker timeline and changes, carriers and premiums, Schedule C providers, Schedule H financials, a glossary, and caveats.
* **EFAST2 live search** (the backend used by the public 5500Search UI) and **filing PDF download**. This includes the newest filings that are not yet in the bulk data.
* **Watch mode** for a weekly cron: finds new filings for a watchlist, downloads their PDFs, and writes a JSON diff (exit code 10 when something is new).
* **Optional FastAPI REST API.**

## Install
```bash
pip install -e ".[api,test]"          # Python >= 3.10; pdftotext (poppler) is optional, used for signer extraction
```
Default storage is under `~/.form5500/` (`raw/`, `form5500.duckdb`, `filings/`). Override it with `--db`, `--raw-dir`, or the env vars `FORM5500_DB`, `FORM5500_RAW`, `FORM5500_HOME`.

## Quick start
```bash
form5500 update --years 2009-2025                 # download (incremental, HEAD-checked) + load core datasets
form5500 update --years 2024 --datasets all       # every DOL dataset for one year
form5500 status

form5500 search "Herbalife International" --state CA
form5500 company 953954565
form5500 brokers 953954565                        # broker timeline + detected changes
form5500 broker "PETER C FOY" --year 2024 --out foy_book.xlsx          # a competitor's book
form5500 broker "HUB INTERNATIONAL" --state CA --min-participants 500
form5500 carrier "EVEREST REINSURANCE" --year 2024
form5500 changes --year 2024 --state CA --min-participants 1000 --out ca_movers.csv
form5500 plans --state CA --city TORRANCE --min-participants 1000 --welfare
form5500 report 953954565 --efast --pdfs --out-dir reports/
form5500 efast --ein 521714774 --download filings/edf      # includes PY2025 PDFs
form5500 efast --sponsor "EDF Renewables"
form5500 layout F_SCH_A --year 2024
form5500 serve --port 8787                       # REST: /company/{ein}, /company/{ein}/brokers, /search/broker, /prospects/broker_changes, /efast/search …
```

### Weekly watch (cron)
`watchlist.json`:
```json
{"eins": ["953954565", {"ein": "521714774", "label": "EDF power solutions"}]}
```
```cron
0 7 * * MON  cd ~/f5500 && form5500 watch watchlist.json --json-out new_filings.json || true
0 8 1 * *    cd ~/f5500 && form5500 update --years 2025-2026      # monthly bulk refresh (DOL updates the datasets monthly)
```
The first run only records a baseline. Later runs report filings that are new since then.

## Data model (DuckDB)
Raw tables (one per DOL dataset, all VARCHAR, plus `DATASET_YEAR`): `F_5500`, `F_5500_SF`, `F_SCH_A`, `F_SCH_A_PART1`, `F_SCH_C_PART1_ITEM2`, … Views:

| view | contents |
|---|---|
| `filings` | 5500 + 5500-SF normalized: ack_id, year, form, ein, pn, sponsor, plan, city/state, participants, plan codes, funding/benefit arrangement flags, signers, received date |
| `sch_a` | Schedule A contracts: carrier, EIN/NAIC, contract, covered persons, premium (charges paid, else experience-rated earned premium), commission/fee totals, benefit flags |
| `sch_a_brokers` | Schedule A Part I brokers joined to contract and sponsor: commission, fees, fee text, address |
| `sch_c_providers` | Schedule C Part I item 2 providers: relation, direct/indirect compensation |
| `sch_h` | Schedule H joined to sponsor |

Join key: `ACK_ID` (+ `FORM_ID` for Schedule A ↔ Part I). Broker grouping lives in `form5500.config.BROKER_ALIASES`. Add your own entries as `PATTERN=Group` lines in `~/.form5500/broker_aliases.txt`.

## Verification (tests)
`FORM5500_DB=/path/to/form5500.duckdb pytest -q` (add `--no-network` to skip the EFAST2 tests). The tests check results that were first verified by hand from the DOL bulk data:
* Herbalife (EIN 953954565): plans 001 and 501. PCF/Peter C. Foy first appears in **2011** (predecessor: TBG Danco) and is the primary welfare broker 2013–2024. PY2024 Schedule A premium/charges total **$10,515,552**. Foy's Schedule C indirect compensation in 2024 was **$330,363**. The plan administrator signer for 2016–2024 is Himaya Veazie.
* EDF Renewables / EDF power solutions (EIN 521714774, PN 501): **HUB International** is the primary broker every year from 2012; PCF does not appear.
* EFAST2: Herbalife has ≥35 filings including PY2025, which is not yet in the bulk data. Watch mode detects new filings.

## Caveats
Filings are self-reported and the DOL does not audit them. The newest dataset year is partial. "Latest" keeps only the most recent filing per plan year. Schedule A does not show self-funded claims or ASO fees, and employer-paid consulting fees are not reported anywhere. Broker grouping is heuristic. The EFAST2 search endpoint is the public UI's backend; it is undocumented and could change. DOL's bulk PDF image service needs a request to foiarequest@dol.gov.

## Prior art this borrows from
jdcalvin/form5500 (Go → Postgres loader), coreymichaud/benefits-market-intelligence (DuckDB medallion pipeline), aadibhantihike/Form5500-OpenSearch (broker-name normalization, FastAPI + SQLite), jeffrobot494/labor-scraper (EFAST2 PDF parsing), pipeworx-io/mcp-form5500 (EFAST2 search wrapper), IAR wiki notes (use the `www.askebsa` host).
