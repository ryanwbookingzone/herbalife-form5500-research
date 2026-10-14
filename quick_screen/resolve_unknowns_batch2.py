#!/usr/bin/env python3
"""
Resolve additional unknowns from the TX/CA dataset - Batch 2
October 2026
"""

import pandas as pd

df = pd.read_csv('quick_screen_tx_ca.csv')

# Track changes
changes = []

# 1. Community Memorial Health System - has $67.3M publicly traded securities
mask = df['system_name'] == 'Community Memorial Health System'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_url'] = 'https://siviq.co/nonprofits/organizations/951683892'
df.loc[mask, 'source_type'] = '990_verified'
changes.append(('Community Memorial Health System', 'NOT TARGET', '$67.3M publicly traded securities per 2024 990'))

# 2. Casa Colina - has $106M marketable securities
mask = df['system_name'] == 'CASA COLINA HOSPITAL AND CENTERS FOR HEALTHCARE'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_url'] = 'https://emma.msrb.org/P21602838-P21236085-.pdf'
df.loc[mask, 'source_type'] = 'emma_verified'
changes.append(('CASA COLINA HOSPITAL', 'NOT TARGET', '$106M marketable securities per FY2022 EMMA'))

# 3. Contra Costa Regional Medical Center - county pool (AAAf/S1+ fixed income)
mask = df['system_name'] == 'CONTRA COSTA REGIONAL MEDICAL CENTER'
df.loc[mask, 'has_equities'] = 'no'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'is_target'] = True
df.loc[mask, 'source_url'] = 'https://www.contracosta.ca.gov/DocumentCenter/View/83766/FY24-25-Adopted-Budget-Book'
df.loc[mask, 'source_type'] = 'county_pool_verified'
changes.append(('CONTRA COSTA REGIONAL MEDICAL CENTER', 'MEDIUM TARGET', 'County Investment Pool AAAf/S1+ (CA Gov Code, fixed income)'))

# 4. Henry Mayo Newhall Memorial Hospital - has equity securities per audit
mask = df['system_name'] == 'HENRY MAYO NEWHALL MEMORIAL HOSPITAL'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_url'] = 'https://emma.msrb.org/P21900828.pdf'
df.loc[mask, 'source_type'] = 'emma_verified'
changes.append(('HENRY MAYO NEWHALL MEMORIAL HOSPITAL', 'NOT TARGET', '$119M+ publicly traded securities incl. equity per FY2024'))

# 5. San Joaquin Community Hospital - Adventist Health affiliate (has equities)
mask = df['system_name'] == 'SAN JOAQUIN COMMUNITY HOSPITAL CORP'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_url'] = 'https://www.adventisthealth.org/about/financial-information/'
df.loc[mask, 'source_type'] = 'parent_system'
changes.append(('SAN JOAQUIN COMMUNITY HOSPITAL CORP', 'NOT TARGET', 'Adventist Health affiliate (parent has equities)'))

# 6. Pomona Valley Hospital - check if nonprofit or district
mask = df['system_name'] == 'POMONA VALLEY HOSPITAL MEDICAL CENTER'
df.loc[mask, 'has_equities'] = 'unknown'
df.loc[mask, 'has_captive'] = 'unknown'
changes.append(('POMONA VALLEY HOSPITAL MEDICAL CENTER', 'STILL UNKNOWN', 'Needs audit verification'))

# 7. Saint Agnes Medical Center - CommonSpirit affiliate (has captive)
mask = df['system_name'] == 'SAINT AGNES MEDICAL CENTER'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'yes'
df.loc[mask, 'captive_name'] = 'CommonSpirit Health captive'
df.loc[mask, 'source_url'] = 'https://www.commonspirit.org/investor-resources'
df.loc[mask, 'source_type'] = 'parent_system'
changes.append(('SAINT AGNES MEDICAL CENTER', 'NOT TARGET', 'CommonSpirit Health affiliate (equities + captive)'))

# 8. Goleta Valley Cottage Hospital - Cottage Health affiliate
mask = df['system_name'] == 'GOLETA VALLEY COTTAGE HOSPITAL'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_url'] = 'https://www.cottagehealth.org/about/financial/'
df.loc[mask, 'source_type'] = 'parent_system'
changes.append(('GOLETA VALLEY COTTAGE HOSPITAL', 'NOT TARGET', 'Cottage Health affiliate (parent has equities)'))

# 9. Marshall Medical Center - independent district, needs audit
mask = df['system_name'] == 'MARSHALL MEDICAL CENTER'
df.loc[mask, 'has_equities'] = 'unknown'
df.loc[mask, 'has_captive'] = 'no'
changes.append(('MARSHALL MEDICAL CENTER', 'STILL UNKNOWN', 'Independent district - needs audit'))

# 10. Oroville Hospital - Adventist Health affiliate (has equities)
mask = df['system_name'] == 'OROVILLE HOSPITAL'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_url'] = 'https://www.adventisthealth.org/about/financial-information/'
df.loc[mask, 'source_type'] = 'parent_system'
changes.append(('OROVILLE HOSPITAL', 'NOT TARGET', 'Adventist Health affiliate (parent has equities)'))

# Save updated CSV
df.to_csv('quick_screen_tx_ca.csv', index=False)

# Print summary
print("=" * 80)
print("BATCH 2 UNKNOWN RESOLUTION - October 2026")
print("=" * 80)
print()

for name, action, reason in changes:
    print(f"{action:20} | {name}")
    print(f"{'':20} | {reason}")
    print()

# Recalculate unknown rate
total = len(df)
unknown_equity = len(df[df['has_equities'] == 'unknown'])
unknown_captive = len(df[df['has_captive'] == 'unknown'])
unknown = len(df[(df['has_equities'] == 'unknown') | (df['has_captive'] == 'unknown')])
targets = len(df[df['is_target'] == True])

print("=" * 80)
print("UPDATED STATISTICS")
print("=" * 80)
print(f"Total facilities: {total}")
print(f"Unknowns (equity or captive): {unknown} ({100*unknown/total:.1f}%)")
print(f"  - Unknown equity: {unknown_equity}")
print(f"  - Unknown captive: {unknown_captive}")
print(f"Total targets: {targets}")
print()
print("CSV updated successfully!")
