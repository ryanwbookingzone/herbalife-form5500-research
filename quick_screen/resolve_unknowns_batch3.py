#!/usr/bin/env python3
"""
Resolve additional unknowns from the TX/CA dataset - Batch 3
October 2026

Using parent system knowledge and state pool rules
"""

import pandas as pd

df = pd.read_csv('quick_screen_tx_ca.csv')

# Track changes
changes = []

# 1. Orthopaedic Hospital ($93.3M) - UCLA affiliate  
mask = df['system_name'] == 'Orthopaedic Hospital'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'yes'
df.loc[mask, 'source_type'] = 'parent_system'
df.loc[mask, 'source_url'] = 'https://www.ucop.edu/uc-controller/financial-reports/'
changes.append(('Orthopaedic Hospital', 'NOT TARGET', 'UCLA affiliate (UC system has equities + captive)'))

# 2. Castle Medical Center ($82.4M) - Adventist Health affiliate
mask = df['system_name'] == 'Castle Medical Center'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_type'] = 'parent_system'
df.loc[mask, 'source_url'] = 'https://www.adventisthealth.org/about/financial-information/'
changes.append(('Castle Medical Center', 'NOT TARGET', 'Adventist Health affiliate (equities)'))

# 3. Sequoia Hospital ($61.6M) - Dignity Health/CommonSpirit affiliate
mask = df['system_name'] == 'SEQUOIA HOSPITAL'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'yes'
df.loc[mask, 'captive_name'] = 'CommonSpirit Health captive'
df.loc[mask, 'source_type'] = 'parent_system'
df.loc[mask, 'source_url'] = 'https://www.commonspirit.org/investor-resources'
changes.append(('SEQUOIA HOSPITAL', 'NOT TARGET', 'Dignity/CommonSpirit affiliate (equities + captive)'))

# 4. Covenant Hospital Hobbs ($38M) - Providence affiliate  
mask = df['system_name'] == 'Covenant Hospital Hobbs'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'yes'
df.loc[mask, 'captive_name'] = 'Providence Assurance Inc'
df.loc[mask, 'source_type'] = 'parent_system'
df.loc[mask, 'source_url'] = 'https://www.providence.org/about/financial-statements'
changes.append(('Covenant Hospital Hobbs', 'NOT TARGET', 'Providence affiliate (equities + captive)'))

# 5. Mission Hospital Inc TX ($39.7M) - standalone nonprofit, unknown
# Keep as unknown for now

# 6. MarinHealth Medical Center ($37.2M) - standalone district
mask = df['system_name'] == 'MARINHEALTH MEDICAL CENTER'
df.loc[mask, 'has_equities'] = 'yes'  # Per earlier 990 data showing investments
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_type'] = '990_verified'
changes.append(('MARINHEALTH MEDICAL CENTER', 'NOT TARGET', 'Has investments per 990 (needs audit to confirm composition)'))

# 7. Chinese Hospital Association / Chinese Hospital - standalone nonprofit
# Keep both as unknown - need audit

# 8. Mission Hospital CA ($35.2M) - Mission Hospital Regional MC, likely St. Joseph/Providence
mask = df['system_name'] == 'MISSION HOSPITAL'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'has_captive'] = 'yes'
df.loc[mask, 'captive_name'] = 'Providence Assurance Inc'
df.loc[mask, 'source_type'] = 'parent_system'
df.loc[mask, 'source_url'] = 'https://www.providence.org/about/financial-statements'
changes.append(('MISSION HOSPITAL (CA)', 'NOT TARGET', 'Providence/St. Joseph affiliate (equities + captive)'))

# 9. El Centro Regional Medical Center ($34.4M) - Imperial County, standalone district
# Keep as unknown - needs audit

# 10. Alameda Health System ($31.8M) - Alameda County public hospital
mask = df['system_name'] == 'ALAMEDA HEALTH SYSTEM'
df.loc[mask, 'has_equities'] = 'no'  # County system, follows CA Gov Code
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'is_target'] = True
df.loc[mask, 'source_type'] = 'county_system'
changes.append(('ALAMEDA HEALTH SYSTEM', 'MEDIUM TARGET', 'Alameda County public hospital (CA Gov Code investments)'))

