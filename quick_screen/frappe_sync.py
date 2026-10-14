#!/usr/bin/env python3
"""
Build mapping of existing QS-* records and identify what needs to be created.
"""
import json

# Parse existing QS records from the list_documents output
existing_qs = {
    "QS-CA-MAYERS-MEMORIAL-HOSPITAL": "rauo2pmo96",
    "QS-CA-SAN-GORGONIO-MEMORIAL-HOSPITAL": "raunm5tlal",
    "QS-CA-BEAR-VALLEY-COMMUNITY-HOSPITAL": "ras7399mue",
    "QS-CA-SAN-BERNARDINO-MOUNTAINS-COMM": "ras6h2i6jn",
    "QS-CA-FAIRCHILD-MEDICAL-CENTER": "ras64j13vj",
    "QS-CA-OAK-VALLEY-DISTRICT-HOSPITAL": "ras5o5jvvt",
    "QS-CA-LOMPOC-VALLEY-MEDICAL-CENTER": "ras5jc6u5t",
    "QS-CA-NORTHERN-INYO-HEALTHCARE-DISTR": "rao2k5ldsl",
    "QS-CA-MODOC-MEDICAL-CENTER": "rao1l9egqf",
    "QS-CA-SAN-BENITO-HEALTH-CARE-DISTRIC": "rao0sen6c4",
    "QS-TX-ECTOR-COUNTY-HOSPITAL-DISTRICT": "rao09da90f",
    "QS-TX-NUECES-COUNTY-HOSPITAL-DISTRIC": "ranvl3jehd",
    "QS-TX-MIDLAND-MEMORIAL-HOSPITAL": "rajj5gon9p",
    "QS-TX-UMC-EL-PASO": "rajir6tk0i",
    "QS-TX-UNIVERSITY-HEALTH-SAN-ANTONIO": "raji930e71",
    "QS-TX-UMC-HEALTH-SYSTEM-LUBBOCK": "rajhk16pem",
    "QS-TX-PARKLAND-HEALTH": "rajhpok0f7",
    "QS-CA-PIONEERS-MEMORIAL-HEALTHCARE-D": "raenff9ct4",
    "QS-CA-CONTRA-COSTA-REGIONAL-MEDICAL": "raen6g50t4",
    "QS-CA-TAHOE-FOREST-HOSPITAL-DISTRICT": "raenqe1jdp",
    "QS-CA-SOUTHERN-MONO-HEALTHCARE-DISTR": "raema48a19",
    "QS-CA-KERN-COUNTY-HOSPITAL-AUTHORITY": "raem01n4mr",
    "QS-CA-ADVENTIST-HEALTH-SYSTEM-WEST": "raa7mg1ofj",
    "QS-CA-RIVERSIDE-UNIVERSITY-HEALTH-SY": "raa64gj3c7",
    "QS-CA-KAWEAH-DELTA-HEALTH-CARE-DISTR": "raa6snoobt",
    "QS-TX-COOK-CHILDRENS-MEDICAL-CENTER": "raa5c60ro7",
    "QS-CA-CEDARS-SINAI-HEALTH-SYSTEM": "raa3jtmog5",
    "QS-TX-TEXAS-CHILDRENS-HOSPITAL": "ra5o5e17h3",
    "QS-CA-SHARP-MEMORIAL-HOSPITAL": "ra5ncmbrps",
    "QS-TX-BAYLOR-UNIVERSITY-MEDICAL-CENT": "ra5n8c8vll",
    "QS-TX-THE-METHODIST-HOSPITAL": "ra5md6m6ff",
    "QS-TX-CHILDRENS-HEALTH-SYSTEM-OF-TEX": "ra5ljpm8bh",
    "QS-TX-JPS-HEALTH-NETWORK": "r8g5l7n0q8",
    "QS-TX-HARRIS-HEALTH-SYSTEM": "r8g4h12u37",
    "QS-CA-ALAMEDA-HEALTH-SYSTEM": "r8g3gqbf2p",
}

# Load prepared companies from JSON
with open('/workspace/quick_screen/frappe_all_companies.json') as f:
    all_companies = json.load(f)

# Find missing companies
missing = []
for company in all_companies:
    listing_id = company['listing_id']
    if listing_id not in existing_qs:
        missing.append(company)

print(f"Total companies needed: {len(all_companies)}")
print(f"Already exist in Frappe: {len(existing_qs)}")
print(f"Missing (need to create): {len(missing)}")
print("\nMissing companies:")
for c in missing[:20]:
    print(f"  - {c['listing_id']}")
if len(missing) > 20:
    print(f"  ... and {len(missing) - 20} more")

# Save mapping for reference
with open('/tmp/qs_existing_mapping.json', 'w') as f:
    json.dump(existing_qs, f, indent=2)

with open('/tmp/qs_missing_companies.json', 'w') as f:
    json.dump(missing, f, indent=2)

print(f"\nSaved mapping to /tmp/qs_existing_mapping.json")
print(f"Saved missing list to /tmp/qs_missing_companies.json")
