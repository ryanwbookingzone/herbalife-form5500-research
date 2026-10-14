#!/usr/bin/env python3
"""
Fix University Health San Antonio classification.
Rule: Ignore pension/OPEB investments entirely. Only operating investments count.
University Health SA's operating investments are PFIA compliant (fixed income).
"""

import pandas as pd

df = pd.read_csv('/workspace/quick_screen/quick_screen_tx_ca.csv')

mask = df['system_name'] == 'UNIVERSITY HEALTH SAN ANTONIO'
if mask.any():
    # Operating investments are PFIA compliant - pension equities don't count
    df.loc[mask, 'has_equities'] = 'no'
    df.loc[mask, 'is_target'] = True
    df.loc[mask, 'si_notes'] = 'Operating investments are PFIA compliant (fixed income only). Pension plan has equities but pension/OPEB excluded per rule. Self-insurance trust $5.4M, estimated SI costs $6.5M.'
    print("Fixed: UNIVERSITY HEALTH SAN ANTONIO - now target (operating investments are fixed income)")

df.to_csv('/workspace/quick_screen/quick_screen_tx_ca.csv', index=False)
print("Classification fixed")
