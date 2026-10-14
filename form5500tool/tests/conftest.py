import os, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from form5500 import db

DB = os.environ.get("FORM5500_DB", str(Path.home() / ".form5500" / "form5500.duckdb"))

@pytest.fixture(scope="session")
def con():
    if not Path(DB).exists():
        pytest.skip(f"no database at {DB}; run `form5500 update --years 2009-2025` first")
    return db.connect(DB, read_only=True)

def pytest_addoption(parser):
    parser.addoption("--no-network", action="store_true", help="skip EFAST2 live tests")

@pytest.fixture
def network(request):
    if request.config.getoption("--no-network"):
        pytest.skip("network tests disabled")
