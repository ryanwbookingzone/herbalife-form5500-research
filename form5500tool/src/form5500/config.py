import os
from pathlib import Path

HOME = Path(os.environ.get("FORM5500_HOME", Path.home() / ".form5500"))
RAW_DIR = Path(os.environ.get("FORM5500_RAW", HOME / "raw"))
DB_PATH = Path(os.environ.get("FORM5500_DB", HOME / "form5500.duckdb"))
FILINGS_DIR = Path(os.environ.get("FORM5500_FILINGS", HOME / "filings"))
UA = {"User-Agent": "Mozilla/5.0 (form5500-research-tool)"}

# NB: use the www. host; the apex host 301s with an unescaped space (see IAR wiki notes).
FOIA_URL = "https://www.askebsa.dol.gov/FOIA%20Files/{year}/Latest/{name}_{year}_Latest.zip"
EFAST_SEARCH = "https://www.efast.dol.gov/services/afs"
EFAST_PDF = "https://efast2-filings-public.s3.amazonaws.com/prd"

# All DOL FOIA "Latest" datasets (some do not exist for every year; missing ones are recorded and skipped)
DATASETS = [
    "F_5500", "F_5500_SF", "F_5500_SF_PART7",
    "F_SCH_A", "F_SCH_A_PART1",
    "F_SCH_C", "F_SCH_C_PART1_ITEM1", "F_SCH_C_PART1_ITEM2", "F_SCH_C_PART1_ITEM2_CODES",
    "F_SCH_C_PART1_ITEM3", "F_SCH_C_PART2", "F_SCH_C_PART3",
    "F_SCH_D", "F_SCH_D_PART1", "F_SCH_D_PART2",
    "F_SCH_G", "F_SCH_G_PART1", "F_SCH_G_PART2", "F_SCH_G_PART3",
    "F_SCH_H", "F_SCH_H_PART1", "F_SCH_I", "F_SCH_I_PART1",
    "F_SCH_R", "F_SCH_R_PART1", "F_SCH_SB", "F_SCH_SB_PART1", "F_SCH_MB", "F_SCH_MB_PART1",
    "F_SCH_MB_PART2", "F_SCH_DCG", "F_SCH_MEP",
]
CORE = ["F_5500", "F_5500_SF", "F_SCH_A", "F_SCH_A_PART1", "F_SCH_C", "F_SCH_C_PART1_ITEM1",
        "F_SCH_C_PART1_ITEM2", "F_SCH_C_PART1_ITEM2_CODES", "F_SCH_C_PART1_ITEM3", "F_SCH_C_PART3",
        "F_SCH_D", "F_SCH_D_PART1", "F_SCH_G", "F_SCH_H", "F_SCH_I", "F_SCH_R", "F_SCH_SB", "F_SCH_MB"]

# Broker-group aliases (substring on normalized name -> canonical group). Extend via ~/.form5500/broker_aliases.txt  ("PATTERN=Group" lines)
BROKER_ALIASES = [
    ("PETER C FOY", "PCF / Trucordia (Peter C. Foy)"), ("PCF INSURANCE", "PCF / Trucordia (Peter C. Foy)"),
    ("TRUCORDIA", "PCF / Trucordia (Peter C. Foy)"), ("HUB INTERNATIONAL", "HUB International"),
    ("HUB INTL", "HUB International"), ("HUB INT L", "HUB International"), ("GALLAGHER", "Gallagher"), ("ARTHUR J GALLAGHER", "Gallagher"),
    ("USI INSURANCE", "USI"), ("USI SOUTHWEST", "USI"), ("USI SW", "USI"), ("MARSH", "Marsh McLennan Agency"),
    ("MERCER", "Mercer"), ("AON", "Aon"), ("WILLIS", "WTW"), ("LOCKTON", "Lockton"), ("ALLIANT", "Alliant"),
    ("NFP", "NFP"), ("ONEDIGITAL", "OneDigital"), ("ONE DIGITAL", "OneDigital"), ("HOWDEN", "Howden"),
    ("ASSUREDPARTNERS", "AssuredPartners"), ("ASSURED PARTNERS", "AssuredPartners"), ("BROWN & BROWN", "Brown & Brown"),
    ("BROWN AND BROWN", "Brown & Brown"), ("TBG DANCO", "TBG Danco"), ("ACRISURE", "Acrisure"),
    ("SEQUOIA", "Sequoia"), ("CBIZ", "CBIZ"), ("WOODRUFF SAWYER", "Woodruff Sawyer"),
]
