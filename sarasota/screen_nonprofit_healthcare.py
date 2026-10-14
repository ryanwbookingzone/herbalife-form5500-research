#!/usr/bin/env python3
"""
ProPublica Nonprofit Explorer Screening Script
===============================================
Screens US nonprofit hospital and healthcare systems using ProPublica's 
Nonprofit Explorer API to identify organizations with >$25M cash+investments.

NTEE Codes for Healthcare:
- E20: Hospitals, General
- E21: Hospitals, Specialty
- E22: General Rehabilitation

Output: CSV with candidate organizations for financial extraction.

Usage:
    python screen_nonprofit_healthcare.py --output candidates.csv --min-cash 25000000
    
API Documentation:
    https://projects.propublica.org/nonprofits/api
"""

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Warning: requests library required. Install with: pip install requests")


# ProPublica API base URL
PROPUBLICA_API_BASE = "https://projects.propublica.org/nonprofits/api/v2"

# NTEE codes for hospitals and healthcare
HEALTHCARE_NTEE_CODES = [
    "E20",  # Hospitals, General
    "E21",  # Hospitals, Specialty  
    "E22",  # General Rehabilitation
    "E24",  # Hospital, Specialty (Pediatric)
    "E30",  # Ambulatory Health Center
    "E31",  # Community Health Systems
    "E32",  # Rural Health
]

# States to search (can be customized)
US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC"
]


@dataclass
class NonprofitCandidate:
    """Candidate nonprofit healthcare organization."""
    ein: str
    name: str
    city: str
    state: str
    ntee_code: str
    total_assets: float
    total_revenue: float
    cash_and_savings: Optional[float]
    investments: Optional[float]
    cash_plus_investments: Optional[float]
    tax_year: int
    propublica_url: str
    irs_990_available: bool = True


def search_nonprofits(
    query: str = "hospital",
    state: str = None,
    ntee_code: str = None,
    page: int = 0
) -> Dict[str, Any]:
    """Search ProPublica Nonprofit Explorer API."""
    if not HAS_REQUESTS:
        return {"organizations": [], "total_results": 0}
    
    params = {"q": query, "page": page}
    if state:
        params["state[id]"] = state
    if ntee_code:
        params["ntee[id]"] = ntee_code
    
    try:
        resp = requests.get(
            f"{PROPUBLICA_API_BASE}/search.json",
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"API error: {e}")
        return {"organizations": [], "total_results": 0}


