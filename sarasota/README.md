# Healthcare System Financial Extraction Pipeline

This folder contains tools and data for extracting financial figures from US government hospital systems and nonprofit healthcare organizations.

## Overview

This pipeline is designed to:
1. Download and parse audited financial statements and interim reports (PDF)
2. Extract key financial figures with source page references
3. Generate verification screenshots of relevant PDF pages
4. Load structured data into Frappe as `BZ Source Financial Fact` records
5. Produce a match/mismatch report comparing extracted vs expected values

## Target Organizations

- US government hospital districts (public hospitals)
- Nonprofit healthcare systems
- Municipalities with health operations
- Systems with **>$25M cash + investments**

## Data Sources

| Source Type | Description | Example |
|-------------|-------------|---------|
| Audited Financial Statements | Annual audit reports (GASB for govt, GAAP for nonprofits) | AFS_FY25.pdf |
| Interim/Quarterly Reports | Unaudited quarterly financial statements | DAC_Report_Q3_2026.pdf |
| EMMA/MSRB Official Statements | Municipal bond disclosure documents | emma.msrb.org |
| ProPublica Nonprofit Explorer | IRS 990 data for nonprofit health systems | projects.propublica.org/nonprofits |

## Extracted Metrics

### Cash & Investments
- Cash and cash equivalents
- Board-designated investments
- Restricted investments
- Total cash + investments
- Days cash on hand

### Investment Policy & Mix
- Fixed income only policy (equity excluded)
- Short-term duration (days) and amount
- Long-term duration (years) and amount
- U.S. Government securities
- U.S. Agency securities
- Corporate bonds
- Municipal securities

### Debt & Ratings
- Total long-term debt (current + non-current)
- Moody's rating
- Fitch rating
- S&P rating

### Revenue
- Total operating revenue
- Net patient service revenue

### Self-Insurance / Risk
- Professional liability reserve
- Workers' compensation reserve
- Malpractice SIR and limits
- Sovereign immunity caps
- Self-funded employee health plan
- Captive/trust fund info

## Files

```
sarasota/
├── README.md                          # This file
├── extract_healthcare_financials.py   # Main extraction script
├── financial_figures.csv              # Extracted figures with verification
└── screenshots/                       # PDF page screenshots for evidence
    ├── fy25_balance_sheet.png
    ├── fy25_investments_fair_value.png
    ├── fy25_ratios_ratings.png
    ├── fy25_self_insurance.png
    ├── q3fy26_balance_sheet.png
    ├── q3fy26_investment_policy.png
    └── q3fy26_ratios.png
```

## Running for a New System

### Prerequisites

```bash
# PDF tools
sudo apt-get install poppler-utils

# Python packages
pip install requests
```

### Usage

```bash
python extract_healthcare_financials.py \
    --org-name "Organization Name" \
    --org-id "ORG-ID" \
    --pdfs "/path/to/audit.pdf,/path/to/interim.pdf" \
    --output-dir "./output" \
    --frappe-url "https://your-frappe-instance.com" \
    --frappe-token "api_key:api_secret"
```

### Environment Variables (Alternative to CLI)

```bash
export FRAPPE_API_KEY="your_api_key"
export FRAPPE_API_SECRET="your_api_secret"
```

## Frappe DocTypes Used

### BZ Company Listing
Organization master record with:
- `listing_id`: Unique identifier
- `company_name`: Full legal name
- `segment`: Healthcare/Government/Municipal
- `state`, `country`: Location
- `revenue`: Annual revenue

### BZ Source Financial Fact
Individual financial figures with full provenance:
- `entity`: Link to BZ Company Listing
- `fact_category`: cash_and_investments, portfolio_policy, self_insurance, debt, ratings, other
- `fact_name`: Metric name
- `reported_value_text`: Original text from source
- `reported_value_usd`: Numeric value
- `fiscal_year`: FY2025, FY2026, etc.
- `source_url`: PDF URL
- `source_domain`: smh.com, etc.
- `page_reference`: PDF page number
- `source_quote`: Verbatim quote from source
- `content_hash`: Unique hash for deduplication
- `confidence`: verified/unresolved

### BZ Self Insurance Program
Self-insurance program details with coverage lines.

## Candidate Identification Approach

### For Nonprofit Health Systems
1. Query ProPublica Nonprofit Explorer API for healthcare organizations
2. Filter by total assets or revenue > threshold
3. Check Form 990 Schedule D for investments breakdown

```bash
# Example ProPublica API query
curl "https://projects.propublica.org/nonprofits/api/v2/search.json?q=hospital&state[id]=FL"
```

### For Government Hospitals
1. Search EMMA/MSRB for municipal hospital bond issuers
2. Download official statements and continuing disclosure filings
3. Parse balance sheets for cash + investments

```bash
# EMMA search URL pattern
https://emma.msrb.org/IssuerHomePage/Issuer?id=XXX
```

## Verification Status

| Status | Meaning |
|--------|---------|
| `match` | Extracted value matches expected value |
| `mismatch` | Extracted value differs from expected (requires review) |
| `not_checked` | No expected value provided |
| `verified` | Manually verified from source |

## Sarasota Memorial Case Study

First implementation target: **Sarasota County Public Hospital District (SMH)**

### Key Findings

| Metric | FY2025 (9/30/25) | Q3 FY2026 (6/30/26) | Status |
|--------|------------------|---------------------|--------|
| Board Designated Investments | $1.426B | $1.617B | ✓ Match |
| Cash & Equivalents | $131M | $108M | ✓ Match |
| Days Cash on Hand | 305 | 320 | ✓ Match |
| Total Debt | $703M | $953M | ✓ Match |
| Revenue | $2.126B | - | ✓ Match |
| Fitch Rating | AA- | - | ✓ Match |
| Moody's Rating | A1 (not Aa3) | - | ⚠️ Mismatch |

### Investment Policy
- **Fixed income only** - equity investments explicitly excluded
- Minimum 90% rated A or higher
- Short-term portion ($570.8M): 157 days duration
- Long-term portion ($1.046B): 3.63 years duration

### Self-Insurance
- Professional liability reserve: $26.7M
- Malpractice SIR: $10M
- Malpractice limit: $15M/occurrence, $15M aggregate
- Sovereign immunity: $200K/individual, $300K/occurrence
- Self-funded employee health plan: Yes

## Known Limitations

1. **Moody's Rating Mismatch**: Task expected Aa3, but document shows A1 rating with reference to Moody's A1 median comparisons. The actual rating may need manual verification.

2. **Generic Extraction**: Current implementation has Sarasota-specific extraction logic. Full generic extraction requires additional development.

3. **Screenshot Cropping**: Screenshots are full pages, not cropped to specific figures.

## Next Steps

1. Implement generic text extraction patterns
2. Add support for more organization types
3. Build candidate screening from ProPublica/EMMA
4. Add automated figure verification
5. Implement Frappe bulk upload
