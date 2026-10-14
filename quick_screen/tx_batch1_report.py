#!/usr/bin/env python3
"""
Generate Texas Hospital Districts Batch 1 Report
"""

import pandas as pd

df = pd.read_csv('/workspace/quick_screen/quick_screen_tx_ca.csv')

# Filter for TX hospital districts
tx_districts = df[
    (df['state'] == 'TX') & 
    (df['system_type'] == 'hospital_district')
].copy()

print("\n" + "="*200)
print("TEXAS BIG HOSPITAL DISTRICTS - BATCH 1 COMPREHENSIVE REPORT")
print("="*200)
print(f"\nTotal TX Hospital Districts Processed: {len(tx_districts)}")
print(f"Targets (Fixed Income, No Captive): {len(tx_districts[tx_districts['is_target'] == True])}")
print(f"Non-Targets: {len(tx_districts[tx_districts['is_target'] == False])}")

print("\n" + "-"*200)
print("TARGETS - ELIGIBLE FOR CAPTIVE INSURANCE")
print("-"*200)

targets = tx_districts[tx_districts['is_target'] == True].sort_values('total_cash_investments', ascending=False)

for _, row in targets.iterrows():
    print(f"\n{'='*100}")
    print(f"SYSTEM: {row['system_name']}")
    print(f"{'='*100}")
    print(f"  Operating Cash + Investments: ${row['total_cash_investments']/1e6:,.1f}M")
    print(f"  As of Date: {row['as_of_date']}")
    print(f"  Equities: {row['has_equities'].upper()}")
    print(f"  Captive: {row['has_captive'].upper()}")
    print(f"  Source Type: {row['source_type']}")
    print(f"  Source URL: {row['source_url']}")
    print(f"  Source Page: {row['source_page']}")
    print(f"\n  SELF-INSURANCE RESERVES:")
    print(f"    Professional/General Liability: ${row['professional_liability_reserve']/1e6:.2f}M" if pd.notna(row['professional_liability_reserve']) else "    Professional/General Liability: --")
    print(f"    Workers Comp: ${row['workers_comp_reserve']/1e6:.2f}M" if pd.notna(row['workers_comp_reserve']) else "    Workers Comp: --")
    print(f"    Employee Health IBNR: ${row['employee_health_ibnr']/1e6:.2f}M" if pd.notna(row['employee_health_ibnr']) else "    Employee Health IBNR: --")
    print(f"    TOTAL SELF-INSURANCE: ${row['total_self_insurance_reserves']/1e6:.2f}M" if pd.notna(row['total_self_insurance_reserves']) else "    TOTAL SELF-INSURANCE: --")
    print(f"    SI Trust Balance: ${row['self_insurance_trust_balance']/1e6:.2f}M" if pd.notna(row['self_insurance_trust_balance']) else "    SI Trust Balance: --")
    print(f"    SI Source: {row['si_source_url']}")
    print(f"    SI Page: {row['si_source_page']}")
    print(f"    Notes: {row['si_notes']}")

print("\n\n" + "-"*200)
print("NON-TARGETS - EXCLUDED (HAS EQUITIES OR NO HOSPITAL OPERATIONS)")
print("-"*200)

non_targets = tx_districts[tx_districts['is_target'] == False].sort_values('total_cash_investments', ascending=False)

for _, row in non_targets.iterrows():
    print(f"\n{'='*100}")
    print(f"SYSTEM: {row['system_name']} -- EXCLUDED")
    print(f"{'='*100}")
    print(f"  Operating Cash + Investments: ${row['total_cash_investments']/1e6:,.1f}M")
    print(f"  Equities: {row['has_equities'].upper()}")
    print(f"  Captive: {row['has_captive'].upper()}")
    print(f"  Exclusion Reason: {row['si_notes']}")
    print(f"  Source: {row['source_url']}")

