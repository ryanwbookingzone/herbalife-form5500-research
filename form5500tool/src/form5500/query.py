"""Query helpers over the DuckDB views."""
import pandas as pd
from rapidfuzz import fuzz, process
from . import brokers

def by_ein(con, ein):
    return con.execute("select * from filings where ein=? order by pn, DATASET_YEAR", [str(ein).replace("-", "")]).df()

def search_sponsor(con, name, state=None, city=None, limit=25, min_score=80):
    """Fuzzy sponsor-name search: SQL prefilter on tokens, then rapidfuzz ranking."""
    toks = [t for t in brokers.clean(name).split() if len(t) > 2] or [brokers.clean(name)]
    where = " or ".join(["upper(sponsor) like ?"] * len(toks))
    args = [f"%{t}%" for t in toks]
    q = f"select ein, sponsor, city, state, max(DATASET_YEAR) last_year, max(participants_eoy) max_participants, count(*) filings from filings where ({where})"
    if state:
        q += " and state=?"; args.append(state.upper())
    if city:
        q += " and upper(city)=?"; args.append(city.upper())
    df = con.execute(q + " group by 1,2,3,4", args).df()
    if df.empty:
        return df
    df["score"] = [fuzz.token_set_ratio(brokers.clean(name), brokers.clean(s)) for s in df.sponsor]
    return df[df.score >= min_score].sort_values(["score", "max_participants"], ascending=False).head(limit)

def plans(con, state=None, city=None, min_participants=None, max_participants=None, year=None, welfare_only=False, limit=500):
    q, args = "select * from filings where 1=1", []
    for col, v in (("state", state), ("upper(city)", city.upper() if city else None), ("DATASET_YEAR", year)):
        if v is not None:
            q += f" and {col}=?"; args.append(v)
    if min_participants is not None:
        q += " and participants_eoy>=?"; args.append(min_participants)
    if max_participants is not None:
        q += " and participants_eoy<=?"; args.append(max_participants)
    if welfare_only:
        q += " and pn like '5%'"
    return con.execute(q + f" order by participants_eoy desc nulls last limit {int(limit)}", args).df()

def by_broker(con, broker, year=None, state=None, min_participants=None, limit=2000):
    """All plans where a broker (substring on raw name, or alias group) appears on Schedule A Part I."""
    b = brokers.clean(broker)
    q = """select b.DATASET_YEAR as year, b.ein, b.pn, b.sponsor, b.state, any_value(f.participants_eoy) participants,
           list(distinct b.broker) broker_names, count(*) contracts, sum(b.commission) commission, sum(b.fees) fees,
           sum(b.premium) premium_on_contracts from sch_a_brokers b join filings f using (ACK_ID)
           where trim(regexp_replace(replace(upper(b.broker), '&', ' & '), '[^A-Z0-9&]+', ' ', 'g')) like ?"""
    args = [f"%{b}%"]
    for col, v in (("b.DATASET_YEAR", year), ("b.state", state.upper() if state else None)):
        if v is not None:
            q += f" and {col}=?"; args.append(v)
    q += " group by 1,2,3,4,5"
    if min_participants:
        q += " having any_value(f.participants_eoy)>=?"; args.append(min_participants)
    return con.execute(q + f" order by year desc, participants desc nulls last limit {int(limit)}", args).df()

def by_carrier(con, carrier, year=None, state=None, limit=2000):
    q = """select DATASET_YEAR as year, ein, pn, sponsor, state, carrier, contract, covered, premium, benefits from sch_a
           where upper(carrier) like ?"""
    args = [f"%{carrier.upper()}%"]
    for col, v in (("DATASET_YEAR", year), ("state", state.upper() if state else None)):
        if v is not None:
            q += f" and {col}=?"; args.append(v)
    return con.execute(q + f" order by year desc, premium desc nulls last limit {int(limit)}", args).df()

