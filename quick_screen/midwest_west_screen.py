#!/usr/bin/env python3
"""
Quick Screen Pipeline for Midwest/West US Hospital Systems.

Target criteria:
- Operating cash+investments > $25M
- Operating investments fixed-income only (ignore pension/OPEB)
- No captive insurance

States: OH, MI, IN, IL, WI, MN, IA, MO, KS, NE, SD, ND, CO, NM, AZ, UT, NV, ID, MT, WY, WA, OR, AK, HI

Priority:
1. PUBLIC hospital districts/authorities/county hospitals (most likely fixed-income-only per state law)
2. Nonprofits
"""

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Target states
TARGET_STATES = [
    "OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "KS", "NE", "SD", "ND",
    "CO", "NM", "AZ", "UT", "NV", "ID", "MT", "WY", "WA", "OR", "AK", "HI"
]

# State investment restriction laws (PUBLIC entities only)
STATE_PUBLIC_FUNDS_LAWS = {
    "WA": {
        "code": "RCW 39.59 - Public Funds Investment Act",
        "fixed_income_only": True,
        "applies_to": "public_hospital_districts",
        "notes": "WA Public Hospital Districts governed by RCW 70.44"
    },
    "OR": {
        "code": "ORS 294.035 - Local Government Investment Pool",
        "fixed_income_only": True,
        "applies_to": "public_entities",
        "notes": "LGIP and OSTF authorized investments"
    },
    "AZ": {
        "code": "ARS 35-323 - Investment of Public Money",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "County hospital districts follow county treasurer rules"
    },
    "NV": {
        "code": "NRS 355.170 - Investment of Public Money",
        "fixed_income_only": True,
        "applies_to": "local_governments",
        "notes": "County hospitals invest through county treasurer"
    },
    "CO": {
        "code": "CRS 24-75-601 - Public Funds Investment",
        "fixed_income_only": True,
        "applies_to": "special_districts",
        "notes": "Hospital districts are special districts"
    },
    "KS": {
        "code": "KSA 12-1675 - Investment of Municipal Funds",
        "fixed_income_only": True,
        "applies_to": "county_hospitals",
        "notes": "County hospitals use county investment pools"
    },
    "NE": {
        "code": "Neb. Rev. Stat. 77-2315 - Public Funds Investment",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "Hospital districts invest through NACO pool"
    },
    "IA": {
        "code": "Iowa Code 12B - Public Funds Investment",
        "fixed_income_only": True,
        "applies_to": "county_hospitals",
        "notes": "County hospitals governed by Chapter 347A"
    },
    "MN": {
        "code": "Minn. Stat. 118A - Investment of Local Public Funds",
        "fixed_income_only": True,
        "applies_to": "hospital_districts",
        "notes": "4M Fund and state pool authorized"
    },
    "WI": {
        "code": "Wis. Stat. 66.0603 - Investment of Municipal Funds",
        "fixed_income_only": True,
        "applies_to": "local_governments",
        "notes": "LGIP authorized investment"
    },
    "IL": {
        "code": "30 ILCS 235 - Public Funds Investment Act",
        "fixed_income_only": True,
        "applies_to": "public_entities",
        "notes": "Illinois Funds pool authorized"
    },
    "OH": {
        "code": "ORC 135.14 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "subdivisions",
        "notes": "STAR Ohio authorized for hospitals"
    },
    "MI": {
        "code": "MCL 129.91 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "public_bodies",
        "notes": "County hospitals through county treasurer"
    },
    "IN": {
        "code": "IC 5-13 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "County hospitals governed by IC 16-22"
    },
    "MO": {
        "code": "RSMo 30.950 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "County hospitals through MOSIP"
    },
    "SD": {
        "code": "SDCL 4-5 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "All state investments managed by state"
    },
    "ND": {
        "code": "NDCC 21-06 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "State investment board manages pools"
    },
    "MT": {
        "code": "MCA 7-6-2 - Investment of Local Funds",
        "fixed_income_only": True,
        "applies_to": "local_governments",
        "notes": "STIP available for local governments"
    },
    "WY": {
        "code": "WS 9-4-831 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "County hospitals through county treasurer"
    },
    "ID": {
        "code": "Idaho Code 67-1210 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "State pool authorized for hospital districts"
    },
    "UT": {
        "code": "UCA 51-7 - State Money Management Act",
        "fixed_income_only": True,
        "applies_to": "public_entities",
        "notes": "PTIF pool for public hospitals"
    },
    "NM": {
        "code": "NMSA 6-10 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "political_subdivisions",
        "notes": "State investment council rules"
    },
    "AK": {
        "code": "AS 37.10.071 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "municipalities",
        "notes": "Municipal hospitals through state treasury"
    },
    "HI": {
        "code": "HRS 36-21 - Investment of Public Funds",
        "fixed_income_only": True,
        "applies_to": "state_entities",
        "notes": "Hawaii Health Systems Corp state-managed"
    },
}