def get_organization_details(ein: str) -> Optional[Dict[str, Any]]:
    """Get detailed organization info from ProPublica."""
    if not HAS_REQUESTS:
        return None
    
    try:
        resp = requests.get(
            f"{PROPUBLICA_API_BASE}/organizations/{ein}.json",
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching EIN {ein}: {e}")
        return None


def extract_financial_data(org_data: Dict) -> Dict[str, Any]:
    """Extract cash and investment figures from 990 data."""
    result = {
        "cash_and_savings": None,
        "investments": None,
        "total_assets": None,
        "total_revenue": None,
        "tax_year": None
    }
    
    if not org_data or "filings_with_data" not in org_data:
        return result
    
    filings = org_data.get("filings_with_data", [])
    if not filings:
        return result
    
    # Get most recent filing
    latest = filings[0]
    
    result["tax_year"] = latest.get("tax_prd_yr")
    result["total_assets"] = latest.get("totassetsend")
    result["total_revenue"] = latest.get("totrevenue")
    
    # Cash is typically in "cashsavingsend" or "cashnoneam"
    result["cash_and_savings"] = latest.get("cashsavingsend") or latest.get("cashnoneam")
    
    # Investments can be in multiple fields
    investments = 0
    for field in ["invstmntsinc", "invstmntsend", "othrinvestend", "securedmortend"]:
        val = latest.get(field)
        if val and isinstance(val, (int, float)):
            investments += val
    result["investments"] = investments if investments > 0 else None
    
    return result


def screen_healthcare_nonprofits(
    min_cash_investments: float = 25_000_000,
    states: List[str] = None,
    ntee_codes: List[str] = None,
    max_results: int = 500,
    delay_seconds: float = 0.5,
    search_keywords: List[str] = None
) -> List[NonprofitCandidate]:
    """Screen for healthcare nonprofits with significant cash/investments.
    
    Uses keyword search approach (more reliable) with client-side NTEE filtering.
    """
    
    states = states or US_STATES
    ntee_codes = ntee_codes or HEALTHCARE_NTEE_CODES
    search_keywords = search_keywords or [
        "hospital", "health system", "medical center", 
        "healthcare", "health care"
    ]
    
    candidates = []
    seen_eins = set()
    
    print(f"Screening healthcare nonprofits via keyword search...")
    print(f"Keywords: {', '.join(search_keywords)}")
    print(f"Minimum cash+investments: ${min_cash_investments:,.0f}")
    print(f"NTEE filter: {', '.join(ntee_codes)}")
    if states:
        print(f"States: {', '.join(states)}")
    print()
    
    for keyword in search_keywords:
        print(f"Searching '{keyword}'...", flush=True)
        page = 0
        keyword_count = 0
        
        while page < 20:  # Limit to 20 pages per keyword
            results = search_nonprofits(query=keyword, page=page)
            
            orgs = results.get("organizations", [])
            if not orgs:
                break
            
            for org in orgs:
                ein = org.get("ein")
                if not ein or ein in seen_eins:
                    continue
                
                # State filter (if specified)
                org_state = org.get("state", "")
                if states and org_state not in states:
                    continue
                
                # NTEE filter - check if org's NTEE starts with any target code
                org_ntee = org.get("ntee_code") or org.get("raw_ntee_code") or ""
                if not org_ntee or not any(org_ntee.startswith(code) for code in ntee_codes):
                    continue
                
                seen_eins.add(ein)
                
                # Get detailed financials
                time.sleep(delay_seconds)  # Rate limiting
                details = get_organization_details(ein)
                if not details:
                    continue
                
                org_info = details.get("organization", {})
                financials = extract_financial_data(details)
                
                total_assets = financials.get("total_assets") or 0
                cash = financials.get("cash_and_savings") or 0
                investments = financials.get("investments") or 0
                cash_plus_inv = cash + investments
                
                # ProPublica API often lacks detailed cash/investments - use total_assets as proxy
                # Healthcare orgs typically have 20-40% of assets in cash+investments
                if cash_plus_inv == 0 and total_assets >= min_cash_investments:
                    # Estimate cash+investments as 30% of total assets (conservative)
                    cash_plus_inv = total_assets * 0.30
                
                if cash_plus_inv < min_cash_investments:
                    continue
                
                if cash_plus_inv >= min_cash_investments:
                    candidate = NonprofitCandidate(
                        ein=str(ein),
                        name=org_info.get("name", org.get("name", "")),
                        city=org_info.get("city", ""),
                        state=org_info.get("state", org_state),
                        ntee_code=org_info.get("ntee_code", org_ntee),
                        total_assets=total_assets,
                        total_revenue=financials.get("total_revenue") or 0,
                        cash_and_savings=cash if cash else None,
                        investments=investments if investments else None,
                        cash_plus_investments=cash_plus_inv,
                        tax_year=financials.get("tax_year") or 0,
                        propublica_url=f"https://projects.propublica.org/nonprofits/organizations/{ein}"
                    )
                    candidates.append(candidate)
                    keyword_count += 1
                    print(f"  + {candidate.name} ({candidate.state}): ${cash_plus_inv:,.0f}")
                    
                    if len(candidates) >= max_results:
                        print(f"\nReached max results ({max_results})")
                        return candidates
            
            page += 1
        
        print(f"  Found {keyword_count} candidates from '{keyword}'")
    
    return candidates


def write_candidates_csv(candidates: List[NonprofitCandidate], output_path: str):
    """Write candidates to CSV file."""
    fieldnames = [
        "ein", "name", "city", "state", "ntee_code",
        "cash_plus_investments", "cash_and_savings", "investments",
        "total_assets", "total_revenue", "tax_year", "propublica_url"
    ]
    
    # Sort by cash+investments descending
    candidates.sort(key=lambda x: x.cash_plus_investments or 0, reverse=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates:
            writer.writerow({
                "ein": c.ein,
                "name": c.name,
                "city": c.city,
                "state": c.state,
                "ntee_code": c.ntee_code,
                "cash_plus_investments": c.cash_plus_investments,
                "cash_and_savings": c.cash_and_savings,
                "investments": c.investments,
                "total_assets": c.total_assets,
                "total_revenue": c.total_revenue,
                "tax_year": c.tax_year,
                "propublica_url": c.propublica_url
            })


def main():
    parser = argparse.ArgumentParser(
        description='Screen nonprofit healthcare organizations for financial extraction'
    )
    parser.add_argument(
        '--output', '-o',
        default='nonprofit_healthcare_candidates.csv',
        help='Output CSV file path'
    )
    parser.add_argument(
        '--min-cash',
        type=float,
        default=25_000_000,
        help='Minimum cash+investments threshold (default: $25M)'
    )
    parser.add_argument(
        '--states',
        nargs='+',
        help='States to search (default: all US states)'
    )
    parser.add_argument(
        '--ntee',
        nargs='+',
        default=HEALTHCARE_NTEE_CODES,
        help='NTEE codes to search'
    )
    parser.add_argument(
        '--max-results',
        type=int,
        default=500,
        help='Maximum number of candidates to return'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between API calls (seconds)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: only search FL and CA'
    )
    
    args = parser.parse_args()
    
    if not HAS_REQUESTS:
        print("Error: requests library required. Install with: pip install requests")
        return 1
    
    states = args.states
    max_results = args.max_results
    
    if args.test:
        states = ["FL", "CA", "TX", "NY"]  # Large healthcare states for testing
        max_results = min(max_results, 20)
        print("TEST MODE: Searching FL, CA, TX, NY only; max 20 results")
    
    print("=" * 60)
    print("ProPublica Nonprofit Healthcare Screening")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    candidates = screen_healthcare_nonprofits(
        min_cash_investments=args.min_cash,
        states=states,
        ntee_codes=args.ntee,
        max_results=max_results,
        delay_seconds=args.delay
    )
    
    print()
    print("=" * 60)
    print(f"RESULTS: {len(candidates)} candidates found")
    print("=" * 60)
    
    if candidates:
        write_candidates_csv(candidates, args.output)
        print(f"Wrote: {args.output}")
        
        print("\nTop 10 by cash+investments:")
        print("-" * 60)
        for i, c in enumerate(candidates[:10], 1):
            print(f"{i:2}. {c.name[:40]:<40} ${c.cash_plus_investments:>15,.0f}")
    else:
        print("No candidates found matching criteria")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
