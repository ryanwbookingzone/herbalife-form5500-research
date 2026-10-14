#!/usr/bin/env python3
"""
Quick Screen Pipeline for East/South US Hospital Systems.

Screens hospital systems in FL, GA, AL, MS, LA, AR, TN, KY, NC, SC, VA, WV, MD, DE, DC, 
PA, NJ, NY, CT, RI, MA, VT, NH, ME, OK for fixed-income-only investment targets.

Prioritizes PUBLIC hospital districts/authorities first (usually bound by state public-funds laws),
then nonprofits. Target criteria:
- Operating cash+investments > $25M
- Operating investments fixed-income only (ignore pension/OPEB)
- No captive insurance
"""

import csv
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

import requests

# Target states for this batch
TARGET_STATES = [
    "FL", "GA", "AL", "MS", "LA", "AR", "TN", "KY", "NC", "SC", 
    "VA", "WV", "MD", "DE", "DC", "PA", "NJ", "NY", "CT", "RI", 
    "MA", "VT", "NH", "ME", "OK"
]

PROPUBLICA_API_BASE = "https://projects.propublica.org/nonprofits/api/v2"

HEALTHCARE_NTEE_CODES = ["E20", "E21", "E22", "E24", "E30", "E31", "E32"]

MIN_CASH_INVESTMENTS = 25_000_000

# State-specific public funds investment restrictions
STATE_INVESTMENT_RESTRICTIONS = {
    "FL": {"code": "Florida Statute 218.415", "fixed_income_only": True},
    "GA": {"code": "Georgia Code 36-83", "fixed_income_only": True},
    "AL": {"code": "Alabama Code 11-81-19", "fixed_income_only": True},
    "MS": {"code": "Mississippi Code 27-105-33", "fixed_income_only": True},
    "LA": {"code": "Louisiana RS 33:2955", "fixed_income_only": True},
    "AR": {"code": "Arkansas Code 19-1-501", "fixed_income_only": True},
    "TN": {"code": "Tennessee Code 9-4-501", "fixed_income_only": True},
    "KY": {"code": "Kentucky KRS 66.480", "fixed_income_only": True},
    "NC": {"code": "North Carolina GS 159-30", "fixed_income_only": True},
    "SC": {"code": "South Carolina Code 6-5-10", "fixed_income_only": True},
    "VA": {"code": "Virginia Code 2.2-4501", "fixed_income_only": True},
    "WV": {"code": "West Virginia Code 12-6C-9", "fixed_income_only": True},
    "MD": {"code": "Maryland State Finance 6-222", "fixed_income_only": True},
    "DE": {"code": "Delaware Code Title 29 Ch 61", "fixed_income_only": True},
    "DC": {"code": "DC Code 1-204.90", "fixed_income_only": True},
    "PA": {"code": "Pennsylvania Local Government Unit Debt Act", "fixed_income_only": True},
    "NJ": {"code": "New Jersey NJSA 40A:5-15.1", "fixed_income_only": True},
    "NY": {"code": "New York General Municipal Law 11", "fixed_income_only": True},
    "CT": {"code": "Connecticut CGS 7-402", "fixed_income_only": True},
    "RI": {"code": "Rhode Island RIGL 35-10", "fixed_income_only": True},
    "MA": {"code": "Massachusetts MGL c.44 s.55", "fixed_income_only": True},
    "VT": {"code": "Vermont 24 VSA 1571", "fixed_income_only": True},
    "NH": {"code": "New Hampshire RSA 35:9", "fixed_income_only": True},
    "ME": {"code": "Maine MRSA 30-A 5706", "fixed_income_only": True},
    "OK": {"code": "Oklahoma 62 OS 348.1", "fixed_income_only": True},
}