# Known large public hospital systems in target states (priority research)
KNOWN_PUBLIC_SYSTEMS = {
    # Washington Public Hospital Districts
    "WA": [
        {"name": "Harborview Medical Center", "type": "county", "county": "King", "notes": "King County hospital, UW managed"},
        {"name": "MultiCare Health System", "type": "nonprofit", "notes": "Tacoma-based nonprofit"},
        {"name": "Grays Harbor Community Hospital", "type": "phd", "district": "PHD #2"},
        {"name": "Whidbey Health", "type": "phd", "district": "Whidbey Island PHD"},
        {"name": "Olympic Medical Center", "type": "phd", "district": "Clallam County PHD #2"},
        {"name": "Samaritan Healthcare", "type": "phd", "district": "Grant County PHD #1"},
        {"name": "Columbia Basin Hospital", "type": "phd", "district": "Grant County PHD #2"},
        {"name": "Lourdes Health", "type": "phd", "district": "Pasco PHD"},
        {"name": "Confluence Health", "type": "phd", "district": "Chelan-Douglas PHD"},
        {"name": "Kadlec Regional Medical Center", "type": "nonprofit", "notes": "Providence subsidiary"},
        {"name": "Prosser Memorial Health", "type": "phd", "district": "Benton County PHD"},
        {"name": "Astria Health", "type": "phd", "district": "Yakima Valley"},
    ],
    # Oregon
    "OR": [
        {"name": "Oregon Health & Science University", "type": "state", "notes": "State university hospital"},
        {"name": "Salem Health", "type": "nonprofit", "notes": "Nonprofit system"},
        {"name": "Asante", "type": "nonprofit", "notes": "Southern Oregon nonprofit"},
        {"name": "Sky Lakes Medical Center", "type": "nonprofit", "district": "Klamath"},
        {"name": "Lake Health District", "type": "district", "district": "Lake County"},
        {"name": "Harney District Hospital", "type": "district", "district": "Harney County"},
        {"name": "Morrow County Health District", "type": "district", "district": "Morrow County"},
    ],
    # Arizona
    "AZ": [
        {"name": "Maricopa Integrated Health System", "type": "county", "county": "Maricopa", "notes": "Valleywise Health"},
        {"name": "Pima County Health Department", "type": "county", "county": "Pima"},
        {"name": "Yuma Regional Medical Center", "type": "district", "district": "Yuma County"},
        {"name": "Copper Queen Community Hospital", "type": "district", "district": "Cochise County"},
        {"name": "Cobre Valley Regional Medical Center", "type": "district", "district": "Gila County"},
        {"name": "Page Hospital", "type": "district", "district": "Coconino County"},
    ],
    # Nevada
    "NV": [
        {"name": "University Medical Center of Southern Nevada", "type": "county", "county": "Clark", "notes": "UMC Las Vegas"},
        {"name": "Washoe County Health District", "type": "county", "county": "Washoe"},
        {"name": "Carson Tahoe Health", "type": "nonprofit", "notes": "Carson City"},
        {"name": "Northern Nevada Medical Center", "type": "nonprofit"},
        {"name": "Humboldt General Hospital", "type": "district", "district": "Humboldt County"},
        {"name": "Pershing General Hospital", "type": "district", "district": "Pershing County"},
        {"name": "William Bee Ririe Hospital", "type": "district", "district": "White Pine County"},
        {"name": "Battle Mountain General Hospital", "type": "district", "district": "Lander County"},
        {"name": "Grover C. Dils Medical Center", "type": "district", "district": "Mineral County"},
    ],
    # Colorado
    "CO": [
        {"name": "Denver Health", "type": "authority", "notes": "Denver Health & Hospital Authority"},
        {"name": "UCHealth", "type": "nonprofit", "notes": "University of Colorado Health"},
        {"name": "Centura Health", "type": "nonprofit", "notes": "CommonSpirit/AdventHealth JV - likely has equities"},
        {"name": "San Luis Valley Health", "type": "district", "district": "Alamosa"},
        {"name": "Montrose Memorial Hospital", "type": "district", "district": "Montrose"},
        {"name": "Southwest Health System", "type": "district", "district": "Montezuma"},
        {"name": "Prowers Medical Center", "type": "district", "district": "Prowers County"},
        {"name": "Lincoln Community Hospital", "type": "district", "district": "Lincoln County"},
        {"name": "Melissa Memorial Hospital", "type": "district", "district": "Phillips County"},
        {"name": "Sedgwick County Health Center", "type": "district", "district": "Sedgwick County"},
    ],
    # Kansas
    "KS": [
        {"name": "Via Christi Health", "type": "nonprofit", "notes": "Ascension subsidiary - likely has captive"},
        {"name": "University of Kansas Health System", "type": "state", "notes": "State university"},
        {"name": "Stormont Vail Health", "type": "nonprofit", "notes": "Topeka"},
        {"name": "Labette Health", "type": "county", "county": "Labette", "notes": "County hospital"},
        {"name": "Coffey County Hospital", "type": "county", "county": "Coffey"},
        {"name": "Wilson Medical Center", "type": "county", "county": "Wilson"},
        {"name": "Community Healthcare System", "type": "county", "county": "Onaga"},
        {"name": "Clay County Medical Center", "type": "county", "county": "Clay"},
        {"name": "Republic County Hospital", "type": "county", "county": "Republic"},
        {"name": "Nemaha Valley Community Hospital", "type": "county", "county": "Nemaha"},
    ],
    # Nebraska
    "NE": [
        {"name": "Nebraska Medicine", "type": "nonprofit", "notes": "UNMC affiliate"},
        {"name": "Bryan Health", "type": "nonprofit", "notes": "Lincoln"},
        {"name": "CHI Health", "type": "nonprofit", "notes": "CommonSpirit - likely has equities"},
        {"name": "Box Butte General Hospital", "type": "county", "county": "Box Butte"},
        {"name": "Chadron Community Hospital", "type": "county", "county": "Dawes"},
        {"name": "Community Hospital", "type": "county", "county": "McCook"},
        {"name": "Crete Area Medical Center", "type": "county", "county": "Saline"},
        {"name": "Phelps Memorial Health Center", "type": "county", "county": "Phelps"},
        {"name": "Boone County Health Center", "type": "county", "county": "Boone"},
    ],
    # Iowa
    "IA": [
        {"name": "University of Iowa Hospitals", "type": "state", "notes": "State university"},
        {"name": "UnityPoint Health", "type": "nonprofit", "notes": "Large regional nonprofit"},
        {"name": "MercyOne", "type": "nonprofit", "notes": "CommonSpirit/Trinity - likely has equities"},
        {"name": "Guthrie County Hospital", "type": "county", "county": "Guthrie"},
        {"name": "Buena Vista Regional Medical Center", "type": "county", "county": "Buena Vista"},
        {"name": "Jefferson County Health Center", "type": "county", "county": "Jefferson"},
        {"name": "Ringgold County Hospital", "type": "county", "county": "Ringgold"},
        {"name": "Wayne County Hospital", "type": "county", "county": "Wayne"},
        {"name": "Franklin General Hospital", "type": "county", "county": "Franklin"},
        {"name": "Mitchell County Regional Health Center", "type": "county", "county": "Mitchell"},
    ],
    # Minnesota
    "MN": [
        {"name": "Hennepin Healthcare", "type": "county", "county": "Hennepin", "notes": "HCMC Minneapolis"},
        {"name": "Regions Hospital", "type": "nonprofit", "notes": "HealthPartners"},
        {"name": "Fairview Health Services", "type": "nonprofit", "notes": "M Health Fairview"},
        {"name": "Sanford Health", "type": "nonprofit", "notes": "Large regional - may have equities"},
        {"name": "CentraCare", "type": "nonprofit", "notes": "St. Cloud based"},
        {"name": "Essentia Health", "type": "nonprofit", "notes": "Duluth based"},
        {"name": "Olmsted Medical Center", "type": "nonprofit", "notes": "Rochester"},
        {"name": "Cook County North Shore Health", "type": "district", "district": "Cook County"},
        {"name": "Lake Region Healthcare", "type": "district", "district": "Fergus Falls"},
    ],
    # Wisconsin
    "WI": [
        {"name": "UW Health", "type": "state", "notes": "University of Wisconsin"},
        {"name": "Froedtert Health", "type": "nonprofit", "notes": "Milwaukee"},
        {"name": "Aurora Health Care", "type": "nonprofit", "notes": "Advocate Aurora - likely has equities"},
        {"name": "Aspirus", "type": "nonprofit", "notes": "Wausau based"},
        {"name": "Bellin Health", "type": "nonprofit", "notes": "Green Bay"},
        {"name": "Gundersen Health System", "type": "nonprofit", "notes": "La Crosse"},
        {"name": "Marshfield Clinic Health System", "type": "nonprofit", "notes": "Central Wisconsin"},
    ],
    # Illinois
    "IL": [
        {"name": "Cook County Health", "type": "county", "county": "Cook", "notes": "Stroger Hospital"},
        {"name": "University of Illinois Hospital", "type": "state", "notes": "State university"},
        {"name": "Rush University Medical Center", "type": "nonprofit"},
        {"name": "NorthShore University HealthSystem", "type": "nonprofit"},
        {"name": "OSF HealthCare", "type": "nonprofit", "notes": "Sisters of St. Francis"},
        {"name": "HSHS", "type": "nonprofit", "notes": "Hospital Sisters Health System"},
        {"name": "Carle Health", "type": "nonprofit", "notes": "Urbana based"},
        {"name": "Memorial Health System", "type": "nonprofit", "notes": "Springfield"},
    ],
    # Indiana
    "IN": [
        {"name": "Eskenazi Health", "type": "county", "county": "Marion", "notes": "Marion County hospital"},
        {"name": "Indiana University Health", "type": "nonprofit", "notes": "Largest in state"},
        {"name": "Parkview Health", "type": "nonprofit", "notes": "Fort Wayne"},
        {"name": "Deaconess Health System", "type": "nonprofit", "notes": "Evansville"},
        {"name": "Community Health Network", "type": "nonprofit", "notes": "Indianapolis"},
        {"name": "Franciscan Health", "type": "nonprofit", "notes": "Trinity subsidiary - may have captive"},
    ],
    # Michigan
    "MI": [
        {"name": "Henry Ford Health", "type": "nonprofit"},
        {"name": "Beaumont Health", "type": "nonprofit", "notes": "Now Corewell Health"},
        {"name": "Spectrum Health", "type": "nonprofit", "notes": "Now Corewell Health"},
        {"name": "Munson Healthcare", "type": "nonprofit", "notes": "Traverse City"},
        {"name": "McLaren Health Care", "type": "nonprofit"},
        {"name": "Hurley Medical Center", "type": "county", "county": "Genesee", "notes": "Flint"},
    ],
    # Ohio
    "OH": [
        {"name": "MetroHealth System", "type": "county", "county": "Cuyahoga", "notes": "Cleveland"},
        {"name": "University Hospitals", "type": "nonprofit", "notes": "Cleveland"},
        {"name": "Cleveland Clinic", "type": "nonprofit", "notes": "Large system - likely has equities"},
        {"name": "Ohio State University Wexner Medical Center", "type": "state"},
        {"name": "OhioHealth", "type": "nonprofit", "notes": "Columbus"},
        {"name": "Kettering Health", "type": "nonprofit", "notes": "Adventist"},
        {"name": "ProMedica", "type": "nonprofit", "notes": "Toledo"},
        {"name": "Mercy Health", "type": "nonprofit", "notes": "Bon Secours Mercy - may have captive"},
    ],
    # Missouri
    "MO": [
        {"name": "University of Missouri Health Care", "type": "state"},
        {"name": "BJC HealthCare", "type": "nonprofit", "notes": "Barnes-Jewish"},
        {"name": "SSM Health", "type": "nonprofit", "notes": "Catholic system - may have captive"},
        {"name": "Mercy", "type": "nonprofit", "notes": "Catholic system - may have captive"},
        {"name": "CoxHealth", "type": "nonprofit", "notes": "Springfield"},
        {"name": "Mosaic Life Care", "type": "nonprofit", "notes": "St. Joseph"},
    ],
    # Hawaii
    "HI": [
        {"name": "Hawaii Health Systems Corporation", "type": "state", "notes": "State-run system of 12 facilities"},
        {"name": "The Queen's Health System", "type": "nonprofit"},
        {"name": "Hawaii Pacific Health", "type": "nonprofit"},
    ],
    # Alaska
    "AK": [
        {"name": "Providence Alaska", "type": "nonprofit", "notes": "Providence subsidiary - has captive"},
        {"name": "Fairbanks Memorial Hospital", "type": "nonprofit", "notes": "Foundation Health Partners"},
        {"name": "Bartlett Regional Hospital", "type": "municipal", "city": "Juneau"},
        {"name": "Mat-Su Regional Medical Center", "type": "nonprofit"},
        {"name": "Norton Sound Health Corporation", "type": "tribal"},
        {"name": "Yukon-Kuskokwim Health Corporation", "type": "tribal"},
    ],
    # Utah
    "UT": [
        {"name": "University of Utah Health", "type": "state"},
        {"name": "Intermountain Health", "type": "nonprofit", "notes": "Large system - check investment policy"},
        {"name": "MountainStar Healthcare", "type": "for_profit", "notes": "HCA - skip"},
        {"name": "Steward Health Care", "type": "for_profit", "notes": "Skip"},
    ],
    # New Mexico
    "NM": [
        {"name": "University of New Mexico Hospital", "type": "state", "county": "Bernalillo"},
        {"name": "Presbyterian Healthcare Services", "type": "nonprofit"},
        {"name": "Christus St. Vincent", "type": "nonprofit", "notes": "CHRISTUS subsidiary - has captive"},
        {"name": "San Juan Regional Medical Center", "type": "district", "district": "San Juan County"},
        {"name": "Gila Regional Medical Center", "type": "district", "district": "Grant County"},
        {"name": "Lincoln County Medical Center", "type": "district", "district": "Lincoln County"},
    ],
    # Idaho
    "ID": [
        {"name": "St. Luke's Health System", "type": "nonprofit", "notes": "Boise based"},
        {"name": "Saint Alphonsus Health System", "type": "nonprofit", "notes": "Trinity subsidiary"},
        {"name": "Kootenai Health", "type": "nonprofit", "notes": "Coeur d'Alene"},
        {"name": "Portneuf Medical Center", "type": "nonprofit", "notes": "Pocatello"},
        {"name": "Madison Memorial Hospital", "type": "district", "district": "Madison County"},
        {"name": "Weiser Memorial Hospital", "type": "district", "district": "Washington County"},
        {"name": "Lost Rivers Medical Center", "type": "district", "district": "Butte County"},
    ],
    # Montana
    "MT": [
        {"name": "Billings Clinic", "type": "nonprofit"},
        {"name": "Providence Montana", "type": "nonprofit", "notes": "Providence subsidiary"},
        {"name": "St. Peter's Health", "type": "nonprofit", "notes": "Helena"},
        {"name": "SCL Health Montana", "type": "nonprofit", "notes": "Now Intermountain"},
        {"name": "Marcus Daly Memorial Hospital", "type": "district", "district": "Ravalli County"},
        {"name": "Community Medical Center", "type": "nonprofit", "notes": "Missoula"},
    ],
    # Wyoming
    "WY": [
        {"name": "Cheyenne Regional Medical Center", "type": "nonprofit"},
        {"name": "Wyoming Medical Center", "type": "nonprofit", "notes": "Casper - Banner subsidiary"},
        {"name": "St. John's Medical Center", "type": "nonprofit", "notes": "Jackson"},
        {"name": "Memorial Hospital of Sweetwater County", "type": "county", "county": "Sweetwater"},
        {"name": "Campbell County Health", "type": "county", "county": "Campbell"},
        {"name": "Hot Springs County Memorial Hospital", "type": "county", "county": "Hot Springs"},
        {"name": "Niobrara Health and Life Center", "type": "county", "county": "Niobrara"},
        {"name": "Crook County Medical Services District", "type": "district", "district": "Crook County"},
    ],
    # North Dakota
    "ND": [
        {"name": "Sanford Health", "type": "nonprofit", "notes": "Fargo - large system"},
        {"name": "Essentia Health", "type": "nonprofit", "notes": "Regional"},
        {"name": "Altru Health System", "type": "nonprofit", "notes": "Grand Forks"},
        {"name": "Trinity Health", "type": "nonprofit", "notes": "Minot"},
        {"name": "Sakakawea Medical Center", "type": "district", "district": "Hazen"},
        {"name": "McKenzie County Healthcare Systems", "type": "district", "district": "McKenzie County"},
    ],
    # South Dakota
    "SD": [
        {"name": "Sanford Health", "type": "nonprofit", "notes": "Sioux Falls"},
        {"name": "Avera Health", "type": "nonprofit", "notes": "Large regional system"},
        {"name": "Regional Health", "type": "nonprofit", "notes": "Now Monument Health"},
        {"name": "Brookings Health System", "type": "nonprofit"},
        {"name": "Prairie Lakes Healthcare System", "type": "nonprofit", "notes": "Watertown"},
        {"name": "Huron Regional Medical Center", "type": "nonprofit"},
    ],
}


