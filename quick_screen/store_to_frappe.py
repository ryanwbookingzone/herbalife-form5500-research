#!/usr/bin/env python3
"""
Store target systems to Frappe BZ Company Listing and BZ Source Financial Fact.
This script generates the data structure - actual API calls done separately.
"""

import pandas as pd
import json
import hashlib

df = pd.read_csv('/workspace/quick_screen/quick_screen_tx_ca.csv')
targets = df[df['is_target'] == True].copy()

# Generate Frappe records
company_listings = []
financial_facts = []

for _, row in targets.iterrows():
    # Generate listing ID
    name_clean = row['system_name'].replace(' ', '-').replace(',', '').upper()[:30]
    listing_id = f"QS-{row['state']}-{name_clean}"
    
    # BZ Company Listing record
    company = {
        "listing_id": listing_id,
        "company_name": row['system_name'],
        "segment": "Healthcare",
        "company_type": row['system_type'] if pd.notna(row['system_type']) else "hospital",
        "country": "United States",
        "revenue": 0,
        "employees": 0,
        "premium_estimate": 0,
        "captive_score": 0,
        "insurance_score_cl": 0,
        "score_tier": "warm" if row['total_cash_investments'] > 100000000 else "cold",
        "enrichment_status": "complete",
        "pipeline_status": "prospect",
        "source": "Quick Screen Pipeline",
        "notes": f"[QUICK-SCREEN] State: {row['state']}. Cash+Investments: ${row['total_cash_investments']/1e6:.1f}M. "
                 f"Has equities: {row['has_equities']}. Has captive: {row['has_captive']}. "
                 f"SI Reserves: ${row['total_self_insurance_reserves']/1e6:.1f}M. "
                 f"Source: {row['source_type']}. {row['si_notes'] if pd.notna(row['si_notes']) else ''}"
    }
    company_listings.append(company)
    
    # BZ Source Financial Fact - Cash and Investments
    if pd.notna(row['total_cash_investments']) and row['total_cash_investments'] > 0:
        content = f"{row['system_name']}|cash_and_investments|{row['total_cash_investments']}|{row['source_url']}"
        fact_cash = {
            "entity": listing_id,  # Will need to be linked to actual entity after creation
            "fact_category": "cash_and_investments",
            "fact_name": "Total Operating Cash and Investments",
            "reported_value_text": f"${row['total_cash_investments']/1e6:,.1f}M",
            "reported_value_usd": int(row['total_cash_investments']),
            "fiscal_year": str(row['as_of_date'])[:10] if pd.notna(row['as_of_date']) else "FY2024",
            "source_url": row['source_url'] if pd.notna(row['source_url']) else "",
            "source_domain": row['source_url'].split('/')[2] if pd.notna(row['source_url']) and '/' in str(row['source_url']) else "",
            "page_reference": row['source_page'] if pd.notna(row['source_page']) else "",
            "source_quote": f"Operating cash and investments (excluding pension/OPEB)",
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "confidence": "verified" if 'verified' in str(row['source_type']) else "inferred",
            "decision_eligible": 1,
            "field_mapping_status": "source_fact_only"
        }
        financial_facts.append(fact_cash)
    
    # BZ Source Financial Fact - Self-Insurance
    if pd.notna(row['total_self_insurance_reserves']) and row['total_self_insurance_reserves'] > 0:
        content = f"{row['system_name']}|self_insurance|{row['total_self_insurance_reserves']}|{row['si_source_url']}"
        fact_si = {
            "entity": listing_id,
            "fact_category": "self_insurance",
            "fact_name": "Total Self-Insurance Reserves",
            "reported_value_text": f"${row['total_self_insurance_reserves']/1e6:,.2f}M",
            "reported_value_usd": int(row['total_self_insurance_reserves']),
            "fiscal_year": str(row['si_fiscal_year']) if pd.notna(row['si_fiscal_year']) else "FY2024",
            "source_url": row['si_source_url'] if pd.notna(row['si_source_url']) else "",
            "source_domain": row['si_source_url'].split('/')[2] if pd.notna(row['si_source_url']) and '/' in str(row['si_source_url']) else "",
            "page_reference": row['si_source_page'] if pd.notna(row['si_source_page']) else "",
            "source_quote": row['si_notes'] if pd.notna(row['si_notes']) else "",
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "confidence": "verified",
            "decision_eligible": 1,
            "field_mapping_status": "source_fact_only"
        }
        financial_facts.append(fact_si)

# Save to JSON files for Frappe import
with open('/workspace/quick_screen/frappe_company_listings.json', 'w') as f:
    json.dump(company_listings, f, indent=2)

with open('/workspace/quick_screen/frappe_financial_facts.json', 'w') as f:
    json.dump(financial_facts, f, indent=2)

print(f"Generated {len(company_listings)} BZ Company Listing records")
print(f"Generated {len(financial_facts)} BZ Source Financial Fact records")
print("\nSaved to:")
print("  - /workspace/quick_screen/frappe_company_listings.json")
print("  - /workspace/quick_screen/frappe_financial_facts.json")
