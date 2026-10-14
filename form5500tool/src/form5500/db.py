"""Load DOL zips into DuckDB (all columns VARCHAR, union-by-name across years) and build analysis views."""
import re, tempfile, time, zipfile
from pathlib import Path
import duckdb
from . import config
from .download import local_path

def connect(db_path=config.DB_PATH, read_only=False):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=read_only)
    if not read_only:
        con.execute("""CREATE TABLE IF NOT EXISTS _loads(dataset VARCHAR, year INTEGER, zip VARCHAR, zip_size BIGINT,
                       rows BIGINT, loaded_at DOUBLE)""")
        con.execute("CREATE TABLE IF NOT EXISTS _layouts(dataset VARCHAR, year INTEGER, file VARCHAR, text VARCHAR)")
    return con

def tables(con):
    return {r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()}

def columns(con, table):
    return [r[0] for r in con.execute(
        "select column_name from information_schema.columns where table_name=? order by ordinal_position", [table]).fetchall()]

def _loaded(con, name, year, size):
    r = con.execute("select zip_size from _loads where dataset=? and year=? order by loaded_at desc limit 1", [name, year]).fetchone()
    return r is not None and r[0] == size

def load(con, datasets, years, raw_dir=config.RAW_DIR, force=False, log=print):
    """Load each available zip; skips (dataset, year) already loaded from an identical zip. Idempotent per year."""
    for y in years:
        for n in datasets:
            p = local_path(raw_dir, n, y)
            if not p.exists():
                continue
            size = p.stat().st_size
            if not force and _loaded(con, n, y, size):
                continue
            t0 = time.time()
            with zipfile.ZipFile(p) as z, tempfile.TemporaryDirectory() as td:
                csvs = [m for m in z.namelist() if m.lower().endswith(".csv")]
                for m in z.namelist():
                    if m.lower().endswith(".txt"):  # layout files shipped in the zip
                        txt = z.read(m).decode("latin-1")
                        con.execute("delete from _layouts where dataset=? and year=? and file=?", [n, y, m])
                        con.execute("insert into _layouts values (?,?,?,?)", [n, y, m, txt])
                if not csvs:
                    continue
                z.extract(csvs[0], td)
                src = str(Path(td) / csvs[0])
                rel = f"_stage_{n}_{y}".lower()
                def _read(path, enc):
                    con.execute(f"""create or replace temp table {rel} as
                        select {y}::INTEGER as DATASET_YEAR, * from read_csv('{path}', all_varchar=true, header=true,
                        quote='"', escape='"', encoding='{enc}', strict_mode=false, null_padding=true,
                        ignore_errors=true, sample_size=-1)""")
                try:
                    _read(src, "latin-1")
                except duckdb.InvalidInputException:
                    # DuckDB's latin-1 reader rejects some bytes (e.g. 0x80-0x9F); transcode via Python (cp1252->latin-1 fallback)
                    fixed = src + ".utf8.csv"
                    with open(src, "rb") as fi, open(fixed, "w", encoding="utf-8", newline="") as fo:
                        for chunk in iter(lambda: fi.read(1 << 24), b""):
                            fo.write(chunk.decode("cp1252", errors="replace"))
                    _read(fixed, "utf-8")
                # normalize column names to upper case
                cols = columns(con, rel)
                for c in cols:
                    if c != c.upper():
                        con.execute(f'alter table {rel} rename column "{c}" to "{c.upper()}"')
                t = n.upper()
                if t not in tables(con):
                    con.execute(f"create table {t} as select * from {rel} limit 0")
                existing = set(columns(con, t))
                for c in columns(con, rel):
                    if c not in existing:
                        con.execute(f'alter table {t} add column "{c}" VARCHAR')
                con.execute(f"delete from {t} where DATASET_YEAR={y}")
                con.execute(f"insert into {t} by name select * from {rel}")
                rows = con.execute(f"select count(*) from {rel}").fetchone()[0]
                con.execute(f"drop table {rel}")
            con.execute("delete from _loads where dataset=? and year=?", [n, y])
            con.execute("insert into _loads values (?,?,?,?,?,?)", [n, y, str(p), size, rows, time.time()])
            log(f"  loaded {n} {y}: {rows:,} rows in {time.time()-t0:.0f}s")
    build_views(con)

def _col(con, t, *names, default="NULL"):
    have = set(columns(con, t)) if t in tables(con) else set()
    for n in names:
        if n in have:
            return f'"{n}"'
    return default