@dataclass
class SystemFindings:
    """Findings for a health system."""
    system_name: str
    state: str
    system_type: str  # "public_district", "county", "authority", "nonprofit", "state", "for_profit"
    total_cash_investments: float
    fiscal_year: str
    
    # Investment findings
    has_equities: str = "unknown"  # "yes", "no", "de_minimis", "unknown"
    equity_confidence: str = "unknown"  # "audit_verified", "state_law_inferred", "990_verified", "unknown"
    
    # Captive findings
    has_captive: str = "unknown"  # "yes", "no", "unknown"
    captive_name: Optional[str] = None
    
    # Self-insurance
    si_reserves: float = 0.0
    
    # Target status
    is_target: bool = False
    target_reason: str = ""
    
    # Source
    source_url: str = ""
    source_page: str = ""
    source_type: str = ""  # "emma", "system_audit", "990", "hcris", "state_law_inferred"
    
    # Notes
    notes: str = ""


def generate_listing_id(system_name: str, state: str) -> str:
    """Generate a unique listing ID for Frappe."""
    name_clean = re.sub(r'[^A-Za-z0-9\s-]', '', system_name)
    name_clean = name_clean.replace(' ', '-').upper()[:30]
    return f"QS-{state}-{name_clean}"


def create_frappe_company(findings: SystemFindings) -> dict:
    """Create a Frappe BZ Company Listing record structure."""
    listing_id = generate_listing_id(findings.system_name, findings.state)
    
    segment = "Healthcare"
    if findings.system_type in ["public_district", "county", "authority", "state"]:
        segment = "Government"
    
    score_tier = "warm" if findings.total_cash_investments > 100_000_000 else "cold"
    if findings.is_target:
        score_tier = "hot" if findings.total_cash_investments > 200_000_000 else "warm"
    
    notes = f"[QUICK-SCREEN MW/West] State: {findings.state}. Type: {findings.system_type}. "
    notes += f"Cash+Investments: ${findings.total_cash_investments/1e6:.1f}M. "
    notes += f"Equities: {findings.has_equities} ({findings.equity_confidence}). "
    notes += f"Captive: {findings.has_captive}. "
    if findings.si_reserves > 0:
        notes += f"SI Reserves: ${findings.si_reserves/1e6:.2f}M. "
    notes += f"Target: {findings.is_target}. "
    if findings.notes:
        notes += findings.notes
    
    return {
        "listing_id": listing_id,
        "company_name": findings.system_name,
        "segment": segment,
        "company_type": findings.system_type,
        "state": findings.state,
        "country": "United States",
        "revenue": 0,
        "employees": 0,
        "score_tier": score_tier,
        "enrichment_status": "complete",
        "pipeline_status": "prospect",
        "source": "Quick Screen Pipeline - MW/West",
        "notes": notes
    }


