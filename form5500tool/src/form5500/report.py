"""Per-company report (PDF + Excel + CSVs + charts) from the DuckDB database, optionally enriched with EFAST2 live index."""
from pathlib import Path
import datetime as dt
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from . import brokers, query

GLOSSARY = [
    ["Form 5500 / 5500-SF", "Plan identity, sponsor, administrator/signers, participant counts, plan feature codes (8a pension / 8b welfare), funding (9a) and benefit (9b) arrangements, schedules attached. 5500-SF = small plans (<100 participants, generally)."],
    ["Schedule A", "Insurance contracts: carrier, EIN/NAIC, contract #, persons covered, policy dates, broker/agent commissions & fees (Part I), pension contract values (Part II), welfare premiums/charges (Part III)."],
    ["Schedule C", "Service providers paid >= $5,000: direct & indirect compensation, service codes; Part III terminated accountants/actuaries."],
    ["Schedule D", "Interests in DFEs (CCTs, pooled separate accounts, master trusts, 103-12 IEs)."],
    ["Schedule H / I", "Financial statements (large / small plans): assets, contributions (employer vs participant), benefits paid, expenses, accountant opinion."],
    ["Schedule G / R / SB / MB", "Non-exempt transactions & defaults / retirement plan info & 401(k) testing / single- & multi-employer DB actuarial."],
]

def cat(r):
    t = str(r.get("benefits") or "").upper()
    if "STOP" in t: return "Stop-loss"
    if "PERFORM" in t: return "Perf. guarantee / ASO"
    if "EAP" in t or "ASSISTANCE" in t: return "EAP"
    if "DENTAL" in t: return "Dental"
    if "VISION" in t: return "Vision"
    if any(k in t for k in ("HEALTH", "HMO", "PPO", "DRUG")): return "Medical/Rx"
    if any(k in t for k in ("LTD", "STD", "DISAB", "SDI")): return "Disability"
    if any(k in t for k in ("LIFE", "AD&D", "DEATH")): return "Life/AD&D"
    return "Other"

def _money(v):
    try:
        return "" if pd.isna(v) else f"{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)

def gather(con, ein):
    ein = str(ein).replace("-", "")
    d = {"filings": query.by_ein(con, ein)}
    d["signers"] = query.signers(con, ein)
    d["sch_a"] = con.execute("select * from sch_a where ein=? order by DATASET_YEAR, pn, carrier", [ein]).df()
    if not d["sch_a"].empty:
        d["sch_a"]["category"] = d["sch_a"].apply(cat, axis=1)
    d["brokers_raw"] = con.execute("select * from sch_a_brokers where ein=? order by DATASET_YEAR, pn, broker", [ein]).df()
    d["broker_timeline"] = brokers.timeline(con, ein)
    d["broker_changes"] = brokers.changes(d["broker_timeline"])
    try:
        d["sch_c"] = con.execute("select * from sch_c_providers where ein=? order by DATASET_YEAR, pn, provider", [ein]).df()
    except Exception:
        d["sch_c"] = pd.DataFrame()
    try:
        h = con.execute("select * from sch_h where ein=? order by pn, DATASET_YEAR", [ein]).df()
        d["sch_h"] = h[[c for c in h.columns if c in ("pn", "DATASET_YEAR", "ACCOUNTANT_FIRM_NAME", "ACCTNT_OPINION_TYPE_CD") or c.endswith("_AMT")]]
    except Exception:
        d["sch_h"] = pd.DataFrame()
    return d

def build(con, ein, out_dir, efast_df=None, title=None):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    d = gather(con, ein)
    if efast_df is not None:
        d["efast_index"] = efast_df
    f = d["filings"]
    if f.empty and (efast_df is None or efast_df.empty):
        raise SystemExit(f"No filings for EIN {ein} in the database (load more years?)")
    name = title or (f.sponsor.mode().iloc[0] if not f.empty else efast_df.plansponsor.iloc[0])
    # CSV + Excel
    with pd.ExcelWriter(out / f"form5500_{ein}.xlsx") as xw:
        for k, v in d.items():
            if isinstance(v, pd.DataFrame) and not v.empty:
                v2 = v.copy()
                for c in v2.columns:
                    if v2[c].dtype == object:
                        v2[c] = v2[c].map(lambda x: "; ".join(map(str, x)) if isinstance(x, (list, tuple)) else x)
                v2.to_csv(out / f"{k}.csv", index=False); v2.to_excel(xw, sheet_name=k[:31], index=False)
    charts = _charts(d, out)
    _pdf(d, name, ein, out / f"form5500_report_{ein}.pdf", charts)
    return out

