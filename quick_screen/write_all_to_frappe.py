#!/usr/bin/env python3
"""
Write all 121 systems to Frappe via REST API.
Generates the data and tracks what needs to be created.
"""

import pandas as pd
import hashlib
import json

df = pd.read_csv('/workspace/quick_screen/quick_screen_tx_ca.csv')

# Generate all records needed
all_companies = []
all_facts = []

for idx, row in df.iterrows():
    # Generate listing ID (sanitized)
    name_clean = ''.join(c if c.isalnum() or c == '-' else '-' for c in row['system_name'].upper())[:30]
    listing_id = f"QS-{row['state']}-{name_clean}"
    
    # Determine score tier
    cash = row['total_cash_investments'] if pd.notna(row['total_cash_investments']) else 0
    is_target = row['is_target'] if pd.notna(row['is_target']) else False
    score_tier = "warm" if is_target and cash > 50000000 else ("cold" if not is_target else "lukewarm")
    
    # Build notes
    notes = f"[QUICK-SCREEN] State: {row['state']}. "
    if cash > 0:
        notes += f"Cash+Inv: ${cash/1e6:.1f}M. "
    notes += f"Equities: {row['has_equities'] if pd.notna(row['has_equities']) else 'unknown'}. "
    notes += f"Captive: {row['has_captive'] if pd.notna(row['has_captive']) else 'unknown'}. "
    notes += f"Target: {'YES' if is_target else 'NO'}. "
    if pd.notna(row['source_type']):
        notes += f"Confidence: {row['source_type']}. "
    if pd.notna(row['si_notes']):
        notes += str(row['si_notes'])[:200]
    
    company = {
        "listing_id": listing_id,
        "company_name": row['system_name'],
        "segment": "Healthcare",
        "company_type": row['system_type'] if pd.notna(row['system_type']) else "hospital",
        "country": "United States",
        "score_tier": score_tier,
        "enrichment_status": "complete",
        "pipeline_status": "prospect",
        "source": "Quick Screen Pipeline",
        "notes": notes[:500]  # Limit notes length
    }
    all_companies.append(company)
    
    # Create facts for this system
    facts_for_system = []
    
    # Fact 1: Cash and Investments
    if pd.notna(row['total_cash_investments']) and row['total_cash_investments'] > 0:
        content = f"{row['system_name']}|cash|{row['total_cash_investments']}"
        facts_for_system.append({
            "listing_id": listing_id,
            "fact_category": "cash_and_investments",
            "fact_name": "Total Operating Cash and Investments",
            "reported_value_text": f"${row['total_cash_investments']/1e6:,.1f}M",
            "reported_value_usd": int(row['total_cash_investments']),
            "fiscal_year": str(row['as_of_date'])[:10] if pd.notna(row['as_of_date']) else "FY2024",
            "source_url": str(row['source_url']) if pd.notna(row['source_url']) else "",
            "page_reference": str(row['source_page']) if pd.notna(row['source_page']) else "",
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:40],
            "confidence": "verified" if 'verified' in str(row['source_type']) else "inferred"
        })
    
    # Fact 2: Equities flag
    if pd.notna(row['has_equities']):
        content = f"{row['system_name']}|equities|{row['has_equities']}"
        facts_for_system.append({
            "listing_id": listing_id,
            "fact_category": "investment_allocation",
            "fact_name": "Has Equity Securities",
            "reported_value_text": str(row['has_equities']).upper(),
            "reported_value_usd": 1 if str(row['has_equities']).lower() == 'yes' else 0,
            "fiscal_year": str(row['as_of_date'])[:10] if pd.notna(row['as_of_date']) else "FY2024",
            "source_url": str(row['source_url']) if pd.notna(row['source_url']) else "",
            "page_reference": str(row['source_page']) if pd.notna(row['source_page']) else "",
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:40],
            "confidence": "verified" if 'verified' in str(row['source_type']) else "inferred"
        })
    
    # Fact 3: Captive flag
    if pd.notna(row['has_captive']):
        content = f"{row['system_name']}|captive|{row['has_captive']}"
        facts_for_system.append({
            "listing_id": listing_id,
            "fact_category": "insurance_structure",
            "fact_name": "Has Captive Insurance",
            "reported_value_text": str(row['has_captive']).upper(),
            "reported_value_usd": 1 if str(row['has_captive']).lower() == 'yes' else 0,
            "fiscal_year": str(row['as_of_date'])[:10] if pd.notna(row['as_of_date']) else "FY2024",
            "source_url": str(row['source_url']) if pd.notna(row['source_url']) else "",
            "page_reference": str(row['source_page']) if pd.notna(row['source_page']) else "",
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:40],
            "confidence": "verified" if 'verified' in str(row['source_type']) else "inferred"
        })
    
    # Fact 4: Self-Insurance Reserves
    if pd.notna(row['total_self_insurance_reserves']) and row['total_self_insurance_reserves'] > 0:
        content = f"{row['system_name']}|si|{row['total_self_insurance_reserves']}"
        facts_for_system.append({
            "listing_id": listing_id,
            "fact_category": "self_insurance",
            "fact_name": "Total Self-Insurance Reserves",
            "reported_value_text": f"${row['total_self_insurance_reserves']/1e6:,.2f}M",
            "reported_value_usd": int(row['total_self_insurance_reserves']),
            "fiscal_year": str(row['si_fiscal_year']) if pd.notna(row['si_fiscal_year']) else "FY2024",
            "source_url": str(row['si_source_url']) if pd.notna(row['si_source_url']) else "",
            "page_reference": str(row['si_source_page']) if pd.notna(row['si_source_page']) else "",
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:40],
            "confidence": "verified"
        })
    
    # Fact 5: Target flag
    content = f"{row['system_name']}|target|{is_target}"
    facts_for_system.append({
        "listing_id": listing_id,
        "fact_category": "screening_result",
        "fact_name": "Captive Insurance Target",
        "reported_value_text": "YES" if is_target else "NO",
        "reported_value_usd": 1 if is_target else 0,
        "fiscal_year": "2026",
        "source_url": str(row['source_url']) if pd.notna(row['source_url']) else "",
        "page_reference": "Quick Screen Pipeline Analysis",
        "content_hash": hashlib.sha256(content.encode()).hexdigest()[:40],
        "confidence": str(row['source_type']) if pd.notna(row['source_type']) else "inferred"
    })
    
    all_facts.extend(facts_for_system)

# Save to JSON for reference
with open('/workspace/quick_screen/frappe_all_companies.json', 'w') as f:
    json.dump(all_companies, f, indent=2)

with open('/workspace/quick_screen/frappe_all_facts.json', 'w') as f:
    json.dump(all_facts, f, indent=2)

print(f"Total companies to create: {len(all_companies)}")
print(f"Total facts to create: {len(all_facts)}")
print("\nFirst 3 companies:")
for c in all_companies[:3]:
    print(f"  - {c['listing_id']}: {c['company_name']}")
print(f"\nFacts per system: ~{len(all_facts) / len(all_companies):.1f} avg")
