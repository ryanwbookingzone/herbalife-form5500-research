#!/usr/bin/env python3
"""
Bulk captive opportunity screen for S&P 500 and Nasdaq companies.
Uses only bulk data sources: SEC EDGAR XBRL, DOL Form 5500.
"""
import json
import hashlib
import time
import sys
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd
import duckdb

print("Starting script...", flush=True)

# Configuration
SEC_USER_AGENT = "Mozilla/5.0 (CaptiveScreen/1.0; Contact: research@example.com)"
FORM5500_DB = Path.home() / ".form5500" / "form5500.duckdb"
OUTPUT_DIR = Path("/workspace/captive_screen/output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Rate limiting for SEC API
SEC_RATE_LIMIT = 8
last_sec_request = 0

# Hardcoded S&P 500 top tickers (for reliability)
SP500_TICKERS = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "AVGO",
    "JPM", "TSLA", "UNH", "V", "XOM", "MA", "COST", "JNJ", "PG", "HD",
    "WMT", "ABBV", "MRK", "ORCL", "CVX", "BAC", "KO", "NFLX", "PEP", "CRM",
    "AMD", "TMO", "CSCO", "ABT", "MCD", "ACN", "LIN", "ADBE", "WFC", "DHR",
    "TXN", "DIS", "PM", "INTC", "INTU", "VZ", "AMGN", "IBM", "QCOM", "CAT",
    "CMCSA", "GE", "PFE", "NKE", "UNP", "NOW", "BA", "HON", "ISRG", "COP",
    "RTX", "SPGI", "LOW", "NEE", "GS", "T", "AXP", "BKNG", "BLK", "MS",
    "SYK", "SBUX", "ELV", "TJX", "MDT", "PLD", "GILD", "MDLZ", "DE", "VRTX",
    "LMT", "MMC", "ADP", "AMT", "CB", "BMY", "ETN", "LRCX", "ADI", "SCHW",
    "REGN", "SO", "CVS", "MO", "SLB", "DUK", "CI", "PNC", "AMAT", "CME",
    "ZTS", "USB", "TGT", "FDX", "CL", "EOG", "CMG", "FCX", "ICE", "BDX",
    "APD", "ITW", "WM", "MCK", "EMR", "AON", "SHW", "GD", "NOC", "HCA"
}

NASDAQ_TICKERS = {
    "ADSK", "AEP", "ALGN", "ANSS", "ASML", "BIIB", "CDNS", "CTAS", "CPRT",
    "CRWD", "DDOG", "DXCM", "EA", "EBAY", "ENPH", "EXC", "FANG", "FAST", "FISV",
    "FTNT", "IDXX", "ILMN", "KDP", "KHC", "KLAC", "MAR", "MCHP", "MELI",
    "MNST", "MRNA", "MRVL", "NXPI", "ODFL", "ON", "PANW", "PAYX", "PCAR",
    "PYPL", "ROST", "SNPS", "TEAM", "TMUS", "TTWO", "VRSK", "WBD",
    "WDAY", "XEL", "ZM", "ZS"
}