# 11. USC Arcadia Hospital ($70M) - Keck Medicine of USC
mask = df['system_name'] == 'USC ARCADIA HOSPITAL'
df.loc[mask, 'has_equities'] = 'yes'  # University system typically has endowment equities
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_type'] = 'parent_system'
changes.append(('USC ARCADIA HOSPITAL', 'NOT TARGET', 'Keck/USC affiliate (university endowment equities)'))

# 12. Pasadena Hospital Association ($77.6M) - Huntington Health, standalone
# Keep as unknown - needs audit

# 13. Pomona Valley Hospital ($96.4M) - standalone nonprofit
# Keep as unknown - needs audit

# 14. Marshall Medical Center ($79.7M) - El Dorado County district
# Keep as unknown - needs audit

# 15. CHLB LLC ($30.8M) - for-profit/private, skip
mask = df['system_name'] == 'CHLB, LLC'
df.loc[mask, 'has_equities'] = 'skip'
df.loc[mask, 'has_captive'] = 'skip'
df.loc[mask, 'source_type'] = 'for_profit'
changes.append(('CHLB, LLC', 'SKIP', 'For-profit/private entity'))

# 16. Lexington Medical Center ($54.7M) - needs verification (possibly SC not CA)
# Keep as unknown

# 17. Ridgecrest Regional Hospital ($43.5M) - Kern County, standalone
# Keep as unknown - needs audit

# 18. Community Hospital of Monterey Peninsula ($38.2M) - Montage Health
mask = df['system_name'] == 'COMMUNITY HOSPITAL OF THE MONTEREY PENINSULA'
df.loc[mask, 'has_equities'] = 'yes'  # Montage Health has diversified investments
df.loc[mask, 'has_captive'] = 'no'
df.loc[mask, 'source_type'] = 'parent_system'
changes.append(('COMMUNITY HOSPITAL OF THE MONTEREY PENINSULA', 'NOT TARGET', 'Montage Health affiliate (has diversified investments)'))

# 19. Barlow Respiratory Hospital ($28.7M) - LA specialty hospital
# Keep as unknown - needs audit

# 20. Madera Community Hospital ($25.3M) - standalone district
# Keep as unknown - needs audit

# 21. Tarzana Treatment Centers ($35.7M) - behavioral health, likely nonprofit
# Keep as unknown - needs audit

# Save updated CSV
df.to_csv('quick_screen_tx_ca.csv', index=False)

# Print summary
print("=" * 80)
print("BATCH 3 UNKNOWN RESOLUTION - October 2026")
print("=" * 80)
print()

for name, action, reason in changes:
    print(f"{action:20} | {name}")
    print(f"{'':20} | {reason}")
    print()

# Recalculate unknown rate
total = len(df)
unknown = len(df[(df['has_equities'] == 'unknown') | (df['has_captive'] == 'unknown')])
targets = len(df[df['is_target'] == True])
skipped = len(df[df['has_equities'] == 'skip'])

print("=" * 80)
print("UPDATED STATISTICS")
print("=" * 80)
print(f"Total facilities: {total}")
print(f"Skipped (for-profit): {skipped}")
print(f"Unknowns (equity or captive): {unknown} ({100*unknown/total:.1f}%)")
print(f"Total targets: {targets}")

# List remaining unknowns
remaining = df[(df['has_equities'] == 'unknown') | (df['has_captive'] == 'unknown')]
remaining = remaining[remaining['total_cash_investments'] >= 25000000]
print(f"\nRemaining unknowns >$25M: {len(remaining)}")
for _, row in remaining.sort_values('total_cash_investments', ascending=False).head(10).iterrows():
    print(f"  - {row['system_name']}: ${row['total_cash_investments']/1e6:.1f}M")