def create_frappe_facts(findings: SystemFindings, entity_name: str) -> list[dict]:
    """Create Frappe BZ Source Financial Fact records."""
    facts = []
    
    # Cash and investments fact
    if findings.total_cash_investments > 0:
        content = f"{findings.system_name}|cash_and_investments|{findings.total_cash_investments}|{findings.source_url}"
        facts.append({
            "entity": entity_name,
            "fact_category": "cash_and_investments",
            "fact_name": "Total Operating Cash and Investments",
            "reported_value_text": f"${findings.total_cash_investments/1e6:,.1f}M",
            "reported_value_usd": int(findings.total_cash_investments),
            "fiscal_year": findings.fiscal_year,
            "source_url": findings.source_url,
            "source_domain": urlparse(findings.source_url).netloc if findings.source_url else "unknown",
            "page_reference": findings.source_page or "Financial Statements",
            "source_quote": f"Operating cash and investments (excluding pension/OPEB). Equities: {findings.has_equities}. Captive: {findings.has_captive}.",
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "confidence": "verified" if "verified" in findings.equity_confidence else "unresolved",
            "decision_eligible": 1,
            "field_mapping_status": "source_fact_only"
        })
    
    # Portfolio policy fact (equities status)
    if findings.has_equities != "unknown":
        content = f"{findings.system_name}|portfolio_policy|{findings.has_equities}|{findings.source_url}"
        facts.append({
            "entity": entity_name,
            "fact_category": "portfolio_policy",
            "fact_name": "Has Equity Securities",
            "reported_value_text": findings.has_equities.upper(),
            "fiscal_year": findings.fiscal_year,
            "source_url": findings.source_url,
            "source_domain": urlparse(findings.source_url).netloc if findings.source_url else "unknown",
            "page_reference": findings.source_page or "Investment Note",
            "source_quote": f"Equity securities in operating portfolio: {findings.has_equities}. Confidence: {findings.equity_confidence}.",
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "confidence": "verified" if "verified" in findings.equity_confidence else "unresolved",
            "decision_eligible": 1,
            "field_mapping_status": "source_fact_only"
        })
    
    # Captive status fact
    if findings.has_captive != "unknown":
        content = f"{findings.system_name}|captive|{findings.has_captive}|{findings.source_url}"
        captive_info = findings.captive_name if findings.captive_name else "None disclosed"
        facts.append({
            "entity": entity_name,
            "fact_category": "captive",
            "fact_name": "Has Captive Insurance",
            "reported_value_text": findings.has_captive.upper(),
            "fiscal_year": findings.fiscal_year,
            "source_url": findings.source_url,
            "source_domain": urlparse(findings.source_url).netloc if findings.source_url else "unknown",
            "page_reference": findings.source_page or "Insurance Note",
            "source_quote": f"Captive insurance subsidiary: {captive_info}",
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "confidence": "verified",
            "decision_eligible": 1,
            "field_mapping_status": "source_fact_only"
        })
    
    # Self-insurance reserves fact
    if findings.si_reserves > 0:
        content = f"{findings.system_name}|self_insurance|{findings.si_reserves}|{findings.source_url}"
        facts.append({
            "entity": entity_name,
            "fact_category": "self_insurance",
            "fact_name": "Total Self-Insurance Reserves",
            "reported_value_text": f"${findings.si_reserves/1e6:,.2f}M",
            "reported_value_usd": int(findings.si_reserves),
            "fiscal_year": findings.fiscal_year,
            "source_url": findings.source_url,
            "source_domain": urlparse(findings.source_url).netloc if findings.source_url else "unknown",
            "page_reference": findings.source_page or "Risk Management Note",
            "source_quote": "Self-insurance claims liability from audit risk management note",
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "confidence": "verified",
            "decision_eligible": 1,
            "field_mapping_status": "source_fact_only"
        })
    
    return facts