def _charts(d, out):
    ch = {}
    f = d["filings"]
    if not f.empty:
        fig, ax = plt.subplots(figsize=(9, 3.6))
        for pn, g in f.groupby("pn"):
            ax.plot(g.DATASET_YEAR, g.participants_eoy, marker="o", label=f"PN {pn}")
        ax.set_title("Participants (EOY) by plan"); ax.legend(fontsize=7); ax.grid(alpha=.3); fig.tight_layout()
        ch["participants"] = out / "chart_participants.png"; fig.savefig(ch["participants"], dpi=120); plt.close(fig)
    a = d["sch_a"]
    if not a.empty and a.premium.notna().any():
        pv = a.pivot_table(index="DATASET_YEAR", columns="category", values="premium", aggfunc="sum").fillna(0)
        fig, ax = plt.subplots(figsize=(9, 4)); (pv / 1e6).plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
        ax.set_title("Schedule A premium/charges by category ($M)"); ax.legend(fontsize=6, ncol=3); fig.tight_layout()
        ch["premium"] = out / "chart_premium.png"; fig.savefig(ch["premium"], dpi=120); plt.close(fig)
    t = d["broker_timeline"]
    if not t.empty:
        t2 = t.copy(); t2["comp"] = t2[["commission", "fees"]].sum(axis=1, min_count=1).fillna(0)
        if "sch_c_indirect" in t2:
            t2["comp"] += t2[["sch_c_direct", "sch_c_indirect"]].sum(axis=1, min_count=1).fillna(0)
        pv = t2.pivot_table(index="year", columns="group", values="comp", aggfunc="sum").fillna(0)
        if pv.values.sum() > 0:
            fig, ax = plt.subplots(figsize=(9, 4)); (pv / 1e3).plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
            ax.set_title("Broker compensation by broker group ($K; Sch A comm+fees + Sch C broker/consultant comp)"); ax.legend(fontsize=6)
            fig.tight_layout(); ch["brokers"] = out / "chart_brokers.png"; fig.savefig(ch["brokers"], dpi=120); plt.close(fig)
    h = d["sch_h"]
    if not h.empty and "NET_ASSETS_EOY_AMT" in h:
        fig, ax = plt.subplots(figsize=(9, 3.6))
        for pn, g in h.groupby("pn"):
            ax.plot(g.DATASET_YEAR, pd.to_numeric(g.NET_ASSETS_EOY_AMT, errors="coerce") / 1e6, marker="o", label=f"PN {pn}")
        ax.set_title("Schedule H net assets EOY ($M)"); ax.legend(); ax.grid(alpha=.3); fig.tight_layout()
        ch["assets"] = out / "chart_assets.png"; fig.savefig(ch["assets"], dpi=120); plt.close(fig)
    return ch

