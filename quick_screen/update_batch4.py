#!/usr/bin/env python3
"""Update batch 4 (systems 31-40) with audit scan findings."""

import pandas as pd

BATCH4_UPDATES = {
    "KERN COUNTY HOSPITAL AUTHORITY": {
        "has_equities": "no",
        "has_captive": "no",
        "is_target": True,
        "source_url": "https://www.kernmedical.com/documents/Kern-County-Hospital-Authority-FY-2024-Audited-FS-Final-12.23.24.pdf"
    },
    "TAHOE FOREST HOSPITAL DISTRICT": {
        "has_equities": "no",  # De minimis equity ($102k = 0.1% of portfolio, essentially fixed income)
        "has_captive": "no",
        "is_target": True,
        "source_url": "https://www.tfhd.com/wp-content/uploads/2025/09/0.-Tahoe-Forest-Hospital-District-6-30-24-FS-Issued-10-29-24.pdf"
    },
    "QUEEN OF THE VALLEY MEDICAL CENTER": {
        "has_equities": "yes",
        "has_captive": "yes",
        "captive_name": "Providence Assurance Inc",
        "is_target": False,
        "source_url": "https://www.providence.org/about/financial-statements"
    },
    "SUTTER MEDICAL CENTER SACRAMENTO": {
        "has_equities": "yes",
        "has_captive": "no",
        "is_target": False,
        "source_url": "https://emma.msrb.org/P11855694.pdf"
    },
    "CHILDRENS HOSPITAL LOS ANGELES": {
        "has_equities": "yes",
        "equity_pct": 51.0,  # 33.5% US + 17.5% non-US equity target
        "has_captive": "no",
        "is_target": False,
        "source_url": "https://emma.msrb.org/P11827180.pdf"
    }
}

def update_csv():
    df = pd.read_csv('/workspace/quick_screen/quick_screen_tx_ca.csv')
    
    for system_name, updates in BATCH4_UPDATES.items():
        mask = df['system_name'].str.upper() == system_name.upper()
        if mask.any():
            for field, value in updates.items():
                df.loc[mask, field] = value
            print(f"Updated: {system_name}")
        else:
            print(f"NOT FOUND: {system_name}")
    
    df.to_csv('/workspace/quick_screen/quick_screen_tx_ca.csv', index=False)
    
    # Count targets
    targets = df[df['is_target'] == True]
    print(f"\nTotal targets: {len(targets)}")
    for _, t in targets.iterrows():
        print(f"  - {t['system_name']} ({t['state']}): ${t['total_cash_investments']:,.0f}")

if __name__ == "__main__":
    update_csv()