def determine_target(findings: SystemFindings) -> tuple[bool, str]:
    """Determine if a system is a target."""
    # Check investment threshold
    if findings.total_cash_investments < 25_000_000:
        return (False, "Below $25M threshold")
    
    # Check equity status
    if findings.has_equities == "yes":
        return (False, "Has equity securities")
    
    if findings.has_equities == "unknown":
        return (False, "Equity status unknown")
    
    # de_minimis counts as "no" for targeting purposes
    equity_ok = findings.has_equities in ["no", "de_minimis"]
    
    # Check captive status
    if findings.has_captive == "yes":
        return (False, f"Has captive insurance: {findings.captive_name or 'name unknown'}")
    
    if findings.has_captive == "unknown":
        return (False, "Captive status unknown")
    
    captive_ok = findings.has_captive == "no"
    
    if equity_ok and captive_ok:
        return (True, "Fixed income only, no captive, >$25M")
    
    return (False, "Did not meet all criteria")


def export_results_csv(findings_list: list[SystemFindings], output_path: str):
    """Export findings to CSV."""
    fieldnames = [
        "system_name", "state", "system_type", "total_cash_investments", "fiscal_year",
        "has_equities", "equity_confidence", "has_captive", "captive_name", "si_reserves",
        "is_target", "target_reason", "source_url", "source_page", "source_type", "notes"
    ]
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for findings in findings_list:
            writer.writerow({
                "system_name": findings.system_name,
                "state": findings.state,
                "system_type": findings.system_type,
                "total_cash_investments": findings.total_cash_investments,
                "fiscal_year": findings.fiscal_year,
                "has_equities": findings.has_equities,
                "equity_confidence": findings.equity_confidence,
                "has_captive": findings.has_captive,
                "captive_name": findings.captive_name or "",
                "si_reserves": findings.si_reserves,
                "is_target": findings.is_target,
                "target_reason": findings.target_reason,
                "source_url": findings.source_url,
                "source_page": findings.source_page,
                "source_type": findings.source_type,
                "notes": findings.notes
            })


