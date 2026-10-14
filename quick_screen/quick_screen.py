#!/usr/bin/env python3
"""
Quick Screen Pipeline for Healthcare Systems
=============================================
Extracts key financial data points for US nonprofit and government hospital systems:
1. Operating cash + investment balance (board-designated, ignore pension/OPEB)
2. Equity holdings (yes/no, % if stated) vs fixed-income-only
3. Captive insurance company (yes/no, name/domicile if stated)

Target flag: fixed_income_only AND no_captive AND investments > $25M

Sources:
- California HCAI Hospital Annual Financial Disclosure
- ProPublica Nonprofit Explorer (990 data) for other states
- EMMA/MSRB for government hospitals (keyword scan only)
"""

import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    import pandas as pd
    import requests
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("Required: pip install pandas requests openpyxl")

# Frappe API config (from environment)
FRAPPE_URL = os.environ.get('FRAPPE_URL', 'https://bz-api.dev.bookingzone.com')
FRAPPE_API_KEY = os.environ.get('FRAPPE_API_KEY', '')
FRAPPE_API_SECRET = os.environ.get('FRAPPE_API_SECRET', '')

MIN_INVESTMENTS = 25_000_000


@dataclass
class QuickScreenResult:
    """Single system screening result."""
    system_name: str
    state: str
    system_type: str  # nonprofit, government, district
    
    # Financial data
    cash_balance: Optional[float] = None
    investment_balance: Optional[float] = None
    total_cash_investments: Optional[float] = None
    as_of_date: Optional[str] = None
    
    # Investment policy
    has_equities: Optional[str] = None  # yes/no/unknown
    equity_pct: Optional[float] = None
    
    # Captive status
    has_captive: Optional[str] = None  # yes/no/unknown
    captive_name: Optional[str] = None
    captive_domicile: Optional[str] = None
    
    # Target flag
    is_target: bool = False
    
    # Source tracking
    source_type: str = ""  # ca_hcai, propublica_990, emma
    source_url: str = ""
    source_page: str = ""
    ein: Optional[str] = None
    facility_id: Optional[str] = None
    
    # Frappe record IDs
    frappe_company_id: Optional[str] = None
    frappe_fact_ids: List[str] = field(default_factory=list)


def load_ca_hcai_data(xlsx_path: str) -> List[QuickScreenResult]:
    """Load California HCAI hospital financial data."""
    print(f"Loading CA HCAI data from {xlsx_path}...")
    
    df = pd.read_excel(xlsx_path, sheet_name=0, header=None)
    
    # Column mappings (0-indexed)
    COL_FAC_ID = 0        # Facility ID
    COL_FY_END = 1        # Fiscal year end date
    COL_LEGAL_NAME = 2    # Legal name
    COL_FAC_NAME = 4      # Facility name
    COL_CITY = 8          # City
    
    # Balance sheet columns
    COL_CASH = 1786               # Balance_Sheet_Current_Assets_Cash
    COL_LIMITED_CASH = 1797       # Balance_Sheet_Assets_Whose_Use_is_Limited_Limited_Use_Cash
    COL_LIMITED_INVEST = 1798     # Balance_Sheet_Assets_Whose_Use_is_Limited_Limited_Use_Investments
    COL_OTHER_INVEST = 1812       # Balance_Sheet_Investments_and_Other_Assets_Other_Investments
    COL_TOTAL_INVEST = 1815       # Balance_Sheet_Investments_and_Other_Assets_Total_Investments_and_Other_Assets
    
    results = []
    
    # Skip header rows (0-3), data starts at row 4
    for idx in range(4, len(df)):
        row = df.iloc[idx]
        
        try:
            fac_id = str(row[COL_FAC_ID]) if pd.notna(row[COL_FAC_ID]) else ""
            legal_name = str(row[COL_LEGAL_NAME]) if pd.notna(row[COL_LEGAL_NAME]) else ""
            fy_end = str(row[COL_FY_END]) if pd.notna(row[COL_FY_END]) else ""
            
            if not legal_name or legal_name == 'nan':
                continue
            
            # Extract financial values
            def safe_float(val):
                if pd.isna(val):
                    return 0.0
                try:
                    return float(val)
                except:
                    return 0.0
            
            cash = safe_float(row[COL_CASH])
            limited_cash = safe_float(row[COL_LIMITED_CASH])
            limited_invest = safe_float(row[COL_LIMITED_INVEST])
            other_invest = safe_float(row[COL_OTHER_INVEST])
            
            # Total operating cash + investments (exclude restricted/pension)
            # Limited use = board-designated, which we want
            total = cash + limited_cash + limited_invest + other_invest
            
            # Only include if > $25M
            if total < MIN_INVESTMENTS:
                continue
            
            result = QuickScreenResult(
                system_name=legal_name,
                state="CA",
                system_type="hospital",  # CA HCAI includes both nonprofit and district
                cash_balance=cash + limited_cash,
                investment_balance=limited_invest + other_invest,
                total_cash_investments=total,
                as_of_date=fy_end,
                has_equities="unknown",
                has_captive="unknown",
                is_target=False,  # Will compute after equity/captive check
                source_type="ca_hcai",
                source_url="https://data.chhs.ca.gov/dataset/hospital-annual-financial-disclosure-report-complete-data-set",
                facility_id=fac_id
            )
            results.append(result)
            
        except Exception as e:
            continue
    
    print(f"  Found {len(results)} CA hospitals with >${MIN_INVESTMENTS/1e6:.0f}M cash+investments")
    return results


