"""Broker-name normalization, broker-of-record timelines and change detection."""
import re
from pathlib import Path
import pandas as pd
from . import config

_SUFFIX = r"\b(INC|INCORPORATED|LLC|L L C|LTD|CORP|CORPORATION|CO|COMPANY|LP|LLP|PLLC|PC|THE|OF|AND|INSURANCE|INS|SERVICES|SERVICE|SVCS|AGENCY|BROKERAGE|ASSOCIATES|ASSOC|GROUP|BENEFITS|BENEFIT|INSURANCES)\b"

def _aliases():
    al = list(config.BROKER_ALIASES)
    p = config.HOME / "broker_aliases.txt"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1); al.insert(0, (k.strip().upper(), v.strip()))
    return al

ALIASES = _aliases()

def clean(name):
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    s = re.sub(r"[^A-Z0-9& ]", " ", str(name).upper().replace("&", " & "))
    return re.sub(r"\s+", " ", s).strip()

def group(name):
    """Canonical broker group: alias match (word-boundary) else name stripped of legal/industry suffixes."""
    s = clean(name)
    if not s:
        return "(blank)"
    for pat, g in ALIASES:
        if re.search(r"\b" + re.escape(pat) + r"\b", s):
            return g
    core = re.sub(r"\s+", " ", re.sub(_SUFFIX, " ", s.replace("&", " "))).strip()
    return core or s

def timeline(con, ein, pn=None):
    """Per plan year x broker group: contracts, commissions, fees, Sch C compensation (if the provider looks like a broker)."""
    q = "select DATASET_YEAR as year, pn, broker, broker_city, carrier, commission, fees from sch_a_brokers where ein=?"
    args = [str(ein)]
    if pn:
        q += " and pn=?"; args.append(pn)
    a = con.execute(q, args).df()
    a["group"] = a.broker.map(group)
    ta = a.groupby(["year", "pn", "group"]).agg(contracts=("carrier", "size"), commission=("commission", "sum"),
            fees=("fees", "sum"), names=("broker", lambda s: "; ".join(sorted({str(x) for x in s if pd.notna(x)}))),
            cities=("broker_city", lambda s: "; ".join(sorted({str(x) for x in s if pd.notna(x)})))).reset_index()
    ta["source"] = "Sch A Part I"
    try:
        c = con.execute("""select DATASET_YEAR as year, pn, provider, relation, direct_comp, indirect_comp from sch_c_providers
                           where ein=? and (upper(relation) like '%BROKER%' or upper(relation) like '%AGENT%' or upper(relation) like '%CONSULT%')""",
                        [str(ein)]).df()
    except Exception:
        c = pd.DataFrame()
    if len(c):
        c["group"] = c.provider.map(group)
        tc = c.groupby(["year", "pn", "group"]).agg(sch_c_direct=("direct_comp", "sum"), sch_c_indirect=("indirect_comp", "sum"),
                names=("provider", lambda s: "; ".join(sorted(set(map(str, s))))), relation=("relation", "first")).reset_index()
        tc["source"] = "Sch C"
        ta = pd.concat([ta, tc], ignore_index=True)
    return ta.sort_values(["pn", "year", "source", "group"]).reset_index(drop=True)

def primary_by_year(tl):
    """Primary broker per (pn, year): Sch A group with the most contracts, tie-break by commission+fees."""
    a = tl[tl.source == "Sch A Part I"].copy()
    if a.empty:
        return pd.DataFrame(columns=["pn", "year", "primary", "all_groups"])
    a["comp"] = a.commission.fillna(0) + a.fees.fillna(0)
    a = a[a.group != "(blank)"]
    rows = []
    for (pn, y), g in a.groupby(["pn", "year"]):
        g = g.sort_values(["contracts", "comp"], ascending=False)
        rows.append({"pn": pn, "year": int(y), "primary": g.group.iloc[0], "all_groups": sorted(g.group)})
    return pd.DataFrame(rows)

def changes(tl):
    """Detect broker-of-record changes year over year (per plan)."""
    p = primary_by_year(tl)
    out = []
    for pn, g in p.sort_values("year").groupby("pn"):
        prev = None
        for _, r in g.iterrows():
            if prev is not None:
                added = sorted(set(r.all_groups) - set(prev.all_groups)); dropped = sorted(set(prev.all_groups) - set(r.all_groups))
                if r.primary != prev.primary or added or dropped:
                    out.append({"pn": pn, "from_year": int(prev.year), "to_year": int(r.year), "primary_before": prev.primary,
                                "primary_after": r.primary, "primary_changed": r.primary != prev.primary,
                                "groups_added": "; ".join(added), "groups_dropped": "; ".join(dropped)})
            prev = r
    return pd.DataFrame(out)

def first_appearance(tl, group_name):
    g = tl[tl.group == group_name]
    return None if g.empty else int(g.year.min())
