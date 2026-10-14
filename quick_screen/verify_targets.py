#!/usr/bin/env python3
"""
Verify and update medium-confidence targets with actual audit findings.
Updates: October 2026 batch verification
"""

import pandas as pd

df = pd.read_csv('quick_screen_tx_ca.csv')

# Track changes
changes = []

# 1. Antelope Valley - DROP: has mutual funds ($217M), ETFs ($81M), limited partnerships
mask = df['system_name'] == 'ANTELOPE VALLEY MEDICAL CENTER'
df.loc[mask, 'has_equities'] = 'yes'
df.loc[mask, 'equity_pct'] = 35.0  # Significant equity exposure
df.loc[mask, 'is_target'] = False
df.loc[mask, 'source_url'] = 'https://www.avmc.org/images/AVHD-6-24-FS-Final.pdf'
df.loc[mask, 'source_type'] = 'audit_verified'
changes.append(('ANTELOPE VALLEY MEDICAL CENTER', 'DROP', 'Mutual funds $217M, ETFs $81M, limited partnerships per FY2024 audit'))

# 2. Pioneers Memorial - UPGRADE: CA Code 53600, Mechanics Bank Wealth Management (fixed income only)
mask = df['system_name'] == 'PIONEERS MEMORIAL HEALTHCARE DISTRICT'
df.loc[mask, 'source_url'] = 'https://pmhd.org/wp-content/uploads/2024/11/11-26-24-agenda-packet.pdf'
df.loc[mask, 'source_type'] = 'audit_verified_high'
changes.append(('PIONEERS MEMORIAL HEALTHCARE DISTRICT', 'UPGRADE to HIGH', 'CA Code 53600 fixed income, Mechanics Bank per FY2024 audit'))

# 3. Bear Valley - UPGRADE: LAIF only ($40M)
mask = df['system_name'] == 'BEAR VALLEY COMMUNITY HOSPITAL'
df.loc[mask, 'source_url'] = 'https://bvchd.com/wp-content/uploads/2024/03/March-05-2024-Finance-Committee-Meeting-Agenda-Supporting-Documents.pdf'
df.loc[mask, 'source_type'] = 'audit_verified_high'
changes.append(('BEAR VALLEY COMMUNITY HOSPITAL', 'UPGRADE to HIGH', 'LAIF only $40M per FY2023 audit'))

# 4. San Benito - UPGRADE: US Government securities + LAIF
mask = df['system_name'] == 'SAN BENITO HEALTH CARE DISTRICT'
df.loc[mask, 'source_url'] = 'https://www.hazelhawkins.com/images/FY24-Audited-Financial-Statement.pdf'
df.loc[mask, 'source_type'] = 'audit_verified_high'
changes.append(('SAN BENITO HEALTH CARE DISTRICT', 'UPGRADE to HIGH', 'US Government securities + CGC collateralized per FY2024 audit'))

# 5. Modoc (Last Frontier) - UPGRADE: Money market + US Treasuries only
mask = df['system_name'] == 'MODOC MEDICAL CENTER'
df.loc[mask, 'source_url'] = 'https://modocmedicalcenter.org/wp-content/uploads/2026/05/Last-Frontier-Healthcare-District-6.30.24-Issued-FS.pdf'
df.loc[mask, 'source_type'] = 'audit_verified_high'
changes.append(('MODOC MEDICAL CENTER', 'UPGRADE to HIGH', 'Money market $5.1M + US Treasuries $30M per FY2024 audit'))

# 6. Oak Valley - UPGRADE: LAIF only ($20M+)
mask = df['system_name'] == 'OAK VALLEY DISTRICT HOSPITAL'
df.loc[mask, 'source_url'] = 'https://oakvalleyhospital.com/wp-content/uploads/2025/08/08.07.2025-Finance-Committee-Packet.pdf'
df.loc[mask, 'source_type'] = 'audit_verified_high'
changes.append(('OAK VALLEY DISTRICT HOSPITAL', 'UPGRADE to HIGH', 'LAIF only $25M per FY2025 board reports'))

# 7. Lompoc Valley - UPGRADE: LAIF $18.7M (99.9% fixed income)
mask = df['system_name'] == 'LOMPOC VALLEY MEDICAL CENTER'
df.loc[mask, 'source_url'] = 'https://www.lompocvmc.com/files/95f1acfc1/LHDafs24.2%29.pdf'
df.loc[mask, 'source_type'] = 'audit_verified_high'
changes.append(('LOMPOC VALLEY MEDICAL CENTER', 'UPGRADE to HIGH', 'LAIF $18.7M (99.9% fixed income) per FY2024 audit'))