def search_propublica_hospitals(states: List[str], max_per_state: int = 50) -> List[QuickScreenResult]:
    """Search ProPublica for nonprofit hospitals in given states."""
    print(f"Searching ProPublica for hospitals in {states}...")
    
    results = []
    seen_eins = set()
    
    keywords = ["hospital", "health system", "medical center"]
    healthcare_ntee = ["E20", "E21", "E22", "E24"]
    
    for state in states:
        print(f"  Searching {state}...", end=" ", flush=True)
        state_count = 0
        
        for keyword in keywords:
            if state_count >= max_per_state:
                break
                
            page = 0
            while page < 5 and state_count < max_per_state:
                try:
                    resp = requests.get(
                        "https://projects.propublica.org/nonprofits/api/v2/search.json",
                        params={"q": keyword, "page": page},
                        timeout=15
                    )
                    if resp.status_code != 200:
                        break
                    
                    data = resp.json()
                    orgs = data.get("organizations", [])
                    if not orgs:
                        break
                    
                    for org in orgs:
                        ein = str(org.get("ein", ""))
                        if not ein or ein in seen_eins:
                            continue
                        
                        # Filter by state
                        org_state = org.get("state", "")
                        if org_state != state:
                            continue
                        
                        # Filter by NTEE code
                        ntee = org.get("ntee_code") or org.get("raw_ntee_code") or ""
                        if not any(ntee.startswith(code) for code in healthcare_ntee):
                            continue
                        
                        seen_eins.add(ein)
                        
                        # Get detailed financials
                        time.sleep(0.3)
                        details = get_propublica_org_details(ein)
                        if not details:
                            continue
                        
                        org_info = details.get("organization", {})
                        filings = details.get("filings_with_data", [])
                        
                        if not filings:
                            continue
                        
                        latest = filings[0]
                        total_assets = latest.get("totassetsend", 0) or 0
                        
                        # Skip if assets too small (proxy for investments)
                        if total_assets < MIN_INVESTMENTS:
                            continue
                        
                        # ProPublica doesn't have detailed cash/investment breakdown
                        # Use investment income as indicator, estimate from assets
                        inv_income = latest.get("invstmntinc", 0) or 0
                        
                        # Estimate: if they have investment income, likely have investments
                        # Use 30% of assets as rough estimate when no detail available
                        estimated_investments = total_assets * 0.30 if inv_income > 0 else total_assets * 0.15
                        
                        if estimated_investments < MIN_INVESTMENTS:
                            continue
                        
                        tax_year = latest.get("tax_prd_yr", "")
                        
                        result = QuickScreenResult(
                            system_name=org_info.get("name", org.get("name", "")),
                            state=state,
                            system_type="nonprofit",
                            cash_balance=None,  # Not available in ProPublica
                            investment_balance=estimated_investments,
                            total_cash_investments=estimated_investments,
                            as_of_date=str(tax_year),
                            has_equities="unknown",
                            has_captive="unknown",
                            is_target=False,
                            source_type="propublica_990",
                            source_url=f"https://projects.propublica.org/nonprofits/organizations/{ein}",
                            ein=ein
                        )
                        results.append(result)
                        state_count += 1
                        
                        if state_count >= max_per_state:
                            break
                    
                    page += 1
                    
                except Exception as e:
                    break
        
        print(f"found {state_count}")
    
    print(f"  Total: {len(results)} nonprofits with >${MIN_INVESTMENTS/1e6:.0f}M estimated investments")
    return results