def generate_report(findings_list: list[SystemFindings]) -> str:
    """Generate markdown report."""
    targets = [f for f in findings_list if f.is_target]
    
    # Count by state
    by_state = {}
    for f in findings_list:
        if f.state not in by_state:
            by_state[f.state] = {"total": 0, "targets": 0}
        by_state[f.state]["total"] += 1
        if f.is_target:
            by_state[f.state]["targets"] += 1
    
    report = """# Midwest/West Hospital Quick Screen Results

## Summary

"""
    report += f"**Total Systems Reviewed:** {len(findings_list)}\n"
    report += f"**Targets Found:** {len(targets)}\n\n"
    
    report += "### Systems Reviewed by State\n\n"
    report += "| State | Reviewed | Targets |\n"
    report += "|-------|----------|--------|\n"
    for state in sorted(by_state.keys()):
        report += f"| {state} | {by_state[state]['total']} | {by_state[state]['targets']} |\n"
    
    report += "\n## TARGET Shortlist\n\n"
    report += "| System | State | Cash+Investments | Equities | Captive | SI Reserves | Source URL |\n"
    report += "|--------|-------|------------------|----------|---------|-------------|------------|\n"
    
    for t in sorted(targets, key=lambda x: x.total_cash_investments, reverse=True):
        si_display = f"${t.si_reserves/1e6:.1f}M" if t.si_reserves > 0 else "-"
        report += f"| {t.system_name} | {t.state} | ${t.total_cash_investments/1e6:.1f}M | {t.has_equities} | {t.has_captive} | {si_display} | {t.source_url[:50]}... |\n"
    
    report += f"\n**Total TARGET Cash+Investments:** ${sum(t.total_cash_investments for t in targets)/1e6:,.1f}M\n"
    
    return report


if __name__ == "__main__":
    print("Midwest/West Hospital Quick Screen Pipeline")
    print("=" * 60)
    print(f"Target states: {', '.join(TARGET_STATES)}")
    print("\nThis script provides data structures and utilities.")
    print("Run the main research loop separately to populate findings.")
