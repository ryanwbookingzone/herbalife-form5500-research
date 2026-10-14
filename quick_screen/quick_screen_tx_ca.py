#!/usr/bin/env python3
"""
Quick Screen TX & CA - Comprehensive scan of all nonprofit and government 
hospital/health systems in Texas and California.

Sources:
- CA HCAI Hospital Annual Financial Disclosure (all hospitals)
- ProPublica Nonprofit Explorer (TX NTEE E20-E22)
- Skip already processed systems from quick_screen_results.csv
"""

import csv
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set, Tuple

import pandas as pd
import requests

MIN_INVESTMENTS = 25_000_000
PROPUBLICA_API = "https://projects.propublica.org/nonprofits/api/v2"


@dataclass
class QuickScreenResult:
    system_name: str
    state: str
    system_type: str
    cash_balance: Optional[float] = None
    investment_balance: Optional[float] = None
    total_cash_investments: Optional[float] = None
    as_of_date: Optional[str] = None
    has_equities: Optional[str] = None
    equity_pct: Optional[float] = None
    has_captive: Optional[str] = None
    captive_name: Optional[str] = None
    captive_domicile: Optional[str] = None
    is_target: bool = False
    source_type: str = ""
    source_url: str = ""
    source_page: str = ""
    ein: Optional[str] = None
    facility_id: Optional[str] = None


def load_processed_systems(csv_path: str) -> Set[Tuple[str, str]]:
    """Load already processed systems to skip."""
    processed = set()
    if os.path.exists(csv_path):
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['system_name'].upper().strip(), row['state'])
                processed.add(key)
    return processed


def load_all_ca_hcai(xlsx_path: str, processed: Set) -> List[QuickScreenResult]:
    """Load ALL California hospitals from HCAI data with >$25M investments."""
    print(f"Loading ALL CA hospitals from HCAI...")
    
    df = pd.read_excel(xlsx_path, sheet_name=0, header=None)
    
    # Column mappings
    COL_FAC_ID = 0
    COL_FY_END = 1
    COL_LEGAL_NAME = 2
    COL_CASH = 1786
    COL_LIMITED_CASH = 1797
    COL_LIMITED_INVEST = 1798
    COL_OTHER_INVEST = 1812
    
    results = []
    skipped = 0
    
    for idx in range(4, len(df)):
        row = df.iloc[idx]
        
        try:
            fac_id = str(row[COL_FAC_ID]) if pd.notna(row[COL_FAC_ID]) else ""
            legal_name = str(row[COL_LEGAL_NAME]) if pd.notna(row[COL_LEGAL_NAME]) else ""
            fy_end = str(row[COL_FY_END]) if pd.notna(row[COL_FY_END]) else ""
            
            if not legal_name or legal_name == 'nan':
                continue
            
            # Check if already processed
            key = (legal_name.upper().strip(), "CA")
            if key in processed:
                skipped += 1
                continue
            
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
            
            total = cash + limited_cash + limited_invest + other_invest
            
            if total < MIN_INVESTMENTS:
                continue
            
            result = QuickScreenResult(
                system_name=legal_name,
                state="CA",
                system_type="hospital",
                cash_balance=cash + limited_cash,
                investment_balance=limited_invest + other_invest,
                total_cash_investments=total,
                as_of_date=fy_end,
                has_equities="unknown",
                has_captive="unknown",
                is_target=False,
                source_type="ca_hcai",
                source_url="https://data.chhs.ca.gov/dataset/hospital-annual-financial-disclosure-report-complete-data-set",
                facility_id=fac_id
            )
            results.append(result)
            
        except Exception as e:
            continue
    
    print(f"  Found {len(results)} new CA hospitals with >${MIN_INVESTMENTS/1e6:.0f}M")
    print(f"  Skipped {skipped} already processed")
    return results


