"""Reproduce results verified by hand from DOL bulk data (see README 'Verification').
Note: Some tests require full historical data (2009-2024). They skip when only partial data is loaded."""
import pandas as pd
import pytest
from form5500 import brokers, query

HERBALIFE, EDF = "953954565", "521714774"
PCF = "PCF / Trucordia (Peter C. Foy)"

def _min_year(con):
    """Get the minimum year loaded in the database."""
    try:
        return con.execute("select min(DATASET_YEAR) from filings").fetchone()[0]
    except:
        return 2024

def test_herbalife_filings(con):
    f = query.by_ein(con, HERBALIFE)
    assert set(f.pn) == {"001", "501"}
    min_year = _min_year(con)
    if min_year <= 2009:
        assert f[f.pn == "501"].DATASET_YEAR.min() == 2009
    assert f.sponsor.str.contains("HERBALIFE", case=False).all()

def test_herbalife_foy_since_2011(con):
    min_year = _min_year(con)
    if min_year > 2011:
        pytest.skip(f"requires data back to 2011 (min loaded: {min_year})")
    tl = brokers.timeline(con, HERBALIFE)
    sa = tl[tl.source == "Sch A Part I"]
    assert brokers.first_appearance(sa, PCF) == 2011
    before = set(sa[sa.year < 2011].group)
    assert "TBG Danco" in before          # predecessor welfare broker
    prim = brokers.primary_by_year(tl)
    assert (prim[(prim.pn == "501") & (prim.year.between(2013, 2024))].primary == PCF).all()

def test_herbalife_2024_premium_and_sch_c(con):
    a = con.execute("select sum(premium) from sch_a where ein=? and pn='501' and DATASET_YEAR=2024", [HERBALIFE]).fetchone()[0]
    assert round(a) == 10_515_552
    c = con.execute("""select indirect_comp from sch_c_providers where ein=? and DATASET_YEAR=2024 and provider like '%FOY%'""", [HERBALIFE]).fetchone()[0]
    assert round(c) == 330_363

def test_herbalife_signers(con):
    s = query.signers(con, HERBALIFE)
    assert (s[(s.pn == "501") & (s.year.between(2016, 2024))].admin_signer.str.upper() == "HIMAYA VEAZIE").all()

def test_edf_hub_every_year(con):
    min_year = _min_year(con)
    if min_year > 2012:
        pytest.skip(f"requires data back to 2012 (min loaded: {min_year})")
    tl = brokers.timeline(con, EDF, pn="501")
    prim = brokers.primary_by_year(tl)
    yrs = prim[prim.pn == "501"]
    assert yrs.year.min() <= 2012
    assert (yrs.primary == "HUB International").all()
    assert PCF not in set(tl.group)

def test_prospect_by_broker(con):
    df = query.by_broker(con, "PETER C FOY", year=2024)
    assert HERBALIFE in set(df.ein)

def test_sponsor_fuzzy(con):
    df = query.search_sponsor(con, "Herbalife International of America", state="CA")
    assert HERBALIFE in set(df.ein)

def test_market_changes_runs(con):
    df = query.broker_changes_market(con, 2024, state="CA", min_participants=1000, limit=50)
    assert isinstance(df, pd.DataFrame)

def test_schedule_a(con):
    """Test Schedule A query for Herbalife 2024."""
    df = query.schedule_a(con, HERBALIFE, 2024)
    assert not df.empty
    # Check total premium matches expected value
    total = df.premium.sum()
    assert round(total) == 10_515_552

def test_combined_timeline(con):
    """Test combined broker + signer timeline."""
    df = query.combined_timeline(con, HERBALIFE)
    assert not df.empty
    assert "admin_signer" in df.columns or "primary_broker" in df.columns

def test_edf_hub_current_years(con):
    """Test that EDF has HUB as broker in available years (regardless of data extent)."""
    tl = brokers.timeline(con, EDF, pn="501")
    if tl.empty:
        pytest.skip("No EDF data loaded")
    prim = brokers.primary_by_year(tl)
    yrs = prim[prim.pn == "501"]
    if not yrs.empty:
        assert (yrs.primary == "HUB International").all()
    assert PCF not in set(tl.group)
