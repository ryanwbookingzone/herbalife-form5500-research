#!/usr/bin/env python3
"""Sync East/South hospital systems to Frappe BZ Company Listing and BZ Source Financial Fact"""

import csv
import hashlib
import json
import requests
import urllib.parse
from typing import Optional, Dict, List

BASE_URL = "https://bz-api.dev.bookingzone.com"
AUTH_HEADER = {"Authorization": "token 823f038ebbc2115:fee5ea3bee70e2e"}

def api_get(endpoint: str, params: Optional[Dict] = None) -> Dict:
    url = f"{BASE_URL}{endpoint}"
    resp = requests.get(url, headers=AUTH_HEADER, params=params)
    resp.raise_for_status()
    return resp.json()

def api_post(endpoint: str, data: Dict) -> Dict:
    url = f"{BASE_URL}{endpoint}"
    resp = requests.post(url, headers=AUTH_HEADER, json=data)
    resp.raise_for_status()
    return resp.json()

def check_company_exists(company_name: str) -> Optional[str]:
    """Check if company exists by name, return doc name if found"""
    encoded_name = urllib.parse.quote(company_name)
    try:
        resp = api_get(f"/api/resource/BZ%20Company%20Listing", 
                      params={"filters": json.dumps([["company_name", "=", company_name]]),
                              "fields": json.dumps(["name", "company_name"])})
        data = resp.get("data", [])
        if data:
            return data[0]["name"]
    except Exception as e:
        print(f"  Error checking company {company_name}: {e}")
    return None

def create_company(system: Dict) -> Optional[str]:
    """Create a BZ Company Listing record, return doc name"""
    company_name = system["system_name"]
    
    existing = check_company_exists(company_name)
    if existing:
        print(f"  Company exists: {company_name} -> {existing}")
        return existing
    
    state_map = {
        "FL": "Florida", "GA": "Georgia", "AL": "Alabama", "MS": "Mississippi",
        "LA": "Louisiana", "AR": "Arkansas", "TN": "Tennessee", "KY": "Kentucky",
        "NC": "North Carolina", "SC": "South Carolina", "VA": "Virginia",
        "WV": "West Virginia", "MD": "Maryland", "DE": "Delaware", "DC": "District of Columbia",
        "PA": "Pennsylvania", "NJ": "New Jersey", "NY": "New York", "CT": "Connecticut",
        "RI": "Rhode Island", "MA": "Massachusetts", "VT": "Vermont", "NH": "New Hampshire",
        "ME": "Maine", "OK": "Oklahoma"
    }
    
    cash_inv = int(system.get("cash_investments", 0) or 0)
    has_captive = 1 if system.get("has_captive", "").lower() == "yes" else 0
    has_equities = system.get("has_equities", "").lower() == "yes"
    
    doc = {
        "doctype": "BZ Company Listing",
        "company_name": company_name,
        "state": state_map.get(system.get("state", ""), system.get("state", "")),
        "segment": "Healthcare",
        "portfolio_size": cash_inv,
        "has_captive": has_captive,
        "is_operating_hospital_prospect": 1,
        "equity_pct": 100 if has_equities else 0,
        "fi_pct": 0 if has_equities else 100,
        "dossier_status": "pending",
        "pipeline_status": "prospect",
        "source": "quick_screen_east_south"
    }
    
    try:
        resp = api_post("/api/resource/BZ%20Company%20Listing", {"data": json.dumps(doc)})
        doc_name = resp.get("data", {}).get("name")
        print(f"  Created company: {company_name} -> {doc_name}")
        return doc_name
    except Exception as e:
        print(f"  Error creating company {company_name}: {e}")
        return None

def create_financial_fact(entity_name: str, system: Dict) -> bool:
    """Create BZ Source Financial Fact for a system"""
    cash_inv = int(system.get("cash_investments", 0) or 0)
    has_equities = system.get("has_equities", "").lower()
    has_captive = system.get("has_captive", "").lower()
    fiscal_year = system.get("fiscal_year", "unknown")
    source_url = system.get("source_url", "")
    notes = system.get("notes", "")
    is_target = system.get("is_target", "").lower() == "true"
    
    fact_name = f"Quick Screen Summary - {system['system_name']}"
    content_for_hash = f"{entity_name}|{fact_name}|{cash_inv}|{has_equities}|{has_captive}|{fiscal_year}"
    content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()[:16]
    
    reported_value = f"Cash+Investments: ${cash_inv:,.0f}" if cash_inv else "Cash+Investments: unknown"
    reported_value += f" | Equities: {has_equities} | Captive: {has_captive} | Target: {is_target}"
    
    source_domain = ""
    if source_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(source_url)
            source_domain = parsed.netloc or "unknown"
        except:
            source_domain = "unknown"
    
    doc = {
        "doctype": "BZ Source Financial Fact",
        "entity": entity_name,
        "fact_category": "cash_and_investments",
        "fact_name": fact_name,
        "reported_value_text": reported_value,
        "reported_value_usd": cash_inv if cash_inv else 0,
        "fiscal_year": fiscal_year,
        "source_url": source_url or "N/A",
        "source_domain": source_domain or "N/A",
        "page_reference": "Investment Note / Balance Sheet",
        "source_quote": notes[:500] if notes else "See source document",
        "content_hash": content_hash,
        "confidence": "verified" if "audit_verified" in system.get("confidence", "") or "990_verified" in system.get("confidence", "") else "unresolved",
        "decision_eligible": 1 if is_target else 0,
        "field_mapping_status": "source_fact_only"
    }
    
    try:
        resp = api_post("/api/resource/BZ%20Source%20Financial%20Fact", {"data": json.dumps(doc)})
        fact_name = resp.get("data", {}).get("name")
        print(f"    Created fact: {fact_name}")
        return True
    except requests.exceptions.HTTPError as e:
        if "DuplicateEntryError" in str(e.response.text) or "content_hash" in str(e.response.text):
            print(f"    Fact already exists (duplicate hash)")
            return True
        print(f"    Error creating fact: {e}")
        return False
    except Exception as e:
        print(f"    Error creating fact: {e}")
        return False

def main():
    csv_path = "/workspace/quick_screen/shortlist_east_south.csv"
    
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        systems = list(reader)
    
    print(f"Processing {len(systems)} systems...")
    
    companies_created = 0
    companies_existed = 0
    facts_created = 0
    facts_skipped = 0
    
    for i, system in enumerate(systems):
        print(f"\n[{i+1}/{len(systems)}] {system['system_name']} ({system.get('state', '')})")
        
        entity_name = create_company(system)
        if entity_name:
            if "Created" in str(entity_name):
                companies_created += 1
            else:
                companies_existed += 1
            
            confidence = system.get("confidence", "")
            if "verified" in confidence.lower() and entity_name:
                if create_financial_fact(entity_name, system):
                    facts_created += 1
                else:
                    facts_skipped += 1
            else:
                print(f"    Skipping fact (needs_audit)")
                facts_skipped += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"Companies processed: {len(systems)}")
    print(f"Facts created: {facts_created}")
    print(f"Facts skipped: {facts_skipped}")

if __name__ == "__main__":
    main()