def build_views(con):
    T = tables(con)
    parts = []
    if "F_5500" in T:
        c = lambda *a, **k: _col(con, "F_5500", *a, **k)
        parts.append(f"""select ACK_ID, DATASET_YEAR, '5500' as form, SPONS_DFE_EIN as ein, SPONS_DFE_PN as pn,
            SPONSOR_DFE_NAME as sponsor, PLAN_NAME as plan_name, {c('SPONS_DFE_MAIL_US_CITY')} as city,
            {c('SPONS_DFE_MAIL_US_STATE')} as state, {c('SPONS_DFE_MAIL_US_ZIP')} as zip, {c('BUSINESS_CODE')} as business_code,
            FORM_PLAN_YEAR_BEGIN_DATE as plan_year_begin, {c('FORM_TAX_PRD')} as plan_year_end,
            try_cast({c('TOT_PARTCP_BOY_CNT')} as BIGINT) as participants_boy,
            try_cast(coalesce({c('TOT_ACT_RTD_SEP_BENEF_CNT')}, {c('TOT_ACTIVE_PARTCP_CNT')}) as BIGINT) as participants_eoy,
            {c('TYPE_PENSION_BNFT_CODE')} as pension_codes, {c('TYPE_WELFARE_BNFT_CODE')} as welfare_codes,
            {c('FUNDING_INSURANCE_IND')} as fund_insurance, {c('FUNDING_TRUST_IND')} as fund_trust, {c('FUNDING_GEN_ASSET_IND')} as fund_gen_assets,
            {c('BENEFIT_INSURANCE_IND')} as bnft_insurance, {c('BENEFIT_TRUST_IND')} as bnft_trust, {c('BENEFIT_GEN_ASSET_IND')} as bnft_gen_assets,
            {c('ADMIN_SIGNED_NAME')} as admin_signer, {c('ADMIN_SIGNED_DATE')} as admin_signed_date,
            {c('SPONS_SIGNED_NAME')} as sponsor_signer, {c('ADMIN_NAME')} as admin_name,
            {c('SHORT_PLAN_YR_IND')} as short_year, {c('FINAL_FILING_IND')} as final_filing, {c('AMENDED_IND')} as amended,
            {c('DATE_RECEIVED')} as date_received, {c('NUM_SCH_A_ATTACHED_CNT')} as num_sch_a from F_5500""")
    if "F_5500_SF" in T:
        c = lambda *a, **k: _col(con, "F_5500_SF", *a, **k)
        parts.append(f"""select ACK_ID, DATASET_YEAR, '5500-SF' as form, SF_SPONS_EIN as ein, SF_PLAN_NUM as pn,
            SF_SPONSOR_NAME as sponsor, SF_PLAN_NAME as plan_name, {c('SF_SPONS_US_CITY')} as city, {c('SF_SPONS_US_STATE')} as state,
            {c('SF_SPONS_US_ZIP')} as zip, {c('SF_BUSINESS_CODE')} as business_code, SF_PLAN_YEAR_BEGIN_DATE as plan_year_begin,
            {c('SF_TAX_PRD')} as plan_year_end, try_cast({c('SF_TOT_PARTCP_BOY_CNT')} as BIGINT) as participants_boy,
            try_cast({c('SF_TOT_PARTCP_EOY_CNT')} as BIGINT) as participants_eoy, {c('SF_TYPE_PENSION_BNFT_CODE')} as pension_codes,
            {c('SF_TYPE_WELFARE_BNFT_CODE')} as welfare_codes, NULL, NULL, NULL, NULL, NULL, NULL,
            {c('SF_ADMIN_SIGNED_NAME')} as admin_signer, {c('SF_ADMIN_SIGNED_DATE')}, {c('SF_SPONS_SIGNED_NAME')}, {c('SF_ADMIN_NAME')},
            {c('SF_SHORT_PLAN_YR_IND')}, {c('SF_FINAL_FILING_IND')}, {c('SF_AMENDED_IND')}, {c('DATE_RECEIVED')}, NULL from F_5500_SF""")
    if parts:
        con.execute("create or replace view filings as " + " union all ".join(parts))
    if "F_SCH_A" in T and parts:
        c = lambda *a, **k: _col(con, "F_SCH_A", *a, **k)
        con.execute(f"""create or replace view sch_a as select a.ACK_ID, a.FORM_ID, f.DATASET_YEAR, f.ein, f.pn, f.sponsor, f.state,
            a.INS_CARRIER_NAME as carrier, a.INS_CARRIER_EIN as carrier_ein, a.INS_CARRIER_NAIC_CODE as naic, a.INS_CONTRACT_NUM as contract,
            try_cast(a.INS_PRSN_COVERED_EOY_CNT as BIGINT) as covered, a.INS_POLICY_FROM_DATE as policy_from, a.INS_POLICY_TO_DATE as policy_to,
            try_cast(a.INS_BROKER_COMM_TOT_AMT as DOUBLE) as comm_total, try_cast(a.INS_BROKER_FEES_TOT_AMT as DOUBLE) as fees_total,
            try_cast(coalesce(nullif({c('WLFR_TOT_CHARGES_PAID_AMT')},''), nullif({c('WLFR_TOT_EARNED_PREM_AMT')},'')) as DOUBLE) as premium,
            try_cast({c('PENSION_PREM_PAID_TOT_AMT')} as DOUBLE) as pension_premium,
            concat_ws(';', case when {c('WLFR_BNFT_HEALTH_IND')}='1' then 'HEALTH' end, case when {c('WLFR_BNFT_DENTAL_IND')}='1' then 'DENTAL' end,
              case when {c('WLFR_BNFT_VISION_IND')}='1' then 'VISION' end, case when {c('WLFR_BNFT_LIFE_INSUR_IND')}='1' then 'LIFE' end,
              case when {c('WLFR_BNFT_TEMP_DISAB_IND')}='1' then 'STD' end, case when {c('WLFR_BNFT_LONG_TERM_DISAB_IND')}='1' then 'LTD' end,
              case when {c('WLFR_BNFT_DRUG_IND')}='1' then 'DRUG' end, case when {c('WLFR_BNFT_STOP_LOSS_IND')}='1' or upper({c('WLFR_TYPE_BNFT_OTH_TEXT')}) like '%STOP%' then 'STOP_LOSS' end,
              case when {c('WLFR_BNFT_HMO_IND')}='1' then 'HMO' end, case when {c('WLFR_BNFT_PPO_IND')}='1' then 'PPO' end,
              case when {c('WLFR_BNFT_INDEMNITY_IND')}='1' then 'INDEMNITY' end, {c('WLFR_TYPE_BNFT_OTH_TEXT')}) as benefits
            from F_SCH_A a join filings f using (ACK_ID)""")
    if "F_SCH_A_PART1" in T and "F_SCH_A" in T:
        con.execute("""create or replace view sch_a_brokers as select p.ACK_ID, p.FORM_ID, s.DATASET_YEAR, s.ein, s.pn, s.sponsor, s.state,
            s.carrier, s.contract, s.covered, s.premium, p.INS_BROKER_NAME as broker, p.INS_BROKER_US_ADDRESS1 as broker_address,
            p.INS_BROKER_US_CITY as broker_city, p.INS_BROKER_US_STATE as broker_state, p.INS_BROKER_CODE as broker_code,
            try_cast(p.INS_BROKER_COMM_PD_AMT as DOUBLE) as commission, try_cast(p.INS_BROKER_FEES_PD_AMT as DOUBLE) as fees,
            p.INS_BROKER_FEES_PD_TEXT as fee_text from F_SCH_A_PART1 p join sch_a s on s.ACK_ID=p.ACK_ID and s.FORM_ID=p.FORM_ID""")
    if "F_SCH_C_PART1_ITEM2" in T:
        con.execute("""create or replace view sch_c_providers as select c.ACK_ID, f.DATASET_YEAR, f.ein, f.pn, f.sponsor, f.state,
            c.ROW_ORDER, c.PROVIDER_OTHER_NAME as provider, c.PROVIDER_OTHER_EIN as provider_ein, c.PROVIDER_OTHER_RELATION as relation,
            c.PROVIDER_OTHER_US_CITY as provider_city, try_cast(c.PROVIDER_OTHER_DIRECT_COMP_AMT as DOUBLE) as direct_comp,
            try_cast(c.PROV_OTHER_TOT_IND_COMP_AMT as DOUBLE) as indirect_comp from F_SCH_C_PART1_ITEM2 c join filings f using (ACK_ID)""")
    if "F_SCH_H" in T:
        con.execute("""create or replace view sch_h as select f.ein, f.pn, f.sponsor, h.* from F_SCH_H h join filings f using (ACK_ID)""")

def status(con):
    if "_loads" not in tables(con):
        return []
    return con.execute("select dataset, list(year order by year) as yrs, sum(rows) as n_rows from _loads group by 1 order by 1").fetchall()
