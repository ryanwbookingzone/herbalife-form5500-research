#!/usr/bin/env python3
"""
Parent System Mapping for Quick Screen Pipeline.

Maps individual facilities to their parent health systems to enable audit caching.
Sources: 990 Schedule R, audit "obligated group" disclosures, HCAI ownership data.
"""

PARENT_SYSTEMS = {
    # Providence St. Joseph Health
    "providence": {
        "name": "Providence St. Joseph Health",
        "audit_url": "https://www.providence.org/about/financial-statements",
        "emma_issuer": "Providence St. Joseph Health",
        "has_equities": True,
        "has_captive": True,
        "captive_name": "Providence Assurance Inc",
        "facilities": [
            "ST. JOSEPH HOSPITAL",
            "QUEEN OF THE VALLEY MEDICAL CENTER",
            "St Mary Medical Center",
            "Covenant Medical Center",
            "PROVIDENCE CEDARS-SINAI TARZANA MEDICAL CENTER",
            "PROVIDENCE LITTLE COMPANY OF MARY MC - SAN PEDRO",
            "SANTA ROSA MEMORIAL HOSPITAL",
            "REDWOOD MEMORIAL HOSPITAL",
            "ST. JOHNS REGIONAL MEDICAL CENTER",
        ]
    },
    
    # CommonSpirit Health
    "commonspirit": {
        "name": "CommonSpirit Health",
        "audit_url": "https://www.commonspirit.org/investor-resources",
        "emma_issuer": "CommonSpirit Health",
        "has_equities": True,
        "has_captive": True,
        "captive_name": "CommonSpirit Health captive",
        "facilities": [
            "CALIFORNIA HOSPITAL MEDICAL CENTER",
            "NORTHRIDGE HOSPITAL MEDICAL CENTER",
            "MERCY GENERAL HOSPITAL",
            "MERCY MEDICAL CENTER",
            "MERCY SAN JUAN MEDICAL CENTER",
            "MERCY MEDICAL CENTER - MT. SHASTA",
            "COMMUNITY HOSPITAL OF SAN BERNARDINO",
        ]
    },
    
    # Sutter Health
    "sutter": {
        "name": "Sutter Health",
        "audit_url": "https://www.sutterhealth.org/about/financials",
        "emma_issuer": "Sutter Health",
        "emma_url": "https://emma.msrb.org/P11855694.pdf",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "SUTTER WEST BAY HOSPITALS",
            "SUTTER MEDICAL CENTER SACRAMENTO",
        ]
    },
    
    # Adventist Health
    "adventist": {
        "name": "Adventist Health",
        "audit_url": "https://www.adventisthealth.org/about/financial-information/",
        "emma_issuer": "Adventist Health System/West",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "Adventist Health System-west",
            "SIERRA NEVADA MEMORIAL MINERS HOSPITAL INC",
            "SONORA COMMUNITY HOSPITAL",
            "ADVENTIST HEALTH DELANO",
            "UKIAH ADVENTIST HOSPITAL",
            "ADVENTIST HEALTH HOWARD MEMORIAL",
            "ADVENTIST HEALTH CLEARLAKE HOSPITAL",
            "REEDLEY COMMUNITY HOSPITAL",
        ]
    },
    
    # UC Health System
    "uc_health": {
        "name": "University of California Health",
        "audit_url": "https://www.ucop.edu/uc-controller/financial-reports/",
        "emma_issuer": "Regents of the University of California",
        "has_equities": True,
        "has_captive": True,
        "facilities": [
            "UCI HEALTH - FOUNTAIN VALLEY",
            "UCI HEALTH - PLACENTIA LINDA HOSPITAL",
            "UCLA SANTA MONICA MEDICAL CENTER",
        ]
    },
    
    # LA County DHS
    "la_county_dhs": {
        "name": "Los Angeles County Department of Health Services",
        "audit_url": "https://auditor.lacounty.gov/wp-content/uploads/2025/01/Annual-Comprehensive-Financial-Report-FY-2023-2024.pdf",
        "has_equities": True,  # Via LACERA pension exposure
        "has_captive": False,
        "facilities": [
            "LOS ANGELES GENERAL MEDICAL CENTER",
            "LOS ANGELES COUNTY OLIVE VIEW-UCLA MEDICAL CENTER",
            "LOS ANGELES COUNTY/ HARBOR-UCLA MEDICAL CENTER",
            "RANCHO LOS AMIGOS NATIONAL REHABILITATION CENTER",
        ]
    },
    
    # Sharp HealthCare
    "sharp": {
        "name": "Sharp HealthCare",
        "audit_url": "https://www.sharp.com/about/financial-reports/",
        "emma_issuer": "Sharp HealthCare",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "Sharp Memorial Hospital",
            "SHARP CORONADO HOSPITAL AND HEALTHCARE",
        ]
    },
    
    # Cedars-Sinai
    "cedars_sinai": {
        "name": "Cedars-Sinai Health System",
        "audit_url": "https://www.cedars-sinai.org/about/financial-reports.html",
        "emma_issuer": "Cedars-Sinai Medical Center",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "Cedars-sinai Health System",
        ]
    },
    
    # Methodist Healthcare San Antonio
    "methodist_sa": {
        "name": "Methodist Healthcare System of San Antonio",
        "audit_url": "https://www.mhm.org/library/financial-statements-and-tax-returns/",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "The Methodist Hospital",
            "Methodist Childrens Hospital",
        ]
    },
    
    # Texas Children's
    "texas_childrens": {
        "name": "Texas Children's Hospital",
        "audit_url": "https://www.texaschildrens.org/about-us/financials",
        "emma_issuer": "Texas Children's Hospital",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "Texas Childrens Hospital",
        ]
    },
    
    # Children's Health System of Texas
    "childrens_dallas": {
        "name": "Children's Health System of Texas",
        "audit_url": "https://www.childrens.com/about-us/financial-information",
        "emma_issuer": "Children's Medical Center of Dallas",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "Childrens Health System Of Texas",
        ]
    },
    
    # Baylor Scott & White
    "baylor_scott_white": {
        "name": "Baylor Scott & White Health",
        "audit_url": "https://www.bswhealth.com/about-us/financial-information",
        "emma_issuer": "Baylor Scott & White Health",
        "has_equities": True,
        "has_captive": True,
        "facilities": [
            "Baylor University Medical Center",
            "Scott & White Hospital",
        ]
    },
    
    # Cook Children's
    "cook_childrens": {
        "name": "Cook Children's Health Care System",
        "audit_url": "https://www.cookchildrens.org/about-us/financial-reports",
        "emma_issuer": "Cook Children's Medical Center",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "Cook Childrens Medical Center",
            "Cook Childrens Health Care System",
        ]
    },
    
    # CHRISTUS Health
    "christus": {
        "name": "CHRISTUS Health",
        "audit_url": "https://www.christushealth.org/about/financial-information",
        "emma_issuer": "CHRISTUS Health",
        "has_equities": True,
        "has_captive": True,
        "captive_name": "Emerald Assurance Cayman Ltd",
        "captive_domicile": "Cayman Islands",
        "facilities": [
            "Christus Spohn Health System Corporation",
        ]
    },
    
    # Emanate Health
    "emanate": {
        "name": "Emanate Health",
        "audit_url": "https://emma.msrb.org/P11869630.pdf",
        "emma_issuer": "Emanate Health",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "EMANATE HEALTH MEDICAL CENTER",
            "EMANATE HEALTH FOOTHILL PRESBYTERIAN HOSPITAL",
        ]
    },
    
    # Children's Hospital Los Angeles
    "chla": {
        "name": "Children's Hospital Los Angeles",
        "audit_url": "https://emma.msrb.org/P11827180.pdf",
        "emma_issuer": "Children's Hospital Los Angeles",
        "has_equities": True,
        "equity_pct": 51,  # 33.5% US + 17.5% non-US
        "has_captive": False,
        "facilities": [
            "CHILDRENS HOSPITAL LOS ANGELES",
            "CHILDRENS HOSPITAL & RESEARCH CENTER OAKLAND",
        ]
    },
    
    # Loma Linda University Health
    "loma_linda": {
        "name": "Loma Linda University Health",
        "audit_url": "https://lluh.org/about-us/financial-information",
        "emma_issuer": "Loma Linda University Medical Center",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "LOMA LINDA UNIVERSITY CHILDRENS HOSPITAL",
        ]
    },
    
    # PIH Health
    "pih": {
        "name": "PIH Health",
        "audit_url": "https://www.pihhealth.org/about/financial-information/",
        "emma_issuer": "PIH Health",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "PIH HEALTH GOOD SAMARITAN HOSPITAL",
        ]
    },
    
    # Hoag Memorial Hospital
    "hoag": {
        "name": "Hoag Memorial Hospital Presbyterian",
        "audit_url": "https://www.hoag.org/about-hoag/financial-information/",
        "emma_issuer": "Hoag Memorial Hospital Presbyterian",
        "has_equities": True,
        "has_captive": False,
        "facilities": [
            "HOAG ORTHOPEDIC INSTITUTE, LLC",
        ]
    },
}

