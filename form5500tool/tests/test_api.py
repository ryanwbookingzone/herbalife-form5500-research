import os
import pytest
from tests.conftest import DB

def test_api(con):
    pytest.importorskip("fastapi")
    os.environ["FORM5500_DB"] = DB
    from fastapi.testclient import TestClient
    from form5500.api import app
    c = TestClient(app)
    assert c.get("/health").json()["ok"]
    r = c.get("/company/953954565/brokers").json()
    assert any(x["group"].startswith("PCF") for x in r["timeline"])
    assert c.get("/search/broker", params={"broker": "HUB INTERNATIONAL", "year": 2024, "state": "CA", "limit": 5}).status_code == 200