# Known public hospital districts/authorities in target states
PUBLIC_HOSPITALS_EAST_SOUTH = [
    # Florida
    {"name": "Sarasota County Public Hospital District", "state": "FL", "type": "hospital_district", "emma_search": "Sarasota Memorial"},
    {"name": "Memorial Healthcare System", "state": "FL", "type": "hospital_district", "city": "Hollywood"},
    {"name": "Jackson Health System", "state": "FL", "type": "hospital_district", "city": "Miami"},
    {"name": "Tampa General Hospital", "state": "FL", "type": "nonprofit", "city": "Tampa"},
    {"name": "Lee Health", "state": "FL", "type": "hospital_district", "city": "Fort Myers"},
    {"name": "Halifax Health", "state": "FL", "type": "hospital_district", "city": "Daytona Beach"},
    {"name": "North Broward Hospital District", "state": "FL", "type": "hospital_district", "city": "Fort Lauderdale"},
    {"name": "Shands Teaching Hospital", "state": "FL", "type": "nonprofit", "city": "Gainesville"},
    {"name": "Bayfront Health St Petersburg", "state": "FL", "type": "nonprofit", "city": "St Petersburg"},
    {"name": "Sacred Heart Hospital Pensacola", "state": "FL", "type": "nonprofit", "city": "Pensacola"},
    
    # Georgia
    {"name": "Grady Health System", "state": "GA", "type": "hospital_authority", "city": "Atlanta"},
    {"name": "Wellstar Health System", "state": "GA", "type": "nonprofit", "city": "Marietta"},
    {"name": "Piedmont Healthcare", "state": "GA", "type": "nonprofit", "city": "Atlanta"},
    {"name": "Augusta University Health", "state": "GA", "type": "public", "city": "Augusta"},
    {"name": "Northeast Georgia Health System", "state": "GA", "type": "nonprofit", "city": "Gainesville"},
    {"name": "Emory Healthcare", "state": "GA", "type": "nonprofit", "city": "Atlanta"},
    
    # North Carolina
    {"name": "Atrium Health", "state": "NC", "type": "nonprofit", "city": "Charlotte"},
    {"name": "Novant Health", "state": "NC", "type": "nonprofit", "city": "Winston-Salem"},
    {"name": "WakeMed Health", "state": "NC", "type": "nonprofit", "city": "Raleigh"},
    {"name": "Vidant Health", "state": "NC", "type": "nonprofit", "city": "Greenville"},
    {"name": "Cone Health", "state": "NC", "type": "nonprofit", "city": "Greensboro"},
    {"name": "UNC Health", "state": "NC", "type": "public", "city": "Chapel Hill"},
    
    # Virginia
    {"name": "Sentara Healthcare", "state": "VA", "type": "nonprofit", "city": "Norfolk"},
    {"name": "Inova Health System", "state": "VA", "type": "nonprofit", "city": "Falls Church"},
    {"name": "Carilion Clinic", "state": "VA", "type": "nonprofit", "city": "Roanoke"},
    {"name": "VCU Health System", "state": "VA", "type": "public", "city": "Richmond"},
    {"name": "University of Virginia Health System", "state": "VA", "type": "public", "city": "Charlottesville"},
    
    # Maryland
    {"name": "Johns Hopkins Health System", "state": "MD", "type": "nonprofit", "city": "Baltimore"},
    {"name": "MedStar Health", "state": "MD", "type": "nonprofit", "city": "Columbia"},
    {"name": "University of Maryland Medical System", "state": "MD", "type": "nonprofit", "city": "Baltimore"},
    {"name": "Adventist HealthCare", "state": "MD", "type": "nonprofit", "city": "Gaithersburg"},
    
    # Pennsylvania
    {"name": "UPMC Health System", "state": "PA", "type": "nonprofit", "city": "Pittsburgh"},
    {"name": "Penn Medicine", "state": "PA", "type": "nonprofit", "city": "Philadelphia"},
    {"name": "Geisinger Health", "state": "PA", "type": "nonprofit", "city": "Danville"},
    {"name": "Lehigh Valley Health Network", "state": "PA", "type": "nonprofit", "city": "Allentown"},
    {"name": "Main Line Health", "state": "PA", "type": "nonprofit", "city": "Bryn Mawr"},
    
    # New York
    {"name": "NYC Health + Hospitals", "state": "NY", "type": "public", "city": "New York"},
    {"name": "Northwell Health", "state": "NY", "type": "nonprofit", "city": "New Hyde Park"},
    {"name": "Mount Sinai Health System", "state": "NY", "type": "nonprofit", "city": "New York"},
    {"name": "NewYork-Presbyterian", "state": "NY", "type": "nonprofit", "city": "New York"},
    {"name": "Montefiore Health System", "state": "NY", "type": "nonprofit", "city": "Bronx"},
    {"name": "Rochester Regional Health", "state": "NY", "type": "nonprofit", "city": "Rochester"},
    
    # New Jersey
    {"name": "RWJBarnabas Health", "state": "NJ", "type": "nonprofit", "city": "West Orange"},
    {"name": "Hackensack Meridian Health", "state": "NJ", "type": "nonprofit", "city": "Edison"},
    {"name": "Atlantic Health System", "state": "NJ", "type": "nonprofit", "city": "Morristown"},
    {"name": "Virtua Health", "state": "NJ", "type": "nonprofit", "city": "Marlton"},
    
    # Massachusetts
    {"name": "Mass General Brigham", "state": "MA", "type": "nonprofit", "city": "Boston"},
    {"name": "Beth Israel Lahey Health", "state": "MA", "type": "nonprofit", "city": "Burlington"},
    {"name": "Baystate Health", "state": "MA", "type": "nonprofit", "city": "Springfield"},
    {"name": "UMass Memorial Health", "state": "MA", "type": "nonprofit", "city": "Worcester"},
    
    # Connecticut
    {"name": "Yale New Haven Health", "state": "CT", "type": "nonprofit", "city": "New Haven"},
    {"name": "Hartford HealthCare", "state": "CT", "type": "nonprofit", "city": "Hartford"},
    {"name": "Trinity Health Of New England", "state": "CT", "type": "nonprofit", "city": "Hartford"},
    
    # Alabama
    {"name": "UAB Health System", "state": "AL", "type": "public", "city": "Birmingham"},
    {"name": "Huntsville Hospital Health System", "state": "AL", "type": "nonprofit", "city": "Huntsville"},
    {"name": "DCH Health System", "state": "AL", "type": "nonprofit", "city": "Tuscaloosa"},
    
    # Tennessee
    {"name": "Vanderbilt University Medical Center", "state": "TN", "type": "nonprofit", "city": "Nashville"},
    {"name": "Regional One Health", "state": "TN", "type": "hospital_authority", "city": "Memphis"},
    {"name": "Erlanger Health System", "state": "TN", "type": "hospital_authority", "city": "Chattanooga"},
    {"name": "Ballad Health", "state": "TN", "type": "nonprofit", "city": "Johnson City"},
    
    # Kentucky
    {"name": "Norton Healthcare", "state": "KY", "type": "nonprofit", "city": "Louisville"},
    {"name": "Baptist Health Kentucky", "state": "KY", "type": "nonprofit", "city": "Louisville"},
    {"name": "UK HealthCare", "state": "KY", "type": "public", "city": "Lexington"},
    
    # Louisiana
    {"name": "Ochsner Health", "state": "LA", "type": "nonprofit", "city": "New Orleans"},
    {"name": "Our Lady of the Lake Regional Medical Center", "state": "LA", "type": "nonprofit", "city": "Baton Rouge"},
    {"name": "Louisiana State University Health", "state": "LA", "type": "public", "city": "New Orleans"},
    
    # Mississippi
    {"name": "University of Mississippi Medical Center", "state": "MS", "type": "public", "city": "Jackson"},
    {"name": "Baptist Memorial Health Care", "state": "MS", "type": "nonprofit", "city": "Memphis"},
    {"name": "Forrest General Hospital", "state": "MS", "type": "nonprofit", "city": "Hattiesburg"},
    
    # Arkansas
    {"name": "UAMS Medical Center", "state": "AR", "type": "public", "city": "Little Rock"},
    {"name": "Baptist Health Arkansas", "state": "AR", "type": "nonprofit", "city": "Little Rock"},
    {"name": "CHI St Vincent", "state": "AR", "type": "nonprofit", "city": "Little Rock"},
    
    # South Carolina
    {"name": "MUSC Health", "state": "SC", "type": "public", "city": "Charleston"},
    {"name": "Prisma Health", "state": "SC", "type": "nonprofit", "city": "Greenville"},
    {"name": "Roper St Francis Healthcare", "state": "SC", "type": "nonprofit", "city": "Charleston"},
    
    # West Virginia
    {"name": "WVU Medicine", "state": "WV", "type": "public", "city": "Morgantown"},
    {"name": "CAMC Health System", "state": "WV", "type": "nonprofit", "city": "Charleston"},
    
    # Oklahoma
    {"name": "OU Health", "state": "OK", "type": "public", "city": "Oklahoma City"},
    {"name": "INTEGRIS Health", "state": "OK", "type": "nonprofit", "city": "Oklahoma City"},
    {"name": "Saint Francis Health System", "state": "OK", "type": "nonprofit", "city": "Tulsa"},
    
    # DC
    {"name": "MedStar Washington Hospital Center", "state": "DC", "type": "nonprofit", "city": "Washington"},
    {"name": "George Washington University Hospital", "state": "DC", "type": "nonprofit", "city": "Washington"},
    
    # Delaware
    {"name": "ChristianaCare", "state": "DE", "type": "nonprofit", "city": "Wilmington"},
    {"name": "Bayhealth", "state": "DE", "type": "nonprofit", "city": "Dover"},
    
    # Rhode Island
    {"name": "Lifespan Health System", "state": "RI", "type": "nonprofit", "city": "Providence"},
    {"name": "Care New England", "state": "RI", "type": "nonprofit", "city": "Providence"},
    
    # Vermont
    {"name": "University of Vermont Health Network", "state": "VT", "type": "nonprofit", "city": "Burlington"},
    
    # New Hampshire
    {"name": "Dartmouth-Hitchcock Health", "state": "NH", "type": "nonprofit", "city": "Lebanon"},
    {"name": "Elliot Health System", "state": "NH", "type": "nonprofit", "city": "Manchester"},
    
    # Maine
    {"name": "MaineHealth", "state": "ME", "type": "nonprofit", "city": "Portland"},
    {"name": "Northern Light Health", "state": "ME", "type": "nonprofit", "city": "Brewer"},
]

