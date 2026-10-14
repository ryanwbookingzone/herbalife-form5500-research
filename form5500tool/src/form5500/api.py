"""Optional FastAPI REST API.  Run: form5500 serve --port 8787   (or uvicorn form5500.api:app)"""
import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from . import brokers, config, db, efast, query

app = FastAPI(title="form5500 research API", version="0.1.0")

def _con():
    return db.connect(os.environ.get("FORM5500_DB", str(config.DB_PATH)), read_only=True)

def _j(df):
    import json
    return [] if df is None or df.empty else json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))

@app.get("/health")
def health():
    con = _con(); return {"ok": True, "loads": [list(map(str, r)) for r in db.status(con)]}

@app.get("/company/{ein}")
def company(ein: str):
    con = _con(); f = query.by_ein(con, ein)
    if f.empty: raise HTTPException(404, "EIN not found in local DB")
    return {"filings": _j(f), "signers": _j(query.signers(con, ein))}

@app.get("/company/{ein}/brokers")
def company_brokers(ein: str):
    con = _con(); tl = brokers.timeline(con, ein)
    return {"timeline": _j(tl), "changes": _j(brokers.changes(tl))}

@app.get("/company/{ein}/schedule_a")
def company_sch_a(ein: str):
    return _j(_con().execute("select * from sch_a where ein=? order by DATASET_YEAR", [ein]).df())

@app.get("/search/sponsor")
def search_sponsor(name: str, state: str | None = None, city: str | None = None, limit: int = 25):
    return _j(query.search_sponsor(_con(), name, state, city, limit))

@app.get("/search/broker")
def search_broker(broker: str, year: int | None = None, state: str | None = None, min_participants: int | None = None, limit: int = 500):
    return _j(query.by_broker(_con(), broker, year, state, min_participants, limit))

@app.get("/search/carrier")
def search_carrier(carrier: str, year: int | None = None, state: str | None = None, limit: int = 500):
    return _j(query.by_carrier(_con(), carrier, year, state, limit))

@app.get("/prospects/broker_changes")
def prospects(year: int, state: str | None = None, min_participants: int | None = None,
              from_broker: str | None = None, to_broker: str | None = None, limit: int = 500):
    return _j(query.broker_changes_market(_con(), year, state, min_participants, from_broker, to_broker, limit))

@app.get("/efast/search")
def efast_search(ein: str | None = None, sponsor: str | None = None, ack_id: str | None = None):
    return _j(efast.search(ein=ein, sponsor=sponsor, ack_id=ack_id))
