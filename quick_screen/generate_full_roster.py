#!/usr/bin/env python3
"""
Generate comprehensive roster of all systems reviewed.
"""

import pandas as pd

df = pd.read_csv('/workspace/quick_screen/quick_screen_tx_ca.csv')

# Add Frappe record column
df['frappe_company_listing'] = ''
df['frappe_facts_count'] = 0

# Generate roster
roster_cols = [
    'system_name', 'state', 'system_type', 'total_cash_investments', 
    'has_equities', 'has_captive', 'is_target',
    'total_self_insurance_reserves', 'self_insurance_trust_balance',
    'source_type', 'source_url', 'frappe_company_listing'
]

# Create roster DataFrame
roster = df[roster_cols].copy()

# Format for readability
roster['cash_investments_m'] = roster['total_cash_investments'].apply(
    lambda x: f"${x/1e6:.1f}M" if pd.notna(x) and x > 0 else ""
)
roster['si_reserves_m'] = roster['total_self_insurance_reserves'].apply(
    lambda x: f"${x/1e6:.2f}M" if pd.notna(x) and x > 0 else ""
)
roster['si_trust_m'] = roster['self_insurance_trust_balance'].apply(
    lambda x: f"${x/1e6:.2f}M" if pd.notna(x) and x > 0 else ""
)

# Save full roster
roster_export = roster[[
    'system_name', 'state', 'system_type', 'cash_investments_m', 
    'has_equities', 'has_captive', 'is_target',
    'si_reserves_m', 'si_trust_m', 'source_type', 'source_url'
]]

roster_export.to_csv('/workspace/quick_screen/full_roster.csv', index=False)

# Print summary
print("="*100)
print("FULL ROSTER SUMMARY")
print("="*100)

print(f"\nTotal systems reviewed: {len(df)}")
print(f"  - California: {len(df[df['state'] == 'CA'])}")
print(f"  - Texas: {len(df[df['state'] == 'TX'])}")

targets = df[df['is_target'] == True]
print(f"\nTotal TARGETS: {len(targets)}")
print(f"  - CA targets: {len(targets[targets['state'] == 'CA'])}")
print(f"  - TX targets: {len(targets[targets['state'] == 'TX'])}")

total_cash = targets['total_cash_investments'].sum()
print(f"\nTotal cash+investments (targets): ${total_cash/1e9:.2f}B")

total_si = targets['total_self_insurance_reserves'].sum()
print(f"Total self-insurance reserves (targets): ${total_si/1e6:.1f}M")

total_trust = targets['self_insurance_trust_balance'].sum()
print(f"Total SI trust balances (targets): ${total_trust/1e6:.1f}M")

# Count by confidence level
print(f"\nConfidence breakdown:")
for conf in df['source_type'].dropna().unique():
    count = len(df[df['source_type'] == conf])
    print(f"  - {conf}: {count}")

print(f"\nRoster saved to: /workspace/quick_screen/full_roster.csv")

# Print target list
print("\n" + "="*100)
print("ALL TARGETS (Fixed Income, No Captive)")
print("="*100)
print(f"\n{'System':<45} {'State':>6} {'Cash+Inv':>12} {'SI Reserves':>12} {'Confidence':>18}")
print("-"*95)

for _, row in targets.sort_values('total_cash_investments', ascending=False).iterrows():
    name = row['system_name'][:44]
    state = row['state']
    cash = f"${row['total_cash_investments']/1e6:.0f}M" if pd.notna(row['total_cash_investments']) else ""
    si = f"${row['total_self_insurance_reserves']/1e6:.1f}M" if pd.notna(row['total_self_insurance_reserves']) and row['total_self_insurance_reserves'] > 0 else "-"
    conf = str(row['source_type'])[:17] if pd.notna(row['source_type']) else ""
    print(f"{name:<45} {state:>6} {cash:>12} {si:>12} {conf:>18}")

if __name__ == "__main__":
    pass