print("\n\n" + "="*200)
print("SUMMARY TABLE - TEXAS HOSPITAL DISTRICTS")
print("="*200)
print(f"\n{'System':<45} {'Cash+Inv':>12} {'Equities':>8} {'Captive':>8} {'Target':>8} {'Total SI':>12} {'SI Trust':>12} {'Confidence':>15}")
print("-"*130)

for _, row in tx_districts.sort_values('total_cash_investments', ascending=False).iterrows():
    name = row['system_name'][:44]
    cash = f"${row['total_cash_investments']/1e6:,.0f}M"
    eq = str(row['has_equities']).upper()[:6]
    cap = str(row['has_captive']).upper()[:6]
    target = "YES" if row['is_target'] else "NO"
    si = f"${row['total_self_insurance_reserves']/1e6:.1f}M" if pd.notna(row['total_self_insurance_reserves']) and row['total_self_insurance_reserves'] > 0 else "--"
    si_trust = f"${row['self_insurance_trust_balance']/1e6:.1f}M" if pd.notna(row['self_insurance_trust_balance']) and row['self_insurance_trust_balance'] > 0 else "--"
    conf = row['source_type'][:14] if pd.notna(row['source_type']) else ""
    print(f"{name:<45} {cash:>12} {eq:>8} {cap:>8} {target:>8} {si:>12} {si_trust:>12} {conf:>15}")

print("\n" + "="*200)
print("KEY FINDINGS:")
print("="*200)
print("""
1. ALL Texas hospital districts are subject to the Texas Public Funds Investment Act (PFIA)
   - PFIA restricts investments to: time deposits, commercial paper, money market funds,
     investment pools (TexPool, TexSTAR, Texas CLASS), government securities (Treasuries, agencies)
   - This provides HIGH CONFIDENCE that operating funds are fixed-income-only

2. TARGETS IDENTIFIED (6 systems):
   - PARKLAND HEALTH (Dallas County HD): ~$1.7B - PFIA compliant, SI ~$50M estimated
   - JPS HEALTH NETWORK (Tarrant County HD): $2.17B - PFIA compliant, SI $14.2M, SI Trust $14.4M
   - HARRIS HEALTH SYSTEM (Harris County HD): $1.46B - PFIA compliant, SI $67.6M (employee health)
   - UMC HEALTH SYSTEM LUBBOCK: $412M - PFIA compliant, SI $4.8M, SI Trust $17M
   - UMC EL PASO (El Paso County HD): ~$350M - PFIA compliant, audit needed for SI
   - MIDLAND MEMORIAL HOSPITAL: ~$250M - PFIA compliant, audit needed for SI
   - ECTOR COUNTY HD (Medical Center Health System): ~$175M - PFIA compliant, audit needed for SI

3. EXCLUDED SYSTEMS (2):
   - University Health San Antonio: $2.32B - BUT pension plan has equities (common stocks, equity mutual funds, alternatives)
   - Nueces County Hospital District: $50M - Does NOT operate a hospital (funds indigent care only)

4. TX TORT CLAIMS ACT provides sovereign immunity for medical malpractice:
   - Limits: $100K per individual, $300K per occurrence, $500K property damage
   - This significantly reduces professional liability self-insurance exposure for TX public hospitals
   - Main self-insurance exposure is employee health plans and workers compensation

5. TOTAL IDENTIFIED SELF-INSURANCE RESERVES FOR TX TARGETS: ~$136M+
   (Harris Health $67.6M + JPS $14.2M + Parkland ~$50M + UMC Lubbock $4.8M)
""")

print("\n" + "="*200)
print("SOURCE URLS FOR ALL TX HOSPITAL DISTRICTS:")
print("="*200)
for _, row in tx_districts.iterrows():
    print(f"\n{row['system_name']}:")
    print(f"  Financial: {row['source_url']}")
    if pd.notna(row['si_source_url']) and row['si_source_url']:
        print(f"  SI Data: {row['si_source_url']}")

if __name__ == "__main__":
    pass
