#!/usr/bin/env python3
"""Update batch 3 (systems 21-30) with audit scan results."""

import csv

BATCH3_UPDATES = {
    "CITY OF HOPE HELFORD RESEARCH HOSPITAL": {
        "has_equities": "yes",  # City of Hope audit shows equity securities, private equity funds
        "has_captive": "no",  # No captive found
        "is_target": False,
        "source_url": "https://www.cityofhope.org/about-city-of-hope/who-we-are/financials"
    },
    "SUTTER WEST BAY HOSPITALS": {
        "has_equities": "yes",  # Sutter Health audit shows equity securities, commingled equity funds
        "has_captive": "no",  # No captive found
        "is_target": False,
        "source_url": "https://edge.sitecorecloud.io/sutterhealt962c-sutterhealt8fce-production57cc-4860/media/Project/SutterHealth/SutterHealth/PDF/about/sutter-health-financials-2024.pdf"
    },
    "Marin General Hospital": {
        "has_equities": "yes",  # Marin audit shows equity securities (3%)
        "has_captive": "no",  # No captive found
        "is_target": False,
        "source_url": "https://www.marinhealthcare.org/financial-reports/"
    },
    "LOS ANGELES GENERAL MEDICAL CENTER": {
        "has_equities": "yes",  # LA County/LACERA has equity securities in pool
        "has_captive": "no",  # County self-insures, no captive
        "is_target": False,
        "source_url": "https://auditor.lacounty.gov/wp-content/uploads/2025/01/Annual-Comprehensive-Financial-Report-FY-2023-2024.pdf"
    },
    "LOS ANGELES COUNTY OLIVE VIEW-UCLA MEDICAL CENTER": {
        "has_equities": "yes",  # LA County/LACERA has equity securities in pool
        "has_captive": "no",  # County self-insures, no captive
        "is_target": False,
        "source_url": "https://auditor.lacounty.gov/wp-content/uploads/2025/01/Annual-Comprehensive-Financial-Report-FY-2023-2024.pdf"
    },
    "NORTHRIDGE HOSPITAL MEDICAL CENTER": {
        "has_equities": "yes",  # CommonSpirit audit shows equity securities
        "has_captive": "yes",  # CommonSpirit has offshore/onshore captives
        "is_target": False,
        "source_url": "https://www.commonspirit.org/investor-resources"
    },
    "St Mary Medical Center": {
        "has_equities": "yes",  # Providence audit shows equity securities
        "has_captive": "yes",  # Providence Assurance Inc
        "captive_name": "Providence Assurance Inc",
        "is_target": False,
        "source_url": "https://www.providence.org/about/financial-statements"
    },
}

def main():
    input_path = "quick_screen_tx_ca.csv"
    output_path = "quick_screen_tx_ca.csv"
    
    rows = []
    updated_count = 0
    
    with open(input_path, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            name = row['system_name']
            
            if name in BATCH3_UPDATES:
                updates = BATCH3_UPDATES[name]
                for k, v in updates.items():
                    row[k] = v
                updated_count += 1
                print(f"Updated: {name}")
            
            rows.append(row)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\nUpdated {updated_count} systems in batch 3")
    
    # Show targets
    targets = [r for r in rows if r.get('is_target') == 'True' or r.get('is_target') == True]
    print(f"Total targets: {len(targets)}")
    for t in targets:
        print(f"  - {t['system_name']} ({t['state']}): ${float(t['total_cash_investments'])/1e6:.1f}M")

if __name__ == '__main__':
    main()