def broker_changes_market(con, year, state=None, min_participants=None, from_broker=None, to_broker=None, limit=5000):
    """Prospect mode: plans whose broker group set/primary changed between year-1 and year."""
    q = """select b.DATASET_YEAR as year, b.ein, b.pn, any_value(b.sponsor) sponsor, any_value(b.state) state,
           any_value(f.participants_eoy) participants, b.broker, count(*) n, sum(coalesce(b.commission,0)+coalesce(b.fees,0)) comp
           from sch_a_brokers b join filings f using (ACK_ID) where b.DATASET_YEAR in (?, ?)"""
    args = [year - 1, year]
    if state:
        q += " and b.state=?"; args.append(state.upper())
    df = con.execute(q + " group by 1,2,3,7", args).df()
    if min_participants:
        keep = df[(df.year == year) & (df.participants >= min_participants)][["ein", "pn"]].drop_duplicates()
        df = df.merge(keep, on=["ein", "pn"])
    df["group"] = df.broker.map(brokers.group)
    df = df[df.group != "(blank)"]
    out = []
    for (ein, pn), g in df.groupby(["ein", "pn"]):
        a, b = g[g.year == year - 1], g[g.year == year]
        if a.empty or b.empty:
            continue
        def prim(x):
            x = x.groupby("group").agg(n=("n", "sum"), comp=("comp", "sum")).sort_values(["n", "comp"], ascending=False)
            return x.index[0], set(x.index)
        pa, sa = prim(a); pb, sb = prim(b)
        if pa != pb:
            out.append({"ein": ein, "pn": pn, "sponsor": b.sponsor.iloc[0], "state": b.state.iloc[0],
                        "participants": b.participants.iloc[0], "primary_before": pa, "primary_after": pb,
                        "added": "; ".join(sorted(sb - sa)), "dropped": "; ".join(sorted(sa - sb))})
    r = pd.DataFrame(out)
    if r.empty:
        return r
    if from_broker:
        r = r[r.primary_before.str.contains(from_broker, case=False)]
    if to_broker:
        r = r[r.primary_after.str.contains(to_broker, case=False)]
    return r.sort_values("participants", ascending=False).head(limit)

def signers(con, ein):
    return con.execute("""select pn, DATASET_YEAR as year, admin_signer, admin_signed_date, sponsor_signer, ACK_ID from filings
                          where ein=? order by pn, year""", [str(ein)]).df()

def schedule_a(con, ein, year=None):
    """Schedule A insurance contracts: carriers, policy type, premiums, commissions/fees by broker per year."""
    ein = str(ein).replace("-", "")
    q = """select a.DATASET_YEAR, a.pn, a.carrier, a.carrier_ein, a.naic, a.contract, a.covered,
           a.premium, a.comm_total, a.fees_total, a.benefits as policy_type,
           a.policy_from, a.policy_to,
           coalesce(group_concat(distinct b.broker), '') as brokers,
           sum(b.commission) as broker_commissions, sum(b.fees) as broker_fees
           from sch_a a left join sch_a_brokers b on a.ACK_ID=b.ACK_ID and a.FORM_ID=b.FORM_ID
           where a.ein=?"""
    args = [ein]
    if year:
        q += " and a.DATASET_YEAR=?"
        args.append(year)
    q += " group by 1,2,3,4,5,6,7,8,9,10,11,12,13 order by a.DATASET_YEAR, a.pn, a.carrier"
    return con.execute(q, args).df()

def combined_timeline(con, ein, pn=None):
    """Combined year-by-year broker + signer timeline."""
    ein = str(ein).replace("-", "")
    
    # Get signer info per year
    sig = signers(con, ein)
    if pn:
        sig = sig[sig.pn == pn]
    
    # Get broker timeline
    tl = brokers.timeline(con, ein, pn)
    
    # Pivot broker timeline to get primary broker per year
    prim = brokers.primary_by_year(tl)
    
    # Merge with signers
    if sig.empty:
        return prim
    
    merged = sig.merge(prim, on=["pn", "year"], how="outer").sort_values(["pn", "year"])
    
    # Select and reorder columns
    cols = ["year", "pn", "admin_signer", "sponsor_signer", "primary"]
    if "all_groups" in merged.columns:
        cols.append("all_groups")
    cols = [c for c in cols if c in merged.columns]
    return merged[cols].rename(columns={"primary": "primary_broker"})