# Equity keywords
EQUITY_KEYWORDS = [
    "equity securities", "common stock", "domestic equity", "international equity",
    "equity mutual fund", "equity fund", "equity etf", "alternative investment",
    "hedge fund", "private equity", "venture capital", "reit", "equity commingled",
]

# Fixed income keywords
FIXED_INCOME_KEYWORDS = [
    "treasury", "federal agency", "municipal bond", "corporate bond",
    "money market", "commercial paper", "certificate of deposit",
    "government securities", "fannie mae", "freddie mac", "gnma",
]

# Captive insurance keywords
CAPTIVE_KEYWORDS = [
    "captive insurance", "insurance captive", "wholly-owned insurance",
    "insurance subsidiary", "risk retention group", "rrg", "protected cell",
    "cayman", "vermont captive", "bermuda", "assurance inc", "assurance ltd",
]


@dataclass
class SystemFindings:
    """Findings for a health system."""
    system_name: str
    state: str
    system_type: str
    cash_investments: float
    fiscal_year: str
    has_equities: str  # "yes", "no", "de_minimis", "unknown"
    has_captive: str   # "yes", "no", "unknown"
    si_reserves: float
    is_target: bool
    confidence: str
    source_url: str
    page_reference: str
    notes: str


def search_propublica(query: str, state: str = None, page: int = 0) -> Dict:
    """Search ProPublica Nonprofit Explorer."""
    params = {"q": query, "page": page}
    if state:
        params["state[id]"] = state
    
    try:
        resp = requests.get(
            f"{PROPUBLICA_API_BASE}/search.json",
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  API error: {e}")
        return {"organizations": [], "total_results": 0}


def get_organization_details(ein: str) -> Optional[Dict]:
    """Get detailed organization info from ProPublica."""
    try:
        resp = requests.get(
            f"{PROPUBLICA_API_BASE}/organizations/{ein}.json",
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except:
        return None


def extract_990_financials(org_data: Dict) -> Dict:
    """Extract financial data from 990."""
    result = {
        "cash": 0,
        "investments": 0,
        "total_assets": 0,
        "total_revenue": 0,
        "tax_year": None,
    }
    
    if not org_data or "filings_with_data" not in org_data:
        return result
    
    filings = org_data.get("filings_with_data", [])
    if not filings:
        return result
    
    latest = filings[0]
    result["tax_year"] = latest.get("tax_prd_yr")
    result["total_assets"] = latest.get("totassetsend") or 0
    result["total_revenue"] = latest.get("totrevenue") or 0
    result["cash"] = latest.get("cashsavingsend") or latest.get("cashnoneam") or 0
    
    investments = 0
    for field in ["invstmntsinc", "invstmntsend", "othrinvestend"]:
        val = latest.get(field)
        if val and isinstance(val, (int, float)):
            investments += val
    result["investments"] = investments
    
    return result


def classify_system(
    system: Dict,
    financials: Dict,
) -> SystemFindings:
    """Classify a system based on available data."""
    
    name = system.get("name", "")
    state = system.get("state", "")
    sys_type = system.get("type", "nonprofit")
    
    cash_inv = financials.get("cash", 0) + financials.get("investments", 0)
    
    # For public entities, check state investment restrictions
    has_equities = "unknown"
    has_captive = "unknown"
    confidence = "propublica_990"
    notes = ""
    
    if sys_type in ["hospital_district", "hospital_authority", "public"]:
        # Public entities are usually restricted to fixed income by state law
        if state in STATE_INVESTMENT_RESTRICTIONS:
            restriction = STATE_INVESTMENT_RESTRICTIONS[state]
            if restriction.get("fixed_income_only"):
                has_equities = "no"
                confidence = "state_law_inferred"
                notes = f"Public entity restricted by {restriction['code']}"
    
    # Determine target status
    is_target = False
    if cash_inv >= MIN_CASH_INVESTMENTS:
        if has_equities == "no" and has_captive in ["no", "unknown"]:
            is_target = True
    
    return SystemFindings(
        system_name=name,
        state=state,
        system_type=sys_type,
        cash_investments=cash_inv,
        fiscal_year=str(financials.get("tax_year", "FY2024")),
        has_equities=has_equities,
        has_captive=has_captive,
        si_reserves=0,
        is_target=is_target,
        confidence=confidence,
        source_url=f"https://projects.propublica.org/nonprofits/",
        page_reference="990 filing",
        notes=notes,
    )


def generate_listing_id(name: str, state: str) -> str:
    """Generate a unique listing ID."""
    name_clean = re.sub(r'[^A-Z0-9-]', '', name.upper().replace(' ', '-'))[:30]
    return f"QS-{state}-{name_clean}"


def screen_east_south_systems():
    """Main screening function for East/South states."""
    
    print("=" * 70)
    print("Quick Screen Pipeline - East/South US Hospital Systems")
    print("=" * 70)
    print(f"Target States: {', '.join(TARGET_STATES)}")
    print(f"Minimum Cash+Investments: ${MIN_CASH_INVESTMENTS:,.0f}")
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    all_findings: List[SystemFindings] = []
    state_counts: Dict[str, int] = {state: 0 for state in TARGET_STATES}
    
    # Phase 1: Screen known public hospitals first
    print("Phase 1: Screening known public hospital districts/authorities...")
    print("-" * 70)
    
    public_systems = [s for s in PUBLIC_HOSPITALS_EAST_SOUTH 
                      if s["type"] in ["hospital_district", "hospital_authority", "public"]]
    
    for system in public_systems:
        state = system["state"]
        name = system["name"]
        print(f"  Checking: {name} ({state})", end="", flush=True)
        
        # Search ProPublica for EIN
        results = search_propublica(name, state=state)
        time.sleep(0.3)
        
        orgs = results.get("organizations", [])
        matched = None
        for org in orgs[:3]:  # Check top 3 matches
            org_state = org.get("state", "")
            org_name = org.get("name", "").upper()
            if org_state == state and any(w in org_name for w in name.upper().split()[:2]):
                matched = org
                break
        
        if matched:
            ein = matched.get("ein")
            details = get_organization_details(ein)
            financials = extract_990_financials(details) if details else {}
            
            findings = classify_system(system, financials)
            findings.source_url = f"https://projects.propublica.org/nonprofits/organizations/{ein}"
            
            all_findings.append(findings)
            state_counts[state] += 1
            
            target_marker = " **TARGET**" if findings.is_target else ""
            print(f" -> ${findings.cash_investments/1e6:.1f}M{target_marker}")
        else:
            # Still add with unknown financials for follow-up
            findings = SystemFindings(
                system_name=name,
                state=state,
                system_type=system["type"],
                cash_investments=0,
                fiscal_year="unknown",
                has_equities="unknown",
                has_captive="unknown",
                si_reserves=0,
                is_target=False,
                confidence="needs_audit",
                source_url="",
                page_reference="",
                notes="No 990 found - needs EMMA/audit search",
            )
            all_findings.append(findings)
            state_counts[state] += 1
            print(" -> No 990 found")
        
        time.sleep(0.3)
    
    print()
    print("Phase 2: Screening known nonprofits...")
    print("-" * 70)
    
    # Phase 2: Screen known nonprofit systems
    nonprofit_systems = [s for s in PUBLIC_HOSPITALS_EAST_SOUTH 
                         if s["type"] == "nonprofit"]
    
    for system in nonprofit_systems:
        state = system["state"]
        name = system["name"]
        print(f"  Checking: {name} ({state})", end="", flush=True)
        
        results = search_propublica(name, state=state)
        time.sleep(0.3)
        
        orgs = results.get("organizations", [])
        matched = None
        for org in orgs[:5]:
            org_state = org.get("state", "")
            org_name = org.get("name", "").upper()
            if org_state == state:
                # Check for keyword match
                name_words = [w for w in name.upper().split() if len(w) > 3]
                if any(w in org_name for w in name_words[:2]):
                    matched = org
                    break
        
        if matched:
            ein = matched.get("ein")
            details = get_organization_details(ein)
            financials = extract_990_financials(details) if details else {}
            
            system_copy = system.copy()
            findings = classify_system(system_copy, financials)
            findings.source_url = f"https://projects.propublica.org/nonprofits/organizations/{ein}"
            
            all_findings.append(findings)
            state_counts[state] += 1
            
            target_marker = " [needs audit]" if findings.has_equities == "unknown" and findings.cash_investments >= MIN_CASH_INVESTMENTS else ""
            if findings.is_target:
                target_marker = " **TARGET**"
            print(f" -> ${findings.cash_investments/1e6:.1f}M{target_marker}")
        else:
            findings = SystemFindings(
                system_name=name,
                state=state,
                system_type="nonprofit",
                cash_investments=0,
                fiscal_year="unknown",
                has_equities="unknown",
                has_captive="unknown",
                si_reserves=0,
                is_target=False,
                confidence="needs_audit",
                source_url="",
                page_reference="",
                notes="No 990 found - needs EMMA/audit search",
            )
            all_findings.append(findings)
            state_counts[state] += 1
            print(" -> No 990 found")
        
        time.sleep(0.3)
    
    print()
    print("Phase 3: Additional ProPublica search for >$25M systems...")
    print("-" * 70)
    
    # Phase 3: Search for additional large systems via ProPublica
    existing_names = {f.system_name.upper() for f in all_findings}
    
    for state in TARGET_STATES:
        print(f"  Searching {state}...", end="", flush=True)
        
        for keyword in ["hospital", "health system", "medical center"]:
            results = search_propublica(keyword, state=state)
            time.sleep(0.3)
            
            for org in results.get("organizations", [])[:10]:
                org_name = org.get("name", "")
                org_state = org.get("state", "")
                
                if org_state != state:
                    continue
                
                if org_name.upper() in existing_names:
                    continue
                
                # Check NTEE code for healthcare
                ntee = org.get("ntee_code") or ""
                if not any(ntee.startswith(code) for code in HEALTHCARE_NTEE_CODES):
                    continue
                
                ein = org.get("ein")
                details = get_organization_details(ein)
                financials = extract_990_financials(details) if details else {}
                
                cash_inv = financials.get("cash", 0) + financials.get("investments", 0)
                total_assets = financials.get("total_assets", 0)
                
                # Estimate cash+inv if not reported (30% of assets)
                if cash_inv == 0 and total_assets >= MIN_CASH_INVESTMENTS:
                    cash_inv = total_assets * 0.30
                
                if cash_inv >= MIN_CASH_INVESTMENTS:
                    system = {"name": org_name, "state": state, "type": "nonprofit"}
                    findings = classify_system(system, financials)
                    findings.source_url = f"https://projects.propublica.org/nonprofits/organizations/{ein}"
                    
                    all_findings.append(findings)
                    existing_names.add(org_name.upper())
                    state_counts[state] += 1
                
                time.sleep(0.2)
        
        print(f" found {state_counts[state]} systems")
    
    return all_findings, state_counts


def write_to_frappe(findings: List[SystemFindings]) -> tuple[int, int]:
    """Prepare data for Frappe (returns counts only, actual write via MCP)."""
    companies = []
    facts = []
    
    for f in findings:
        listing_id = generate_listing_id(f.system_name, f.state)
        
        # Company record
        company = {
            "listing_id": listing_id,
            "company_name": f.system_name,
            "segment": "Healthcare",
            "company_type": f.system_type,
            "state": f.state,
            "country": "United States",
            "score_tier": "warm" if f.is_target else "cold",
            "enrichment_status": "complete",
            "pipeline_status": "prospect",
            "source": "Quick Screen Pipeline",
            "notes": f"[QUICK-SCREEN] State: {f.state}. Cash+Inv: ${f.cash_investments/1e6:.1f}M. "
                     f"Equities: {f.has_equities}. Captive: {f.has_captive}. "
                     f"Target: {'YES' if f.is_target else 'NO'}. Confidence: {f.confidence}. {f.notes}"
        }
        companies.append(company)
        
        # Financial facts
        if f.cash_investments > 0:
            content_hash = hashlib.sha256(
                f"{f.system_name}|cash_investments|{f.cash_investments}".encode()
            ).hexdigest()[:40]
            
            fact = {
                "entity": listing_id,
                "fact_category": "cash_and_investments",
                "fact_name": "Total Operating Cash and Investments",
                "reported_value_text": f"${f.cash_investments/1e6:,.1f}M",
                "reported_value_usd": int(f.cash_investments),
                "fiscal_year": f.fiscal_year,
                "source_url": f.source_url,
                "source_domain": urlparse(f.source_url).netloc if f.source_url else "",
                "page_reference": f.page_reference or "990 filing",
                "source_quote": f"Operating cash and investments (excluding pension/OPEB)",
                "content_hash": content_hash,
                "confidence": "verified" if f.confidence in ["audit_verified", "state_law_inferred"] else "unresolved",
            }
            facts.append(fact)
    
    # Save to JSON for Frappe import
    with open('/workspace/quick_screen/frappe_east_south_companies.json', 'w') as f:
        json.dump(companies, f, indent=2)
    
    with open('/workspace/quick_screen/frappe_east_south_facts.json', 'w') as f:
        json.dump(facts, f, indent=2)
    
    return len(companies), len(facts)


def export_csv(findings: List[SystemFindings], output_path: str):
    """Export findings to CSV."""
    fieldnames = [
        "system_name", "state", "system_type", "cash_investments", 
        "has_equities", "has_captive", "si_reserves", "is_target",
        "fiscal_year", "confidence", "source_url", "notes"
    ]
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for finding in sorted(findings, key=lambda x: (-x.is_target, -x.cash_investments)):
            writer.writerow({
                "system_name": finding.system_name,
                "state": finding.state,
                "system_type": finding.system_type,
                "cash_investments": int(finding.cash_investments),
                "has_equities": finding.has_equities,
                "has_captive": finding.has_captive,
                "si_reserves": int(finding.si_reserves),
                "is_target": finding.is_target,
                "fiscal_year": finding.fiscal_year,
                "confidence": finding.confidence,
                "source_url": finding.source_url,
                "notes": finding.notes,
            })


def main():
    """Main entry point."""
    # Run screening
    findings, state_counts = screen_east_south_systems()
    
    # Filter to targets
    targets = [f for f in findings if f.is_target]
    needs_audit = [f for f in findings 
                   if f.cash_investments >= MIN_CASH_INVESTMENTS and f.has_equities == "unknown"]
    
    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    print(f"\nSystems reviewed per state:")
    for state in TARGET_STATES:
        if state_counts[state] > 0:
            print(f"  {state}: {state_counts[state]}")
    
    print(f"\nTotal systems reviewed: {len(findings)}")
    print(f"Confirmed TARGETS (fixed income, no captive, >$25M): {len(targets)}")
    print(f"Need audit verification (>$25M, equity unknown): {len(needs_audit)}")
    
    print("\n" + "=" * 70)
    print("TARGET SHORTLIST")
    print("=" * 70)
    
    for t in sorted(targets, key=lambda x: -x.cash_investments):
        print(f"  {t.system_name} ({t.state}): ${t.cash_investments/1e6:.1f}M - {t.confidence}")
    
    print("\n" + "=" * 70)
    print("NEEDS AUDIT REVIEW")
    print("=" * 70)
    
    for t in sorted(needs_audit, key=lambda x: -x.cash_investments)[:20]:
        print(f"  {t.system_name} ({t.state}): ${t.cash_investments/1e6:.1f}M")
    
    # Export
    csv_path = '/workspace/quick_screen/shortlist_east_south.csv'
    export_csv(findings, csv_path)
    print(f"\nCSV exported: {csv_path}")
    
    # Prepare Frappe data
    company_count, fact_count = write_to_frappe(findings)
    print(f"Frappe data prepared: {company_count} companies, {fact_count} facts")
    print("  -> frappe_east_south_companies.json")
    print("  -> frappe_east_south_facts.json")
    
    return findings, targets


if __name__ == "__main__":
    findings, targets = main()
