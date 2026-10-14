import json
from form5500 import efast, watch

def test_efast_herbalife_includes_py2025(network):
    df = efast.search(ein="953954565")
    assert len(df) >= 35
    assert "2025" in set(df.planyear)          # filed Oct 2026: not yet in bulk data

def test_efast_ack(network):
    df = efast.search(ack_id="20250725175259NAL0007760800001")
    assert list(df.pn) == ["501"]

def test_watch_detects_new(network, tmp_path):
    wl = tmp_path / "wl.json"; wl.write_text(json.dumps({"eins": ["953954565"]}))
    st = tmp_path / "wl.state.json"
    all_ids = list(efast.search(ein="953954565").ack_id)
    st.write_text(json.dumps({"953954565": all_ids[:-2]}))          # pretend the last 2 are new
    rep = watch.run(wl, st, download=False)
    assert len(rep["new"]) == 2
    rep2 = watch.run(wl, st, download=False)
    assert rep2["new"] == []