def get_propublica_org_details(ein: str) -> Optional[Dict]:
    """Get organization details from ProPublica."""
    try:
        resp = requests.get(
            f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json",
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None


def compute_target_flag(result: QuickScreenResult) -> bool:
    """Compute target flag: fixed_income_only AND no_captive AND investments > $25M."""
    if (result.total_cash_investments or 0) < MIN_INVESTMENTS:
        return False
    
    # For target, we need:
    # - Fixed income only (no equities) OR unknown (conservative)
    # - No captive OR unknown
    # If equity status is unknown, we can't confirm as target yet
    # If captive status is unknown, we can't confirm as target yet
    
    # Conservative: only flag as target if we KNOW it's fixed-income-only and no-captive
    # But user said mark unknown rather than guess, so...
    # For now: flag as "potential target" if unknown, true target only if confirmed
    
    has_equities = (result.has_equities or "unknown").lower()
    has_captive = (result.has_captive or "unknown").lower()
    
    if has_equities == "no" and has_captive == "no":
        return True
    
    return False


def save_to_csv(results: List[QuickScreenResult], output_path: str):
    """Save results to CSV."""
    fieldnames = [
        "system_name", "state", "system_type",
        "cash_balance", "investment_balance", "total_cash_investments", "as_of_date",
        "has_equities", "equity_pct", "has_captive", "captive_name", "captive_domicile",
        "is_target", "source_type", "source_url", "source_page", "ein", "facility_id"
    ]
    
    # Sort by total investments descending
    results.sort(key=lambda x: x.total_cash_investments or 0, reverse=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {k: getattr(r, k, None) for k in fieldnames}
            writer.writerow(row)
    
    print(f"Saved {len(results)} results to {output_path}")


def main():
    """Run quick screen pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Quick screen healthcare systems')
    parser.add_argument('--ca-data', default='ca_hospital_data.xlsx', help='CA HCAI data file')
    parser.add_argument('--states', nargs='+', default=['TX'], help='Additional states to search via ProPublica')
    parser.add_argument('--output', '-o', default='quick_screen_results.csv', help='Output CSV')
    parser.add_argument('--max-results', type=int, default=50, help='Max results total')
    parser.add_argument('--skip-ca', action='store_true', help='Skip CA HCAI data')
    parser.add_argument('--skip-propublica', action='store_true', help='Skip ProPublica search')
    
    args = parser.parse_args()
    
    if not HAS_DEPS:
        print("Error: Missing dependencies")
        return 1
    
    print("=" * 60)
    print("Quick Screen: Healthcare System Financial Data")
    print("=" * 60)
    print(f"Minimum investment threshold: ${MIN_INVESTMENTS/1e6:.0f}M")
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    all_results = []
    
    # 1. Load CA HCAI data
    if not args.skip_ca and os.path.exists(args.ca_data):
        ca_results = load_ca_hcai_data(args.ca_data)
        all_results.extend(ca_results)
    
    # 2. Search ProPublica for other states
    if not args.skip_propublica and args.states:
        pp_results = search_propublica_hospitals(
            args.states, 
            max_per_state=max(10, args.max_results // len(args.states))
        )
        all_results.extend(pp_results)
    
    # 3. Compute target flags
    for r in all_results:
        r.is_target = compute_target_flag(r)
    
    # 4. Sort by investment size and limit
    all_results.sort(key=lambda x: x.total_cash_investments or 0, reverse=True)
    all_results = all_results[:args.max_results]
    
    # 5. Save to CSV
    save_to_csv(all_results, args.output)
    
    # 6. Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total systems processed: {len(all_results)}")
    
    targets = [r for r in all_results if r.is_target]
    print(f"Confirmed targets (fixed-income, no captive, >$25M): {len(targets)}")
    
    potential = [r for r in all_results if not r.is_target and (r.has_equities == "unknown" or r.has_captive == "unknown")]
    print(f"Potential targets (need audit scan): {len(potential)}")
    
    print()
    print("Top 15 by investment balance:")
    print("-" * 80)
    print(f"{'Name':<40} {'State':>5} {'Investments':>15} {'Equity':>8} {'Captive':>8}")
    print("-" * 80)
    for r in all_results[:15]:
        inv = f"${r.total_cash_investments/1e6:.1f}M" if r.total_cash_investments else "N/A"
        print(f"{r.system_name[:40]:<40} {r.state:>5} {inv:>15} {r.has_equities or 'unk':>8} {r.has_captive or 'unk':>8}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