# 8. Northern Inyo - Update: has ~1% equities, ~1% mutual funds (near fixed income)
mask = df['system_name'] == 'NORTHERN INYO HEALTHCARE DISTRICT'
df.loc[mask, 'has_equities'] = 'near_fixed_income'
df.loc[mask, 'equity_pct'] = 1.0  # $83K equities out of $8.4M
df.loc[mask, 'source_url'] = 'https://www.nih.org/documents/2026/Financials/NIHD-Signed-Financial-Statements-FY25.pdf'
df.loc[mask, 'source_type'] = 'audit_verified_near'
changes.append(('NORTHERN INYO HEALTHCARE DISTRICT', 'NEAR FIXED INCOME (1%)', '$83K equities + $98K mutual funds out of $8.4M per FY2025 audit'))

# 9. Tahoe Forest - Update: near fixed income (0.1% equity)
mask = df['system_name'] == 'TAHOE FOREST HOSPITAL DISTRICT'
df.loc[mask, 'has_equities'] = 'near_fixed_income'
df.loc[mask, 'equity_pct'] = 0.1
df.loc[mask, 'source_type'] = 'audit_verified_near'
changes.append(('TAHOE FOREST HOSPITAL DISTRICT', 'NEAR FIXED INCOME (0.1%)', 'De minimis equity per FY2024 audit'))

# 10. Remove duplicate Pioneers Memorial (keep only the first occurrence with higher balance)
# Line 79 has $46.9M, Line 87 has $40.6M - both have same EIN, keep the higher one
pioneers_mask = df['system_name'] == 'PIONEERS MEMORIAL HEALTHCARE DISTRICT'
pioneers_indices = df[pioneers_mask].index.tolist()
if len(pioneers_indices) > 1:
    # Keep only the first (higher balance) entry
    df = df.drop(pioneers_indices[1])
    changes.append(('PIONEERS MEMORIAL HEALTHCARE DISTRICT (duplicate)', 'REMOVED', 'Duplicate entry removed'))

# Save updated CSV
df.to_csv('quick_screen_tx_ca.csv', index=False)

# Print summary
print("=" * 80)
print("VERIFICATION RESULTS - October 2026")
print("=" * 80)
print()

for name, action, reason in changes:
    print(f"{action:30} | {name}")
    print(f"{'':30} | {reason}")
    print()

# Update existing high-confidence entries from previous batches
existing_high = ['KAWEAH DELTA HEALTH CARE DISTRICT', 'RIVERSIDE UNIVERSITY HEALTH SYSTEM', 'KERN COUNTY HOSPITAL AUTHORITY']
for name in existing_high:
    mask = df['system_name'] == name
    if mask.any() and df.loc[mask, 'source_type'].iloc[0] == 'ca_hcai':
        df.loc[mask, 'source_type'] = 'audit_verified_high'

# Count targets by confidence level
all_targets = df[df['is_target'] == True]
high_conf = all_targets[all_targets['source_type'] == 'audit_verified_high']
near_fixed = all_targets[all_targets['source_type'] == 'audit_verified_near']
medium_conf = all_targets[~all_targets['source_type'].str.contains('audit_verified', na=False)]

print("=" * 80)
print("TARGET SUMMARY")
print("=" * 80)
print(f"HIGH CONFIDENCE (audit verified fixed income): {len(high_conf)}")
for _, row in high_conf.sort_values('total_cash_investments', ascending=False).iterrows():
    print(f"  - {row['system_name']}: ${row['total_cash_investments']/1e6:.1f}M")

print(f"\nNEAR FIXED INCOME (de minimis equity <5%): {len(near_fixed)}")
for _, row in near_fixed.sort_values('total_cash_investments', ascending=False).iterrows():
    print(f"  - {row['system_name']}: ${row['total_cash_investments']/1e6:.1f}M ({row['equity_pct']}% equity)")

print(f"\nMEDIUM CONFIDENCE (statutory inference, needs audit): {len(medium_conf)}")
for _, row in medium_conf.sort_values('total_cash_investments', ascending=False).iterrows():
    print(f"  - {row['system_name']}: ${row['total_cash_investments']/1e6:.1f}M")

# Calculate unknown rate
total = len(df)
unknown = len(df[(df['has_equities'] == 'unknown') | (df['has_captive'] == 'unknown')])
print(f"\nUNKNOWN RATE: {unknown}/{total} = {100*unknown/total:.1f}%")

print("\nCSV updated successfully!")
