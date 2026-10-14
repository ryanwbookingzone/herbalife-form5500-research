#!/usr/bin/env python3
"""
Update UMC Lubbock with accurate self-insurance data from FY2024 audit.
"""

import pandas as pd

df = pd.read_csv('/workspace/quick_screen/quick_screen_tx_ca.csv')

mask = df['system_name'] == 'UMC HEALTH SYSTEM LUBBOCK'
if mask.any():
    # Update with more accurate data from the audit
    df.loc[mask, 'total_cash_investments'] = 411557000
    df.loc[mask, 'as_of_date'] = '12/31/2024'
    df.loc[mask, 'professional_liability_reserve'] = 0  # TX Tort Claims
    df.loc[mask, 'workers_comp_reserve'] = 910000  # Noncurrent self-insurance
    df.loc[mask, 'employee_health_ibnr'] = 3934000  # Current self-insurance
    df.loc[mask, 'total_self_insurance_reserves'] = 4844000
    df.loc[mask, 'self_insurance_trust_balance'] = 17045000  # Internally designated
    df.loc[mask, 'si_source_url'] = 'https://www.umchealthsystem.com/wp-content/uploads/2025/09/2024-Audited-Financial-Statements.pdf'
    df.loc[mask, 'si_source_page'] = 'Balance Sheet, Note 15'
    df.loc[mask, 'si_fiscal_year'] = 'FY2024'
    df.loc[mask, 'si_notes'] = 'Self-insured for medical malpractice, employee health claims, and workers comp. Current SI liability $3.9M, noncurrent $0.9M. Internally designated $17M for SI and other purposes.'
    print("Updated: UMC HEALTH SYSTEM LUBBOCK")

df.to_csv('/workspace/quick_screen/quick_screen_tx_ca.csv', index=False)