def _pdf(d, name, ein, path, charts):
    s = getSampleStyleSheet(); sm = s["BodyText"].clone("sm", fontSize=6.5, leading=8); bd = s["BodyText"].clone("bd", fontSize=8.5, leading=11)
    P = lambda t: Paragraph(t, bd)
    def T(df, cols=None, widths=None, max_rows=400):
        if df is None or df.empty:
            return P("<i>No rows.</i>")
        df = df[cols] if cols else df
        rows = [list(df.columns)] + [[_money(x) if isinstance(x, float) else ("" if x is None else str(x)) for x in r] for r in df.head(max_rows).itertuples(index=False)]
        rows = [[Paragraph(str(c), sm) for c in r] for r in rows]
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde4ee")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
        return t
    el = [Paragraph(f"{name} (EIN {ein[:2]}-{ein[2:]}) - Form 5500 research report", s["Title"]),
          P(f"Generated {dt.date.today()} from DOL EBSA FOIA Form 5500 'Latest' datasets loaded into DuckDB"
            + (" plus the EFAST2 public search index" if "efast_index" in d else "") + ". All values as filed; nothing imputed.")]
    f = d["filings"]
    if not f.empty:
        pl = f.groupby("pn").agg(plan_name=("plan_name", "last"), first=("DATASET_YEAR", "min"), last=("DATASET_YEAR", "max"),
                                 participants_last=("participants_eoy", "last"), form=("form", "last")).reset_index()
        el += [Paragraph("1. Plans", s["Heading2"]), T(pl)]
        el += [Paragraph("2. Filings and plan details", s["Heading2"]),
               T(f, ["DATASET_YEAR", "pn", "form", "ACK_ID", "participants_boy", "participants_eoy", "pension_codes", "welfare_codes",
                     "fund_insurance", "fund_trust", "fund_gen_assets", "bnft_insurance", "bnft_trust", "bnft_gen_assets", "short_year", "final_filing", "date_received"]),
               P("Funding/benefit arrangement flags (9a/9b): insurance / trust / general assets of sponsor; 1 = checked. Self-funded welfare plans often still check only 'insurance' - confirm via Schedule C claims administrators and stop-loss on Schedule A.")]
        if "participants" in charts: el.append(Image(str(charts["participants"]), width=500, height=200))
        el += [Paragraph("3. Signer timeline (plan administrator / sponsor signature)", s["Heading2"]), T(d["signers"])]
    if "efast_index" in d and not d["efast_index"].empty:
        el += [Paragraph("EFAST2 live index (includes filings not yet in bulk data)", s["Heading2"]),
               T(d["efast_index"][["planyear", "pn", "ack_id", "plansponsor", "planname", "participantsboy", "assetseoy", "datereceived"]])]
    el += [PageBreak(), Paragraph("4. Broker-of-record timeline", s["Heading2"])]
    tl = d["broker_timeline"]
    if not tl.empty:
        for g in sorted(tl.group.unique()):
            fy = brokers.first_appearance(tl, g)
            el.append(P(f"<b>{g}</b>: first appears plan year {fy}; last {int(tl[tl.group == g].year.max())}"))
        cols = [c for c in ["year", "pn", "source", "group", "contracts", "commission", "fees", "sch_c_direct", "sch_c_indirect", "names", "cities"] if c in tl]
        el += [T(tl, cols), Spacer(1, 6), Paragraph("Detected broker changes", s["Heading3"]), T(d["broker_changes"])]
        if "brokers" in charts: el.append(Image(str(charts["brokers"]), width=500, height=220))
    else:
        el.append(P("No Schedule A Part I brokers found."))
    a = d["sch_a"]
    el += [PageBreak(), Paragraph("5. Insurance contracts (Schedule A)", s["Heading2"])]
    if not a.empty:
        yt = a.groupby(["DATASET_YEAR", "pn"]).agg(contracts=("carrier", "size"), premium=("premium", "sum"),
                                                   commissions=("comm_total", "sum"), fees=("fees_total", "sum")).reset_index()
        el += [T(yt), P("Premium = WLFR_TOT_CHARGES_PAID_AMT, else WLFR_TOT_EARNED_PREM_AMT (experience-rated). ASO/performance-guarantee lines are not insured premium. Self-funded claims never appear on Schedule A.")]
        if "premium" in charts: el.append(Image(str(charts["premium"]), width=500, height=220))
        el.append(T(a, ["DATASET_YEAR", "pn", "carrier", "carrier_ein", "naic", "contract", "covered", "category", "benefits", "premium", "comm_total", "fees_total", "policy_to"]))
    else:
        el.append(P("No Schedule A rows."))
    el += [PageBreak(), Paragraph("6. Service providers (Schedule C Part I item 2)", s["Heading2"]),
           T(d["sch_c"], ["DATASET_YEAR", "pn", "provider", "provider_ein", "relation", "provider_city", "direct_comp", "indirect_comp"] if not d["sch_c"].empty else None)]
    h = d["sch_h"]
    el += [PageBreak(), Paragraph("7. Financials (Schedule H)", s["Heading2"])]
    if not h.empty:
        keep = [c for c in ["pn", "DATASET_YEAR", "NET_ASSETS_EOY_AMT", "EMPLR_CONTRIB_INCOME_AMT", "PARTICIPANT_CONTRIB_AMT", "OTH_CONTRIB_RCVD_AMT",
                            "TOT_INCOME_AMT", "TOT_DISTRIB_BNFT_AMT", "TOT_ADMIN_EXPENSES_AMT", "NET_INCOME_AMT", "ACCOUNTANT_FIRM_NAME", "ACCTNT_OPINION_TYPE_CD"] if c in h]
        el.append(T(h, keep))
        if "assets" in charts: el.append(Image(str(charts["assets"]), width=500, height=200))
    else:
        el.append(P("No Schedule H (e.g., unfunded/insured welfare plan, or small plan on Schedule I / 5500-SF)."))
    el += [Paragraph("8. Schedule glossary", s["Heading2"]), T(pd.DataFrame(GLOSSARY, columns=["Form", "What it reports"]), widths=[110, 600]),
           Paragraph("9. Caveats", s["Heading2"]),
           P("Self-reported filings, posted without DOL audit. 'Latest' datasets hold the latest filing per plan year; the newest dataset year is partial. "
             "Broker grouping uses name normalization + an alias list (form5500.config.BROKER_ALIASES / ~/.form5500/broker_aliases.txt) and can merge or split entities imperfectly. "
             "Schedule A excludes self-funded claims and ASO fees; employer-paid consulting fees outside the plan are not reported anywhere. "
             "Benefit categories are a heuristic classification of indicator flags/free text.")]
    def foot(cv, doc):
        cv.setFont("Helvetica", 7); cv.drawString(30, 15, f"{name} - Form 5500 report - page {doc.page} - source: DOL EBSA datasets / EFAST2")
    SimpleDocTemplate(str(path), pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24).build(el, onFirstPage=foot, onLaterPages=foot)
