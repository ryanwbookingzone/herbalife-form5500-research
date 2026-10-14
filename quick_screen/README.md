# Quick Screen Pipeline - Healthcare System Financial Data

Fast, lightweight screening pipeline for US nonprofit and government hospital/health systems. Extracts three key data points per system to identify potential targets for detailed analysis.

## Data Points Captured

1. **Operating Cash + Investment Balance** - Board-designated/unrestricted investments (excludes pension/OPEB)
2. **Equity Holdings** - Yes/No/Unknown, equity % if stated (vs fixed-income-only)
3. **Captive Insurance** - Yes/No/Unknown, captive name/domicile if stated

## Target Flag Criteria

Systems flagged as `is_target = True` when ALL conditions met:
- Fixed income only (no equities)
- No captive insurance company
- Cash + investments > $25M

## Data Sources

### California (CA HCAI)
- California Health Care Access and Information (HCAI) Hospital Annual Financial Disclosure
- Direct balance sheet data: Cash, Limited Use Cash, Limited Use Investments, Other Investments
- URL: https://data.chhs.ca.gov/dataset/hospital-annual-financial-disclosure-report-complete-data-set

### Texas and Other States (ProPublica)
- ProPublica Nonprofit Explorer API (IRS 990 data)
- Total assets with investment income as proxy for investment holdings
- Note: Detailed Part X breakdown not available via API

### Equity/Captive Status
- Determined by keyword scan of audited financial statements
- Keywords: 'equity securities', 'common stock', 'mutual funds - equity' for equity
- Keywords: 'captive', 'wholly-owned insurance subsidiary', 'risk retention', 'Cayman', 'Vermont' for captive
- Marked as 'unknown' if audit not scanned or keywords not found

## Files

```
quick_screen/
├── README.md                    # This file
├── quick_screen.py              # Main screening script
├── quick_screen_results.csv     # Output: 50 screened systems
├── ca_hospital_data.xlsx        # CA HCAI source data (FY2024-25)
├── ca_labels.xlsx               # CA HCAI column labels
├── frappe_companies.json        # Company records for Frappe import
└── frappe_facts.json            # Financial fact records for Frappe import
```

## Usage

### Basic Run (CA + TX)
```bash
cd quick_screen
python quick_screen.py --output quick_screen_results.csv
```

### Custom States
```bash
python quick_screen.py --states FL NY PA --output sunbelt_results.csv
```

### Skip ProPublica (CA only)
```bash
python quick_screen.py --skip-propublica --output ca_only.csv
```

### Options
- `--ca-data`: Path to CA HCAI Excel file (default: ca_hospital_data.xlsx)
- `--states`: States to search via ProPublica (default: TX)
- `--output`: Output CSV path (default: quick_screen_results.csv)
- `--max-results`: Maximum total results (default: 50)
- `--skip-ca`: Skip CA HCAI data
- `--skip-propublica`: Skip ProPublica search

## Results Summary (First Batch)

**Processed: 50 systems**
- CA hospitals (from HCAI): 45
- TX nonprofits (from ProPublica): 5

**Confirmed targets: 0** (equity/captive status unknown - need audit scan)

**Potential targets: 50** (need audit scan to determine equity/captive status)

### Top 15 by Investment Balance

| Rank | System | State | Cash+Investments | Equity | Captive |
|------|--------|-------|------------------|--------|---------|
| 1 | Stanford Health Care | CA | $6,975.8M | unknown | unknown |
| 2 | Cedars-Sinai Medical Center | CA | $4,765.1M | unknown | unknown |
| 3 | Memorial Hermann Health System | TX | $3,624.4M | unknown | unknown |
| 4 | Hoag Memorial Hospital Presbyterian | CA | $2,870.8M | unknown | unknown |
| 5 | Ronald Reagan UCLA Medical Center | CA | $2,466.2M | unknown | unknown |
| 6 | UCSF Medical Center | CA | $2,231.7M | unknown | unknown |
| 7 | Valley Children's Hospital | CA | $1,494.2M | unknown | unknown |
| 8 | Mercy Medical Center - Redding | CA | $1,283.8M | unknown | unknown |
| 9 | El Camino Hospital | CA | $1,124.7M | unknown | unknown |
| 10 | UC Davis Health | CA | $1,032.2M | unknown | unknown |
| 11 | Lucile Salter Packard Children's Hospital | CA | $931.7M | unknown | unknown |
| 12 | Palomar Medical Center Escondido | CA | $899.0M | unknown | unknown |
| 13 | Community Health System | CA | $850.1M | unknown | unknown |
| 14 | PIH Health Hospital - Whittier | CA | $830.7M | unknown | unknown |
| 15 | Dominican Hospital Santa Cruz | CA | $793.9M | unknown | unknown |

## Frappe Records Created

### Company Listings (BZ Company Listing)
| Name | Frappe ID |
|------|-----------|
| Stanford Health Care | q3niqvsofl |
| Cedars-Sinai Medical Center | q3q0p2q17e |
| Memorial Hermann Health System | q3pvn71t4h |
| Hoag Memorial Hospital Presbyterian | q3q1rj0bq2 |
| Ronald Reagan UCLA Medical Center | q3q0e50nrq |

### Financial Facts (BZ Source Financial Fact)
| Entity | Fact | Value | Frappe ID |
|--------|------|-------|-----------|
| Stanford Health Care | Total Cash and Investments | $6,975.8M | q44v5iir1q |
| Cedars-Sinai Medical Center | Total Cash and Investments | $4,765.1M | q451lto0ig |
| Memorial Hermann Health System | Total Cash and Investments | $3,624.4M | q450ghnmvd |
| Hoag Memorial Hospital Presbyterian | Total Cash and Investments | $2,870.8M | q450shf9bj |
| Ronald Reagan UCLA Medical Center | Total Cash and Investments | $2,466.2M | q451kpcehc |

## Running the Next Batch

### Add More States
```bash
python quick_screen.py --states FL NY PA OH --max-results 100 --output batch2_results.csv
```

### Refresh CA Data
1. Download latest HCAI data from https://data.chhs.ca.gov/dataset/hospital-annual-financial-disclosure-report-complete-data-set
2. Run: `python quick_screen.py --ca-data new_hospital_data.xlsx`

### Audit Scan for Equity/Captive
To determine equity and captive status for specific systems:
1. Find the system's audited financial statement (EMMA for government, website for nonprofit)
2. Search for keywords in the investment and self-insurance notes
3. Update the CSV with the findings

## Known Limitations

1. **ProPublica API**: Doesn't provide detailed Part X balance sheet lines; uses total assets as proxy
2. **Equity/Captive Status**: Requires manual audit scan to confirm; marked 'unknown' by default
3. **Government Hospitals**: EMMA/MSRB search not implemented in this version
4. **TX Data**: No bulk state dataset like CA HCAI; relies on ProPublica 990 data