# Standalone hospitals/districts (no parent system - need individual audits)
STANDALONE_SYSTEMS = [
    "KAWEAH DELTA HEALTH CARE DISTRICT",
    "RIVERSIDE UNIVERSITY HEALTH SYSTEM",
    "WASHINGTON TOWNSHIP HEALTHCARE DISTRICT",
    "KERN COUNTY HOSPITAL AUTHORITY",
    "TAHOE FOREST HOSPITAL DISTRICT",
    "Community Memorial Health System",
    "Marin General Hospital",
    "BARTON HEALTHCARE SYSTEM",
    "SIERRA VIEW LOCAL HEALTHCARE DISTRICT",
    "COMMUNITY MEMORIAL HOSPITAL OF SAN BUENAVENTURA",
    "Shannon Medical Center",
    "SAN ANTONIO REGIONAL HOSPITAL",
    "SOUTHERN MONO HEALTHCARE DISTRICT",
    "CASA COLINA HOSPITAL AND CENTERS FOR HEALTHCARE",
    "Rideout Memorial Hospital",
    "SAN JOAQUIN COMMUNITY HOSPITAL CORP",
    "ALHAMBRA HOSPITAL MEDICAL CENTER LP",  # For-profit, skip
    "GARFIELD MEDICAL CENTER",  # AHMC, for-profit
    "GREATER EL MONTE COMMUNITY HOSPITAL",  # AHMC, for-profit
    "MONTEREY PARK HOSPITAL",  # AHMC, for-profit
    "POMONA VALLEY HOSPITAL MEDICAL CENTER",
    "Orthopaedic Hospital",
    "Chinese Hospital Association",
    "MARSHALL MEDICAL CENTER",
    "PASADENA HOSPITAL ASSOCIATION, LTD.",
    "SAINT AGNES MEDICAL CENTER",
    "GOLETA VALLEY COTTAGE HOSPITAL",
    "OROVILLE HOSPITAL",
    "USC ARCADIA HOSPITAL",
    "SEQUOIA HOSPITAL",
    "Lexington Medical Center",
    "PIONEERS MEMORIAL HEALTHCARE DISTRICT",
    "FAIRCHILD MEDICAL CENTER",
    "BEAR VALLEY COMMUNITY HOSPITAL",
    "Ridgecrest Regional Hospital",
    "SAN BERNARDINO MOUNTAINS COMMUNITY HOSPITAL DISTRICT",
    "ANTELOPE VALLEY MEDICAL CENTER",
    "Mission Hospital Inc",
    "NORTHERN INYO HEALTHCARE DISTRICT",
    "SAN BENITO HEALTH CARE DISTRICT",
    "COMMUNITY HOSPITAL OF THE MONTEREY PENINSULA",
    "Covenant Hospital Hobbs",
    "MODOC MEDICAL CENTER",
    "SAN GORGONIO MEMORIAL HOSPITAL",
    "MARINHEALTH MEDICAL CENTER",
    "MAYERS MEMORIAL HOSPITAL",
    "CHINESE HOSPITAL",
    "TARZANA TREATMENT CENTERS, INC.",
    "MISSION HOSPITAL",
    "EL CENTRO REGIONAL MEDICAL CENTER",
    "ALAMEDA HEALTH SYSTEM",
    "CHLB, LLC",
    "OAK VALLEY DISTRICT HOSPITAL",
    "Barlow Respiratory Hospital",
    "LOMPOC VALLEY MEDICAL CENTER",
    "MADERA COMMUNITY HOSPITAL",
]


def get_parent_system(facility_name: str) -> dict | None:
    """Look up the parent system for a facility."""
    facility_upper = facility_name.upper().strip()
    
    for system_id, system_info in PARENT_SYSTEMS.items():
        for facility in system_info["facilities"]:
            if facility.upper().strip() == facility_upper:
                return {"system_id": system_id, **system_info}
    
    return None


def is_standalone(facility_name: str) -> bool:
    """Check if facility is standalone (no parent system)."""
    return get_parent_system(facility_name) is None


def is_for_profit(facility_name: str) -> bool:
    """Check if facility is for-profit (should be excluded)."""
    for_profit_keywords = ["LP", "LLC", "INC.", "AHMC"]
    for_profit_systems = ["AHMC", "ALHAMBRA HOSPITAL", "GARFIELD MEDICAL", 
                          "GREATER EL MONTE", "MONTEREY PARK HOSPITAL"]
    
    name_upper = facility_name.upper()
    for keyword in for_profit_systems:
        if keyword in name_upper:
            return True
    return False
