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

## Self-Insurance Reserves (Captive Opportunity Sizing)

Self-insurance reserves from audit risk management notes size the captive insurance opportunity. Data includes:
- **Professional/General Liability Reserve** - Malpractice and general liability claims
- **Workers' Compensation Reserve** - Self-insured WC claims
- **Employee Health IBNR** - Incurred but not reported claims for self-insured health plans
- **Self-Insurance Trust Fund Balance** - Assets held for claims

### Self-Insurance Reserves Summary - 18 Targets

| System | State | Operating Cash+Inv | Total SI Reserves | Prof Liab | Workers Comp | Health IBNR | Source |
|--------|-------|-------------------|-------------------|-----------|--------------|-------------|--------|
| Alameda Health System | CA | $31.8M | **$56.3M** | $20.0M | $20.0M | $16.3M | [FY25 Audit](http://www.alamedahealthsystem.org/wp-content/uploads/2026/01/2026-01-07-BOT-Special-Meeting-Boardbook-rev2.pdf) |
| Kern County Hospital Authority | CA | $174.8M | **$11.1M** | $6.5M | $4.6M | - | [FY24 Audit Note 13](https://www.kernmedical.com/documents/Kern-County-Hospital-Authority-FY-2024-Audited-FS-Final-12.23.24.pdf) |
| Tahoe Forest Hospital District | CA | $174.2M | **$8.0M** | - | $4.0M | $4.0M | [FY24 Audit Note 9](https://www.tfhd.com/wp-content/uploads/2025/09/0.-Tahoe-Forest-Hospital-District-6-30-24-FS-Issued-10-29-24.pdf) |
| Lompoc Valley Medical Center | CA | $25.9M | **$1.5M** | $10K | $1.5M | - | [FY24 Audit](https://www.lompocvmc.com/files/95f1acfc1/LHDafs24.2%29.pdf) |
| Northern Inyo Healthcare District | CA | $39.6M | **$1.1M** | - | - | $1.1M | [FY25 Audit](https://www.nih.org/documents/2026/Financials/NIHD-Signed-Financial-Statements-FY25.pdf) |
| Southern Mono Healthcare District | CA | $152.8M | **$934K** | - | - | $934K | [Mammoth Hospital Financials](https://www.mammothhospital.com/about-us/financials/) |
| Kaweah Delta Health Care District | CA | $269.8M | Trust: $827K | - | - | - | [FY24 Audit](https://www.kaweahhealth.org/about-us/board-of-directors/audited-financials/) |
| San Benito Health Care District | CA | $38.8M | **$500K** | - | - | $500K | [FY24 Audit](https://www.hazelhawkins.com/images/FY24-Audited-Financial-Statement.pdf) |
| Modoc Medical Center | CA | $37.9M | **$5K** | $5K | - | - | [FY24 Audit Note 13](https://modocmedicalcenter.org/wp-content/uploads/2026/05/Last-Frontier-Healthcare-District-6.30.24-Issued-FS.pdf) |
| Riverside University Health System | CA | $265.8M | County ISF | County | County | County | [FY24 County ACFR](https://auditorcontroller.org/sites/g/files/aldnop171/files/2025-01/FY24%20ACFR%20%28Final%29.pdf) |
| Contra Costa Regional Medical Center | CA | $103.3M | County ISF | County | County | County | [FY24 County Budget](https://www.contracosta.ca.gov/DocumentCenter/View/83766/FY24-25-Adopted-Budget-Book) |
| Pioneers Memorial | CA | $46.9M | BETA pool | - | - | - | BETA participant |
| Bear Valley | CA | $43.7M | BETA pool | - | - | - | BETA participant |
| Fairchild | CA | $44.9M | Commercial | - | - | - | Commercial insurance |
| San Bernardino Mountains | CA | $43.4M | Commercial | - | - | - | Commercial insurance |
| San Gorgonio | CA | $37.3M | Commercial | - | - | - | Commercial insurance |
| Mayers Memorial | CA | $36.6M | Commercial | - | - | - | Commercial insurance |
| Oak Valley | CA | $30.2M | BETA pool | - | - | - | BETA participant |

**Totals:** $1.60B operating cash+investments, **$79.4M disclosed self-insurance reserves**

### Key Findings

1. **Alameda Health System** has the largest self-insurance exposure ($56.3M) despite smaller operating investments - significant captive opportunity
2. **Kern County Hospital Authority** has material malpractice ($6.5M) and workers' comp ($4.6M) reserves - audit-verified
3. **Tahoe Forest** self-insures employee health and workers' comp with $8M IBNR
4. **County systems** (Riverside, Contra Costa) route self-insurance through County internal service funds
5. **BETA participants** (Pioneers, Bear Valley, Oak Valley) pool malpractice risk through Beta Healthcare Group
6. **Small districts** (Fairchild, San Bernardino Mountains, San Gorgonio, Mayers) use commercial insurance

## Data Storage

Results are stored in Frappe as:
- **BZ Company Listing** - Entity record
- **BZ Source Financial Fact** - Evidence records with source URL, page reference, and quote (including self_insurance category)

## Texas Hospital Districts - Batch 1 Report (October 2026)

All Texas hospital districts are subject to the **Texas Public Funds Investment Act (PFIA)** which restricts investments to:
- Time deposits, commercial paper, money market funds
- Investment pools (TexPool, TexSTAR, Texas CLASS)
- Government securities (US Treasuries, federal agencies)

### Texas Hospital District Targets

| System | Cash+Investments | Equities | Captive | Target | Total SI | SI Trust | Confidence |
|--------|------------------|----------|---------|--------|----------|----------|------------|
| JPS Health Network | $2,169M | NO | NO | YES | $14.2M | $14.4M | audit_verified |
| Parkland Health | ~$1,700M | NO | NO | YES | ~$50.0M | - | pfia_inferred |
| Harris Health System | $1,462M | NO | NO | YES | $67.6M | - | audit_verified |
| UMC Health System Lubbock | $412M | NO | NO | YES | $4.8M | $17.0M | audit_verified |
| UMC El Paso | ~$350M | NO | NO | YES | - | - | pfia_inferred |
| Midland Memorial Hospital | ~$250M | NO | NO | YES | - | - | pfia_inferred |
| Ector County HD | ~$175M | NO | NO | YES | - | - | pfia_inferred |

**Total TX Targets: 7 systems, ~$6.5B combined cash+investments, ~$136M+ self-insurance reserves**

### Texas Non-Targets (Excluded)

| System | Cash+Investments | Exclusion Reason |
|--------|------------------|-----------------|
| University Health San Antonio | $2,320M | Pension plan has equities (common stocks, equity mutual funds, alternatives) |
| Nueces County Hospital District | $50M | Does not operate hospital (funds indigent care only) |

### Texas Tort Claims Act

TX public hospitals benefit from sovereign immunity limiting malpractice exposure:
- **$100K** per individual
- **$300K** per occurrence  
- **$500K** property damage

This significantly reduces professional liability self-insurance exposure. Main SI exposure is **employee health plans** and **workers compensation**.

### Source URLs - Texas Hospital Districts

| System | Financial Report | SI Data |
|--------|-----------------|---------|
| Harris Health | [FY24 Audit](https://www.harrishealth.org/SiteCollectionDocuments/financials/combined/harris-health-9-24-fs-revised-final.pdf) | Same |
| JPS Health Network | [FY25 Audit](https://jpshealthnet.org/sites/default/files/2026-04/JPS-Health-Network-09-2025-FS.pdf) | Note 9 |
| UMC Lubbock | [FY24 Audit](https://www.umchealthsystem.com/wp-content/uploads/2025/09/2024-Audited-Financial-Statements.pdf) | Note 15 |
| UMC El Paso | [El Paso County ACFR](https://www.epcounty.com/DocumentCenter/View/4578/Annual-Comprehensive-Financial-Report-Fiscal-Year-2024-PDF) | - |
| Parkland Health | [Financial Summary](https://www.parklandhealth.org/financial-summary) | [Reports](https://www.parklandhealth.org/reports-disclosures) |
| Univ Health SA | [FY24 Audit](https://www.universityhealth.com/-/media/Files/About-Us/Public-Notices-Reports/Financial-Reports/Audited-Financial-Reports/2024-Audited-Financial-Reports.ashx) | Note 4 |

## Audit Sources by Type

### California Hospitals
- CA HCAI: https://data.chhs.ca.gov/dataset/hospital-annual-financial-disclosure-report-complete-data-set
- CA State Controller: https://sco.ca.gov/ard_local_districts.html

### Texas Hospitals
- TX Comptroller SPDPID: https://spdpid.comptroller.texas.gov/
- TX Public Funds Investment Act: Chapter 2256, Texas Government Code

### Bond Issuers
- EMMA: https://emma.msrb.org/

### 990 Data
- ProPublica Nonprofit Explorer: https://projects.propublica.org/nonprofits/
