#!/usr/bin/env python3
"""Update batch 2 (systems 11-20) with audit scan results."""

import csv

BATCH2_UPDATES = {
    "KAWEAH DELTA HEALTH CARE DISTRICT": {
        "has_equities": "no",
        "has_captive": "no",
        "is_target": True,  # NO equities, NO captive, >$25M
        "source_url": "https://www.kaweahhealth.org/about-us/board-of-directors/audited-financials/"
    },
    "Covenant Medical Center": {
        "has_equities": "yes",  # Providence audit shows equity securities
        "has_captive": "yes",  # Providence Assurance, Inc.
        "captive_name": "Providence Assurance Inc",
        "is_target": False,
        "source_url": "https://www.providence.org/about/financial-statements"
    },
    "RIVERSIDE UNIVERSITY HEALTH SYSTEM": {
        "has_equities": "no",  # County ACFR shows only LAIF (fixed income)
        "has_captive": "no",  # No captive in County structure
        "is_target": True,  # NO equities, NO captive, >$25M
        "source_url": "https://auditorcontroller.org/reports-and-publications"
    },
    "UCI HEALTH - FOUNTAIN VALLEY": {
        "has_equities": "yes",  # UC Medical Centers audit shows equity securities
        "has_captive": "yes",  # Wholly owned captive insurance company
        "is_target": False,
        "source_url": "https://www.ucop.edu/uc-controller/financial-reports/"
    },
    "ST. JOSEPH HOSPITAL": {
        "has_equities": "yes",  # Providence audit shows equity securities
        "has_captive": "yes",  # Providence Assurance, Inc.
        "captive_name": "Providence Assurance Inc",
        "is_target": False,
        "source_url": "https://www.providence.org/about/financial-statements"
    },
    "WASHINGTON TOWNSHIP HEALTHCARE DISTRICT": {
        "has_equities": "yes",  # Audit shows domestic/international equity funds
        "has_captive": "no",  # No captive found
        "is_target": False,
        "source_url": "https://www.washingtonhealth.com/about-us/board-of-directors/audited-financials/"
    },
    "Christus Spohn Health System Corporation": {
        "has_equities": "yes",  # CHRISTUS audit shows equity securities
        "has_captive": "yes",  # Emerald Assurance Cayman Ltd
        "captive_name": "Emerald Assurance Cayman Ltd",
        "captive_domicile": "Cayman Islands",
        "is_target": False,
        "source_url": "https://app.lla.state.la.us/PublicReports.nsf/"
    },
    "SIERRA NEVADA MEMORIAL MINERS  HOSPITAL INC": {
        "has_equities": "yes",  # Adventist Health audit shows private equity funds
        "has_captive": "no",  # No captive found
        "is_target": False,
        "source_url": "https://www.adventisthealth.org/documents/system/Adventist-Health-Annual-Filing-12-31-24.pdf"
    },
    "SONORA COMMUNITY HOSPITAL": {
        "has_equities": "yes",  # Adventist Health audit shows private equity funds
        "has_captive": "no",  # No captive found
        "is_target": False,
        "source_url": "https://www.adventisthealth.org/documents/system/Adventist-Health-Annual-Filing-12-31-24.pdf"
    },
    "CALIFORNIA HOSPITAL MEDICAL CENTER": {
        "has_equities": "yes",  # CommonSpirit audit shows equity securities
        "has_captive": "yes",  # CommonSpirit has captive insurance companies
        "is_target": False,
        "source_url": "https://www.commonspirit.org/investor-resources"
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
            
            if name in BATCH2_UPDATES:
                updates = BATCH2_UPDATES[name]
                for k, v in updates.items():
                    row[k] = v
                updated_count += 1
                print(f"Updated: {name}")
            
            rows.append(row)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\nUpdated {updated_count} systems in batch 2")
    
    # Show targets
    targets = [r for r in rows if r.get('is_target') == 'True' or r.get('is_target') == True]
    print(f"Total targets: {len(targets)}")
    for t in targets:
        print(f"  - {t['system_name']} ({t['state']}): ${float(t['total_cash_investments'])/1e6:.1f}M")

if __name__ == '__main__':
    main()
