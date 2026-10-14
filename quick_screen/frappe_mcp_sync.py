#!/usr/bin/env python3
"""
Frappe sync script using MCP tools for East/South health systems.
Creates BZ Company Listing and BZ Source Financial Fact records.
"""

import csv
import hashlib
import json
import re
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple

CSV_FILE = "/workspace/quick_screen/shortlist_east_south.csv"

def load_systems() -> List[Dict]:
    """Load systems from CSV file."""
    systems = []
    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            systems.append(row)
    return systems

def generate_listing_id(system_name: str, state: str) -> str:
    """Generate unique listing_id for a health system."""
    slug = re.sub(r'[^a-z0-9]+', '-', system_name.lower()).strip('-')
    return f"health-{state.lower()}-{slug}"

def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return "unknown"
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        return domain.replace('www.', '')
    except:
        return "unknown"

def generate_content_hash(entity: str, fact_category: str, fact_name: str, value: str, fy: str) -> str:
    """Generate unique content hash for a fact."""
    content = f"{entity}|{fact_category}|{fact_name}|{value}|{fy}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]

def prepare_company_data(system: Dict) -> Dict:
    """Prepare BZ Company Listing data for a system."""
    state_map = {
        'FL': 'Florida', 'GA': 'Georgia', 'AL': 'Alabama', 'MS': 'Mississippi',
        'LA': 'Louisiana', 'AR': 'Arkansas', 'TN': 'Tennessee', 'KY': 'Kentucky',
        'NC': 'North Carolina', 'SC': 'South Carolina', 'VA': 'Virginia',
        'WV': 'West Virginia', 'MD': 'Maryland', 'DE': 'Delaware', 'DC': 'District of Columbia',
        'PA': 'Pennsylvania', 'NJ': 'New Jersey', 'NY': 'New York', 'CT': 'Connecticut',
        'RI': 'Rhode Island', 'MA': 'Massachusetts', 'VT': 'Vermont', 'NH': 'New Hampshire',
        'ME': 'Maine', 'OK': 'Oklahoma'
    }
    
    state = system['state']
    listing_id = generate_listing_id(system['system_name'], state)
    
    return {
        'listing_id': listing_id,
        'company_name': system['system_name'],
        'segment': 'Healthcare',
        'state': state_map.get(state, state)
    }

def prepare_facts(system: Dict, entity_name: str) -> List[Dict]:
    """Prepare BZ Source Financial Fact records for a system."""
    facts = []
    source_url = system.get('source_url', '')
    source_domain = extract_domain(source_url)
    fiscal_year = system.get('fiscal_year', 'Unknown')
    confidence = 'verified' if system.get('confidence', '').endswith('_verified') else 'unresolved'
    notes = system.get('notes', '')
    
    cash_inv = system.get('cash_investments', '0')
    if cash_inv and cash_inv != '0':
        cash_amt = int(cash_inv) if cash_inv.isdigit() else 0
        if cash_amt > 0:
            facts.append({
                'entity': entity_name,
                'fact_category': 'cash_and_investments',
                'fact_name': 'Total Cash and Investments',
                'reported_value_text': f"${cash_amt:,}",
                'fiscal_year': fiscal_year,
                'source_url': source_url,
                'source_domain': source_domain,
                'page_reference': 'Financial Statements',
                'source_quote': notes[:500] if notes else 'See audit/financial statements',
                'content_hash': generate_content_hash(entity_name, 'cash_and_investments', 'total', str(cash_amt), fiscal_year),
                'confidence': confidence,
                'field_mapping_status': 'source_fact_only'
            })
    
    has_equities = system.get('has_equities', 'unknown')
    if has_equities != 'unknown':
        facts.append({
            'entity': entity_name,
            'fact_category': 'portfolio_policy',
            'fact_name': 'Has Equity Investments',
            'reported_value_text': 'Yes' if has_equities == 'yes' else 'No',
            'fiscal_year': fiscal_year,
            'source_url': source_url,
            'source_domain': source_domain,
            'page_reference': 'Investment Policy/Notes',
            'source_quote': notes[:500] if notes else 'See audit/financial statements',
            'content_hash': generate_content_hash(entity_name, 'portfolio_policy', 'equities', has_equities, fiscal_year),
            'confidence': confidence,
            'field_mapping_status': 'source_fact_only'
        })
    
    has_captive = system.get('has_captive', 'unknown')
    if has_captive != 'unknown':
        facts.append({
            'entity': entity_name,
            'fact_category': 'captive',
            'fact_name': 'Has Captive Insurance',
            'reported_value_text': 'Yes' if has_captive == 'yes' else 'No',
            'fiscal_year': fiscal_year,
            'source_url': source_url,
            'source_domain': source_domain,
            'page_reference': 'Insurance Notes',
            'source_quote': notes[:500] if notes else 'See audit/financial statements',
            'content_hash': generate_content_hash(entity_name, 'captive', 'has_captive', has_captive, fiscal_year),
            'confidence': confidence,
            'field_mapping_status': 'source_fact_only'
        })
    
    si_reserves = system.get('si_reserves', '0')
    if si_reserves and si_reserves != '0':
        si_amt = int(si_reserves) if si_reserves.isdigit() else 0
        if si_amt > 0:
            facts.append({
                'entity': entity_name,
                'fact_category': 'self_insurance',
                'fact_name': 'Self-Insurance Reserves',
                'reported_value_text': f"${si_amt:,}",
                'fiscal_year': fiscal_year,
                'source_url': source_url,
                'source_domain': source_domain,
                'page_reference': 'Self-Insurance Notes',
                'source_quote': notes[:500] if notes else 'See audit/financial statements',
                'content_hash': generate_content_hash(entity_name, 'self_insurance', 'reserves', str(si_amt), fiscal_year),
                'confidence': confidence,
                'field_mapping_status': 'source_fact_only'
            })
    
    return facts

def main():
    """Main function to prepare data for Frappe sync."""
    systems = load_systems()
    print(f"Loaded {len(systems)} systems from CSV")
    
    companies_to_create = []
    facts_to_create = []
    
    for system in systems:
        company_data = prepare_company_data(system)
        companies_to_create.append(company_data)
        
        if system.get('confidence', '').endswith('_verified'):
            entity_name = company_data['listing_id']
            facts = prepare_facts(system, entity_name)
            facts_to_create.extend(facts)
    
    print(f"\nCompanies to create: {len(companies_to_create)}")
    print(f"Facts to create: {len(facts_to_create)}")
    
    with open('/workspace/quick_screen/companies_for_frappe.json', 'w') as f:
        json.dump(companies_to_create, f, indent=2)
    
    with open('/workspace/quick_screen/facts_for_frappe.json', 'w') as f:
        json.dump(facts_to_create, f, indent=2)
    
    print("\nData exported to JSON files")
    
    verified_count = sum(1 for s in systems if s.get('confidence', '').endswith('_verified'))
    needs_audit_count = sum(1 for s in systems if s.get('confidence', '') == 'needs_audit')
    targets = [s for s in systems if s.get('is_target', '').lower() == 'true']
    
    print(f"\nSummary:")
    print(f"  Total systems: {len(systems)}")
    print(f"  Verified: {verified_count}")
    print(f"  Needs audit: {needs_audit_count}")
    print(f"  Targets: {len(targets)}")
    for t in targets:
        print(f"    - {t['system_name']} ({t['state']}): ${int(t['cash_investments']):,}")

if __name__ == '__main__':
    main()