def sec_request(url, timeout=30, retries=3):
    """Make a rate-limited request to SEC API with retries."""
    global last_sec_request
    
    for attempt in range(retries):
        elapsed = time.time() - last_sec_request
        if elapsed < 1.0 / SEC_RATE_LIMIT:
            time.sleep(1.0 / SEC_RATE_LIMIT - elapsed)
        last_sec_request = time.time()
        
        headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                if 'json' in r.headers.get('content-type', ''):
                    return r.json()
                return r.text
            elif r.status_code == 429:
                wait = min(2 ** attempt * 2, 30)
                print(f"  ! Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    return None

def load_sec_companies():
    """Load SEC company tickers from bulk JSON."""
    json_path = Path("/workspace/captive_screen/company_tickers.json")
    if not json_path.exists():
        print("  ! company_tickers.json not found", flush=True)
        return pd.DataFrame()
    
    with open(json_path) as f:
        data = json.load(f)
    companies = []
    for k, v in data.items():
        companies.append({
            "cik": str(v["cik_str"]).zfill(10),
            "ticker": v["ticker"],
            "company_name": v["title"]
        })
    return pd.DataFrame(companies)

def get_company_ein_from_sec(cik):
    """Get company EIN from SEC submissions."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = sec_request(url)
    if data and isinstance(data, dict):
        ein = data.get("ein", "")
        return ein.replace("-", "") if ein else None
    return None

def get_sec_financials(cik):
    """Get key financial facts from SEC XBRL companyfacts API."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    data = sec_request(url)
    if not data or not isinstance(data, dict):
        return {}
    
    facts = {}
    us_gaap = data.get("facts", {}).get("us-gaap", {})
    
    def get_latest_annual(concept_name):
        concept = us_gaap.get(concept_name, {})
        units = concept.get("units", {})
        for unit_type in ["USD", "shares", "pure"]:
            if unit_type in units:
                annual = [u for u in units[unit_type] if u.get("form") == "10-K"]
                if annual:
                    annual.sort(key=lambda x: x.get("end", ""), reverse=True)
                    return annual[0].get("val"), annual[0].get("fy")
        return None, None
    
    metrics = {
        "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        "cash": ["CashAndCashEquivalentsAtCarryingValue", "Cash"],
        "total_assets": ["Assets"],
    }
    
    for key, concepts in metrics.items():
        for concept in concepts:
            val, fy = get_latest_annual(concept)
            if val is not None:
                facts[key] = val
                facts[f"{key}_fy"] = fy
                break
    
    # Get employee count
    dei = data.get("facts", {}).get("dei", {})
    emp_concept = dei.get("EntityNumberOfEmployees", {})
    emp_units = emp_concept.get("units", {})
    if "pure" in emp_units:
        annual = [u for u in emp_units["pure"] if u.get("form") == "10-K"]
        if annual:
            annual.sort(key=lambda x: x.get("end", ""), reverse=True)
            facts["employees"] = annual[0].get("val")
    
    return facts

def get_form5500_data(con, ein):
    """Get Form 5500 data for a company by EIN."""
    if not ein:
        return {}
    
    ein = str(ein).replace("-", "")
    
    try:
        # Get welfare plans
        welfare = con.execute(f"""
            SELECT DATASET_YEAR, pn, participants_eoy, welfare_codes
            FROM filings 
            WHERE ein='{ein}' AND pn LIKE '5%' AND DATASET_YEAR >= 2023
            ORDER BY DATASET_YEAR DESC, participants_eoy DESC
            LIMIT 5
        """).fetchall()
        
        # Get Schedule A premiums
        premiums = con.execute(f"""
            SELECT DATASET_YEAR, sum(premium) as total_premium
            FROM sch_a WHERE ein='{ein}' AND DATASET_YEAR >= 2023
            GROUP BY 1 ORDER BY 1 DESC LIMIT 2
        """).fetchall()
        
        # Get brokers
        brokers = con.execute(f"""
            SELECT DATASET_YEAR, broker, sum(commission) + sum(fees) as total_comp
            FROM sch_a_brokers WHERE ein='{ein}' AND DATASET_YEAR >= 2023
            GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC LIMIT 5
        """).fetchall()
        
        result = {
            "has_welfare_plan": len(welfare) > 0,
            "welfare_participants": welfare[0][2] if welfare else 0,
        }
        
        if premiums:
            result["total_premium"] = premiums[0][1] if premiums else 0
            result["premium_year"] = premiums[0][0] if premiums else None
        
        if brokers:
            result["primary_broker"] = brokers[0][1]
            result["broker_commission"] = brokers[0][2]
        
        return result
        
    except Exception as e:
        return {}

def calculate_captive_score(row):
    """Calculate captive opportunity score (0-100)."""
    score = 0
    
    # Cash availability (up to 25 points)
    cash = row.get("cash", 0) or 0
    if cash > 10_000_000_000:
        score += 25
    elif cash > 1_000_000_000:
        score += 20
    elif cash > 100_000_000:
        score += 10
    
    # Premium size (up to 25 points)
    premium = row.get("total_premium", 0) or 0
    if premium > 100_000_000:
        score += 25
    elif premium > 10_000_000:
        score += 20
    elif premium > 1_000_000:
        score += 10
    
    # Employee count (up to 15 points)
    employees = row.get("employees", 0) or 0
    if employees > 50000:
        score += 15
    elif employees > 10000:
        score += 10
    elif employees > 1000:
        score += 5
    
    # Revenue (up to 20 points)
    revenue = row.get("revenue", 0) or 0
    if revenue > 50_000_000_000:
        score += 20
    elif revenue > 10_000_000_000:
        score += 15
    elif revenue > 1_000_000_000:
        score += 10
    
    # Has welfare plan data (15 points)
    if row.get("has_welfare_plan"):
        score += 15
    
    return min(score, 100)

def generate_listing_id(ticker, cik):
    """Generate a unique listing ID."""
    base = f"{ticker}-{cik}" if ticker else f"CIK-{cik}"
    return base.upper()

def main():
    print("=== Bulk Captive Opportunity Screen ===", flush=True)
    print(f"Started: {datetime.now().isoformat()}\n", flush=True)
    
    # Step 1: Load company universe
    print("Step 1: Loading company universe...", flush=True)
    sec_companies = load_sec_companies()
    print(f"  Loaded {len(sec_companies)} SEC-registered companies", flush=True)
    
    # Use hardcoded tickers
    target_tickers = SP500_TICKERS | (NASDAQ_TICKERS - SP500_TICKERS)
    print(f"  Using {len(SP500_TICKERS)} S&P 500 + {len(NASDAQ_TICKERS - SP500_TICKERS)} Nasdaq tickers", flush=True)
    
    # Filter SEC companies to our universe
    companies = sec_companies[sec_companies["ticker"].isin(target_tickers)].copy()
    companies["index"] = companies["ticker"].apply(lambda t: "SP500" if t in SP500_TICKERS else "NASDAQ")
    print(f"  Matched {len(companies)} companies in SEC database", flush=True)
    
    if len(companies) == 0:
        print("  ! No companies found!", flush=True)
        return pd.DataFrame()
    
    # Limit for cost efficiency
    MAX_COMPANIES = 150
    if len(companies) > MAX_COMPANIES:
        companies = companies.head(MAX_COMPANIES)
    print(f"  Processing: {len(companies)} companies", flush=True)
    
    # Step 2: Get EINs from SEC submissions
    print("\nStep 2: Getting EINs from SEC submissions...", flush=True)
    ein_cache = {}
    total = len(companies)
    for idx, (i, row) in enumerate(companies.iterrows()):
        if (idx + 1) % 20 == 0 or idx == 0 or idx == total - 1:
            print(f"  Progress: {idx + 1}/{total}", flush=True)
        ein = get_company_ein_from_sec(row["cik"])
        ein_cache[row["cik"]] = ein
    companies["ein"] = companies["cik"].map(ein_cache)
    print(f"  Found EINs for {companies['ein'].notna().sum()} companies", flush=True)
    
    # Step 3: Match to Form 5500 data
    print("\nStep 3: Matching to Form 5500 data...", flush=True)
    if FORM5500_DB.exists():
        con = duckdb.connect(str(FORM5500_DB), read_only=True)
        
        form5500_data = []
        for i, row in companies.iterrows():
            f5500 = get_form5500_data(con, row["ein"])
            form5500_data.append(f5500)
        
        if form5500_data:
            f5500_df = pd.DataFrame(form5500_data)
            companies = pd.concat([companies.reset_index(drop=True), f5500_df], axis=1)
        con.close()
        
        if "has_welfare_plan" in companies.columns:
            matched = companies["has_welfare_plan"].fillna(False).sum()
            print(f"  Matched {matched} companies to Form 5500 welfare plans", flush=True)
    else:
        print("  ! Form 5500 database not found", flush=True)
    
    # Step 4: Get SEC financials
    print("\nStep 4: Getting SEC financials...", flush=True)
    financials_data = []
    total = len(companies)
    
    for idx, (i, row) in enumerate(companies.iterrows()):
        if (idx + 1) % 20 == 0 or idx == 0 or idx == total - 1:
            print(f"  Progress: {idx + 1}/{total}", flush=True)
        fins = get_sec_financials(row["cik"])
        financials_data.append(fins)
    
    fins_df = pd.DataFrame(financials_data)
    companies = pd.concat([companies.reset_index(drop=True), fins_df], axis=1)
    print(f"  Got financials for {companies['cash'].notna().sum()} companies", flush=True)
    
    # Step 5: Calculate scores and rank
    print("\nStep 5: Calculating captive opportunity scores...", flush=True)
    companies["captive_score"] = companies.apply(calculate_captive_score, axis=1)
    companies["listing_id"] = companies.apply(lambda r: generate_listing_id(r["ticker"], r["cik"]), axis=1)
    companies = companies.sort_values("captive_score", ascending=False)
    
    # Step 6: Save results
    print("\nStep 6: Saving results...", flush=True)
    
    # Clean up columns for output
    output_cols = [
        "listing_id", "ticker", "company_name", "cik", "ein", "index",
        "captive_score", "has_welfare_plan", "cash", "revenue", "employees", 
        "total_assets", "total_premium", "premium_year",
        "welfare_participants", "primary_broker", "broker_commission"
    ]
    available_cols = [c for c in output_cols if c in companies.columns]
    
    # Save full dataset
    full_path = OUTPUT_DIR / "full_screen_results.csv"
    companies[available_cols].to_csv(full_path, index=False)
    print(f"  Saved full results: {len(companies)} companies to {full_path}", flush=True)
    
    # Save top opportunities
    top_50 = companies.head(50)
    top_path = OUTPUT_DIR / "top_50_opportunities.csv"
    top_50[available_cols].to_csv(top_path, index=False)
    print(f"  Saved top 50 opportunities to {top_path}", flush=True)
    
    # Summary stats
    print("\n" + "=" * 50, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 50, flush=True)
    print(f"Total companies processed: {len(companies)}", flush=True)
    print(f"  S&P 500: {(companies['index']=='SP500').sum()}", flush=True)
    print(f"  Nasdaq: {(companies['index']=='NASDAQ').sum()}", flush=True)
    print(f"Companies with EINs: {companies['ein'].notna().sum()}", flush=True)
    if "has_welfare_plan" in companies.columns:
        print(f"Companies with welfare plans: {companies['has_welfare_plan'].fillna(False).sum()}", flush=True)
    if "total_premium" in companies.columns:
        print(f"Companies with premium data: {(companies['total_premium'].fillna(0) > 0).sum()}", flush=True)
    print(f"Companies with SEC financials: {companies['cash'].notna().sum()}", flush=True)
    
    print("\n" + "=" * 50, flush=True)
    print("TOP 25 CAPTIVE OPPORTUNITIES", flush=True)
    print("=" * 50, flush=True)
    display_cols = ["ticker", "company_name", "captive_score", "cash", "total_premium", "employees"]
    display_cols = [c for c in display_cols if c in companies.columns]
    print(companies.head(25)[display_cols].to_string(), flush=True)
    
    print(f"\nCompleted: {datetime.now().isoformat()}", flush=True)
    return companies

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
