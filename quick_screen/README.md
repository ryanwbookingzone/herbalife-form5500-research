# Quick Screen Pipeline for US Nonprofit/Government Hospital Systems

A self-correcting pipeline to identify hospital systems with >$25M in fixed-income-only investments and no captive insurance.

## Target Criteria

Systems qualify as targets if they meet ALL of:
1. **Fixed income only** - No equity securities (or de minimis <5%)
2. **No captive insurance** - No wholly-owned insurance subsidiary
3. **>$25M investments** - Board-designated + operating cash/investments

## Pipeline Architecture

### 1. Parent System Resolution

Map individual facilities to parent health systems first. Many hospitals share one parent audit:

| Parent System | Facilities |
|--------------|------------|
| Providence St. Joseph Health | St. Joseph Hospital, Queen of the Valley, Santa Rosa Memorial, etc. |
| CommonSpirit Health | California Hospital MC, Northridge Hospital, Mercy hospitals, etc. |
| Sutter Health | Sutter West Bay, Sutter Sacramento, etc. |
| Adventist Health | Sierra Nevada Memorial, Sonora Community, Reedley, etc. |

Audits are cached per parent system and reused for all subsidiaries.

### 2. Source Ladder

Stop at first hit, in order:
1. **EMMA** - Continuing disclosures for bond issuers (search by name, take latest annual audited financials)
2. **System Website** - Financial/investor relations pages
3. **Government Filings** - For districts: district audit, county ACFR, state controller filings
4. **990 Fallback** - Schedule D Part VII/VIII (investments by type), Schedule R (related insurance companies)

### 3. Classification Rules

#### Equity Securities

**YES** if any of these appear in operating/board-designated investments:
- Equity securities
- Common stock
- Equity mutual funds / ETFs
- Alternative investments with equity exposure
- Hedge funds, private equity

**NO** if investment note lists ONLY:
- LAIF, CAMP, TexPool (state pools)
- US Treasuries, federal agencies
- Municipal bonds, corporate bonds
- CDs, commercial paper, money market

**NO with high confidence** if state law restricts (and note confirms):
- CA Government Code Section 53601
- TX Public Funds Investment Act

**DE_MINIMIS** if equity < 5% or < $1M (counts as NO for targeting)

#### Captive Insurance

**YES** if entity has:
- Wholly-owned insurance subsidiary
- Captive insurance company
- Risk retention group (RRG)
- SPC cell / protected cell

**NO** if insurance note describes only:
- Self-insurance trust (not a separate entity)
- Commercial excess insurance
- Claims-made insurance

### 4. Confidence Levels

| Level | Definition |
|-------|------------|
| HIGH | Direct audit evidence with clear quote |
| MEDIUM | Parent system audit or 990 with investment breakdown |
| LOW | Inferred from state law or partial evidence |
| UNKNOWN | No evidence found |

### 5. Self-Check

Compare audit totals vs 990 cash+investments. Flag >25% discrepancies for review.

### 6. Unknown Rate Target

Each batch should have <10% unknown. If exceeded, retry unknowns with next ladder rung.

## File Structure

```
quick_screen/
├── README.md                    # This file
├── parent_systems.py            # Parent system mappings
├── quick_screen_pipeline.py     # Main pipeline code
├── quick_screen_tx_ca.csv       # Input data (TX/CA hospitals)
├── quick_screen_results.csv     # Output with all evidence
└── update_batch*.py             # Batch update scripts
```

## Running the Pipeline

```bash
cd /workspace/quick_screen
python3 quick_screen_pipeline.py
```

## Results Summary (as of October 2026)

### HIGH CONFIDENCE TARGETS (Audit Verified Fixed Income Only)

| System | State | Total Investments | FY | Evidence |
|--------|-------|-------------------|-----|----------|
| Kaweah Delta Health Care District | CA | $269,754,398 | FY2024 | LAIF + US Treasury, no captive |
| Riverside University Health System | CA | $265,795,287 | FY2024 | County pool (Riverside ACFR), no captive |
| Kern County Hospital Authority | CA | $174,835,076 | FY2024 | County Treasury (CA Gov Code 53601), no captive |
| Pioneers Memorial Healthcare District | CA | $46,943,005 | FY2024 | CA Code 53600, Mechanics Bank (fixed income) |
| Bear Valley Community Hospital | CA | $43,664,443 | FY2023 | LAIF only ($40M) |
| San Benito Health Care District | CA | $38,785,662 | FY2024 | US Government securities + CGC collateralized |
| Modoc Medical Center | CA | $37,899,626 | FY2024 | Money market $5.1M + US Treasuries $30M |
| Oak Valley District Hospital | CA | $30,215,704 | FY2025 | LAIF only ($25M) |
| Lompoc Valley Medical Center | CA | $25,937,370 | FY2024 | LAIF $18.7M (99.9% fixed income) |

**Total HIGH CONFIDENCE: 9 systems, $933M combined**

### NEAR FIXED INCOME (De Minimis Equity <5%)

| System | State | Total Investments | Equity % | FY | Evidence |
|--------|-------|-------------------|----------|-----|----------|
| Tahoe Forest Hospital District | CA | $174,242,477 | 0.1% | FY2024 | De minimis equity per audit |
| Northern Inyo Healthcare District | CA | $39,626,522 | 1.0% | FY2025 | $83K equities + $98K mutual funds of $8.4M |

**Total NEAR FIXED INCOME: 2 systems, $214M combined**

### MEDIUM CONFIDENCE (Needs Full Audit Verification)

| System | State | Total Investments | Status |
|--------|-------|-------------------|--------|
| Southern Mono Healthcare District | CA | $152,760,138 | Shows LAIF + "Investments" - verify composition |
| Fairchild Medical Center | CA | $44,875,305 | Foundation has equities, hospital unclear |
| San Bernardino Mountains CHD | CA | $43,434,431 | No audit found with investment details |
| San Gorgonio Memorial Hospital | CA | $37,277,130 | Minimal investments, mostly cash |
| Mayers Memorial Hospital | CA | $36,625,090 | Policy allows 20% equity - verify actual holdings |

**Total MEDIUM: 5 systems, $315M combined (needs verification)**

### DROPPED FROM TARGETS

| System | Reason |
|--------|--------|
| Antelope Valley Medical Center | Mutual funds $217M + ETFs $81M + limited partnerships (FY2024 audit) |

### Not Targets (with equities or captives)

| System | Parent | Equity | Captive |
|--------|--------|--------|---------|
| Providence hospitals | Providence St. Joseph Health | YES | YES (Providence Assurance Inc) |
| CommonSpirit hospitals | CommonSpirit Health | YES | YES |
| Sutter hospitals | Sutter Health | YES | NO |
| Adventist hospitals | Adventist Health | YES | NO |
| UC hospitals | UC Health | YES | YES |
| Children's Hospital LA | - | YES (51%) | NO |

## Data Storage

Results are stored in Frappe as:
- **BZ Company Listing** - Entity record
- **BZ Source Financial Fact** - Evidence records with source URL, page reference, and quote

## Audit Sources by Type

### California Hospitals
- CA HCAI: https://data.chhs.ca.gov/dataset/hospital-annual-financial-disclosure-report-complete-data-set
- CA State Controller: https://sco.ca.gov/ard_local_districts.html

### Texas Hospitals
- TX Comptroller: https://comptroller.texas.gov/transparency/local/

### Bond Issuers
- EMMA: https://emma.msrb.org/

### 990 Data
- ProPublica Nonprofit Explorer: https://projects.propublica.org/nonprofits/