def search_all_tx_propublica(processed: Set) -> List[QuickScreenResult]:
    """Search ProPublica for ALL Texas hospitals with NTEE E20-E22."""
    print(f"Searching ProPublica for ALL TX hospitals...")
    
    results = []
    seen_eins = set()
    healthcare_ntee = ["E20", "E21", "E22", "E24"]
    keywords = ["hospital", "health system", "medical center", "healthcare", "health care"]
    
    for keyword in keywords:
        print(f"  Searching '{keyword}'...", end=" ", flush=True)
        keyword_count = 0
        page = 0
        
        while page < 20:
            try:
                resp = requests.get(
                    f"{PROPUBLICA_API}/search.json",
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
                    if org_state != "TX":
                        continue
                    
                    # Filter by NTEE code
                    ntee = org.get("ntee_code") or org.get("raw_ntee_code") or ""
                    if not any(ntee.startswith(code) for code in healthcare_ntee):
                        continue
                    
                    org_name = org.get("name", "")
                    
                    # Check if already processed
                    key = (org_name.upper().strip(), "TX")
                    if key in processed:
                        continue
                    
                    seen_eins.add(ein)
                    
                    # Get detailed financials
                    time.sleep(0.3)
                    details = get_org_details(ein)
                    if not details:
                        continue
                    
                    org_info = details.get("organization", {})
                    filings = details.get("filings_with_data", [])
                    
                    if not filings:
                        continue
                    
                    latest = filings[0]
                    total_assets = latest.get("totassetsend", 0) or 0
                    
                    if total_assets < MIN_INVESTMENTS:
                        continue
                    
                    inv_income = latest.get("invstmntinc", 0) or 0
                    estimated_investments = total_assets * 0.30 if inv_income > 0 else total_assets * 0.15
                    
                    if estimated_investments < MIN_INVESTMENTS:
                        continue
                    
                    tax_year = latest.get("tax_prd_yr", "")
                    
                    result = QuickScreenResult(
                        system_name=org_info.get("name", org_name),
                        state="TX",
                        system_type="nonprofit",
                        cash_balance=None,
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
                    keyword_count += 1
                
                page += 1
                
            except Exception as e:
                break
        
        print(f"{keyword_count} found")
    
    # Deduplicate by EIN
    unique_results = {}
    for r in results:
        if r.ein and r.ein not in unique_results:
            unique_results[r.ein] = r
    
    results = list(unique_results.values())
    print(f"  Total unique TX nonprofits: {len(results)}")
    return results


def search_ca_propublica(processed: Set) -> List[QuickScreenResult]:
    """Search ProPublica for CA hospitals not in HCAI (e.g., system-level entities)."""
    print(f"Searching ProPublica for CA nonprofit health systems...")
    
    results = []
    seen_eins = set()
    healthcare_ntee = ["E20", "E21", "E22", "E24"]
    keywords = ["hospital", "health system", "medical center"]
    
    for keyword in keywords:
        print(f"  Searching '{keyword}'...", end=" ", flush=True)
        keyword_count = 0
        page = 0
        
        while page < 15:
            try:
                resp = requests.get(
                    f"{PROPUBLICA_API}/search.json",
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
                    
                    org_state = org.get("state", "")
                    if org_state != "CA":
                        continue
                    
                    ntee = org.get("ntee_code") or org.get("raw_ntee_code") or ""
                    if not any(ntee.startswith(code) for code in healthcare_ntee):
                        continue
                    
                    org_name = org.get("name", "")
                    key = (org_name.upper().strip(), "CA")
                    if key in processed:
                        continue
                    
                    seen_eins.add(ein)
                    
                    time.sleep(0.3)
                    details = get_org_details(ein)
                    if not details:
                        continue
                    
                    org_info = details.get("organization", {})
                    filings = details.get("filings_with_data", [])
                    
                    if not filings:
                        continue
                    
                    latest = filings[0]
                    total_assets = latest.get("totassetsend", 0) or 0
                    
                    if total_assets < MIN_INVESTMENTS:
                        continue
                    
                    inv_income = latest.get("invstmntinc", 0) or 0
                    estimated_investments = total_assets * 0.30 if inv_income > 0 else total_assets * 0.15
                    
                    if estimated_investments < MIN_INVESTMENTS:
                        continue
                    
                    tax_year = latest.get("tax_prd_yr", "")
                    
                    result = QuickScreenResult(
                        system_name=org_info.get("name", org_name),
                        state="CA",
                        system_type="nonprofit",
                        cash_balance=None,
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
                    keyword_count += 1
                
                page += 1
                
            except Exception as e:
                break
        
        print(f"{keyword_count} found")
    
    unique_results = {}
    for r in results:
        if r.ein and r.ein not in unique_results:
            unique_results[r.ein] = r
    
    results = list(unique_results.values())
    print(f"  Total unique CA nonprofits from ProPublica: {len(results)}")
    return results


def get_org_details(ein: str):
    """Get organization details from ProPublica."""
    try:
        resp = requests.get(f"{PROPUBLICA_API}/organizations/{ein}.json", timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None


def save_results(results: List[QuickScreenResult], output_path: str):
    """Save results to CSV."""
    fieldnames = [
        "system_name", "state", "system_type",
        "cash_balance", "investment_balance", "total_cash_investments", "as_of_date",
        "has_equities", "equity_pct", "has_captive", "captive_name", "captive_domicile",
        "is_target", "source_type", "source_url", "source_page", "ein", "facility_id"
    ]
    
    results.sort(key=lambda x: x.total_cash_investments or 0, reverse=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {k: getattr(r, k, None) for k in fieldnames}
            writer.writerow(row)


def main():
    print("=" * 70)
    print("Quick Screen TX & CA - Comprehensive Hospital/Health System Scan")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Minimum investment threshold: ${MIN_INVESTMENTS/1e6:.0f}M")
    print()
    
    # Load already processed
    processed = load_processed_systems('quick_screen_results.csv')
    print(f"Already processed: {len(processed)} systems")
    print()
    
    all_results = []
    
    # 1. Load ALL CA from HCAI
    if os.path.exists('ca_hospital_data.xlsx'):
        ca_hcai = load_all_ca_hcai('ca_hospital_data.xlsx', processed)
        all_results.extend(ca_hcai)
    
    # 2. Search CA via ProPublica (catch any not in HCAI)
    # Update processed set with what we just found
    for r in all_results:
        processed.add((r.system_name.upper().strip(), r.state))
    
    ca_propublica = search_ca_propublica(processed)
    all_results.extend(ca_propublica)
    
    # Update processed again
    for r in ca_propublica:
        processed.add((r.system_name.upper().strip(), r.state))
    
    # 3. Search ALL TX via ProPublica
    tx_results = search_all_tx_propublica(processed)
    all_results.extend(tx_results)
    
    # Sort by investment size
    all_results.sort(key=lambda x: x.total_cash_investments or 0, reverse=True)
    
    # Save
    save_results(all_results, 'quick_screen_tx_ca.csv')
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    ca_results = [r for r in all_results if r.state == "CA"]
    tx_results = [r for r in all_results if r.state == "TX"]
    
    print(f"Total NEW systems processed: {len(all_results)}")
    print(f"  California: {len(ca_results)}")
    print(f"  Texas: {len(tx_results)}")
    print()
    
    # Target counts (all unknown for now)
    ca_targets = [r for r in ca_results if r.is_target]
    tx_targets = [r for r in tx_results if r.is_target]
    print(f"Confirmed targets (fixed-income, no captive, >$25M):")
    print(f"  California: {len(ca_targets)}")
    print(f"  Texas: {len(tx_targets)}")
    print()
    
    # Top 15 CA
    print("TOP 15 CALIFORNIA:")
    print("-" * 90)
    print(f"{'Name':<45} {'Investments':>15} {'Equity':>10} {'Captive':>10}")
    print("-" * 90)
    for r in ca_results[:15]:
        inv = f"${r.total_cash_investments/1e6:.1f}M" if r.total_cash_investments else "N/A"
        print(f"{r.system_name[:45]:<45} {inv:>15} {r.has_equities or 'unk':>10} {r.has_captive or 'unk':>10}")
    
    print()
    
    # Top 15 TX
    print("TOP 15 TEXAS:")
    print("-" * 90)
    print(f"{'Name':<45} {'Investments':>15} {'Equity':>10} {'Captive':>10}")
    print("-" * 90)
    for r in tx_results[:15]:
        inv = f"${r.total_cash_investments/1e6:.1f}M" if r.total_cash_investments else "N/A"
        print(f"{r.system_name[:45]:<45} {inv:>15} {r.has_equities or 'unk':>10} {r.has_captive or 'unk':>10}")
    
    print()
    print(f"Results saved to: quick_screen_tx_ca.csv")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
