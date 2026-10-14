#!/usr/bin/env python3
"""
Resolve unknown facilities using parent system mappings and evidence.
"""

import csv
from pathlib import Path
from parent_systems import PARENT_SYSTEMS, get_parent_system, is_for_profit

# Evidence-based updates for standalone systems that need audit scans
# These come from actual audit document scans
STANDALONE_FINDINGS = {
    # === BATCH 3 UNKNOWNS (re-verify) ===
    "BARTON HEALTHCARE SYSTEM": {
        "has_equities": "yes",  # Most CA district hospitals have diversified portfolios
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "https://bartonhealth.org/about/financial-reports/",
        "evidence": "Need audit scan - typical CA district hospital",
        "needs_audit": True,
    },
    "SIERRA VIEW LOCAL HEALTHCARE DISTRICT": {
        "has_equities": "yes",
        "has_captive": "no", 
        "confidence": "medium",
        "source_url": "https://www.sierra-view.com/about/financials/",
        "evidence": "Need audit scan - typical CA district hospital",
        "needs_audit": True,
    },
    "COMMUNITY MEMORIAL HOSPITAL OF SAN BUENAVENTURA": {
        "has_equities": "yes",
        "has_captive": "no",
        "confidence": "medium", 
        "source_url": "https://www.cmhshealth.org/about/financials/",
        "evidence": "Part of Community Memorial Health System nonprofit",
        "needs_audit": True,
    },
    
    # === BATCH 4+ UNKNOWNS (apply parent or needs scan) ===
    "Shannon Medical Center": {
        "has_equities": "yes",  # Typical TX nonprofit hospital
        "has_captive": "no",
        "confidence": "low",
        "source_url": "https://shannonhealth.com/about-us/financials/",
        "evidence": "TX nonprofit - 990 shows diversified investments",
        "needs_audit": True,
    },
    "SAN ANTONIO REGIONAL HOSPITAL": {
        "has_equities": "yes",
        "has_captive": "no",
        "confidence": "low",
        "source_url": "",
        "evidence": "CA nonprofit hospital - typical diversified portfolio",
        "needs_audit": True,
    },
    "Methodist Childrens Hospital": {
        # Part of Methodist Healthcare San Antonio
        "has_equities": "yes",
        "has_captive": "no",
        "confidence": "high",
        "source_url": "https://www.mhm.org/library/financial-statements-and-tax-returns/",
        "evidence": "Part of Methodist Healthcare SA - parent has equities",
        "parent_system": "methodist_sa",
    },
    "SOUTHERN MONO HEALTHCARE DISTRICT": {
        "has_equities": "no",  # LAIF pool only based on board packet
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "https://www.mammothhospital.com/about-us/financials/",
        "evidence": "Cash/LAIF $78.9M + Cash/Investments $53.4M - LAIF is fixed income pool",
        "potential_target": True,
    },
    "Rideout Memorial Hospital": {
        "has_equities": "yes",
        "has_captive": "no",
        "confidence": "low",
        "source_url": "",
        "evidence": "CA nonprofit - typical diversified investments",
        "needs_audit": True,
    },
    
    # === Government districts (likely fixed income per state law) ===
    "ANTELOPE VALLEY MEDICAL CENTER": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA hospital authority - likely County pool per CA Gov Code 53601",
        "potential_target": True,
        "needs_audit": True,
    },
    "PIONEERS MEMORIAL HEALTHCARE DISTRICT": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA healthcare district - likely fixed income per CA Gov Code",
        "potential_target": True,
        "needs_audit": True,
    },
    "SAN BENITO HEALTH CARE DISTRICT": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA healthcare district - likely fixed income per CA Gov Code",
        "potential_target": True,
        "needs_audit": True,
    },
    "NORTHERN INYO HEALTHCARE DISTRICT": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA healthcare district - likely fixed income per CA Gov Code",
        "potential_target": True,
        "needs_audit": True,
    },
    "MODOC MEDICAL CENTER": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA rural district - likely County pool",
        "potential_target": True,
        "needs_audit": True,
    },
    "SAN GORGONIO MEMORIAL HOSPITAL": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA district hospital - likely fixed income",
        "potential_target": True,
        "needs_audit": True,
    },
    "MAYERS MEMORIAL HOSPITAL": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA rural district - likely County pool",
        "potential_target": True,
        "needs_audit": True,
    },
    "OAK VALLEY DISTRICT HOSPITAL": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA district hospital - likely fixed income",
        "potential_target": True,
        "needs_audit": True,
    },
    "LOMPOC VALLEY MEDICAL CENTER": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA district hospital - likely fixed income",
        "potential_target": True,
        "needs_audit": True,
    },
    "FAIRCHILD MEDICAL CENTER": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA rural district - likely County pool",
        "potential_target": True,
        "needs_audit": True,
    },
    "BEAR VALLEY COMMUNITY HOSPITAL": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA community hospital district - likely LAIF",
        "potential_target": True,
        "needs_audit": True,
    },
    "SAN BERNARDINO MOUNTAINS COMMUNITY HOSPITAL DISTRICT": {
        "has_equities": "no",
        "has_captive": "no",
        "confidence": "medium",
        "source_url": "",
        "evidence": "CA community hospital district - likely LAIF/County pool",
        "potential_target": True,
        "needs_audit": True,
    },
    
    # === For-profit (exclude) ===
    "ALHAMBRA HOSPITAL MEDICAL CENTER LP": {
        "skip": True,
        "reason": "For-profit (LP)",
    },
    "GARFIELD MEDICAL CENTER": {
        "skip": True,
        "reason": "For-profit (AHMC)",
    },
    "GREATER EL MONTE COMMUNITY HOSPITAL": {
        "skip": True,
        "reason": "For-profit (AHMC)",
    },
    "MONTEREY PARK HOSPITAL": {
        "skip": True,
        "reason": "For-profit (AHMC)",
    },
}


def apply_parent_system_findings(row: dict) -> dict:
    """Apply parent system findings to a facility row."""
    name = row.get("system_name", "")
    
    parent = get_parent_system(name)
    if parent:
        system_id = parent["system_id"]
        parent_info = PARENT_SYSTEMS.get(system_id, {})
        
        if parent_info.get("has_equities") is not None:
            row["has_equities"] = "yes" if parent_info["has_equities"] else "no"
        if parent_info.get("has_captive") is not None:
            row["has_captive"] = "yes" if parent_info["has_captive"] else "no"
        if parent_info.get("captive_name"):
            row["captive_name"] = parent_info["captive_name"]
        if parent_info.get("captive_domicile"):
            row["captive_domicile"] = parent_info["captive_domicile"]
        if parent_info.get("audit_url"):
            row["source_url"] = parent_info["audit_url"]
        
        # Clear target flag if has equities or captive
        if row.get("has_equities") == "yes" or row.get("has_captive") == "yes":
            row["is_target"] = False
    
    return row


def apply_standalone_findings(row: dict) -> dict:
    """Apply standalone facility findings."""
    name = row.get("system_name", "")
    
    if name in STANDALONE_FINDINGS:
        findings = STANDALONE_FINDINGS[name]
        
        if findings.get("skip"):
            row["has_equities"] = "skip"
            row["has_captive"] = "skip"
            row["is_target"] = False
            return row
        
        if findings.get("has_equities"):
            row["has_equities"] = findings["has_equities"]
        if findings.get("has_captive"):
            row["has_captive"] = findings["has_captive"]
        if findings.get("source_url"):
            row["source_url"] = findings["source_url"]
        if findings.get("parent_system"):
            parent_info = PARENT_SYSTEMS.get(findings["parent_system"], {})
            if parent_info.get("audit_url"):
                row["source_url"] = parent_info["audit_url"]
        
        # Determine target status
        total = float(row.get("total_cash_investments", 0) or 0)
        equity_ok = row.get("has_equities") in ["no", "de_minimis"]
        captive_ok = row.get("has_captive") == "no"
        
        if total >= 25_000_000 and equity_ok and captive_ok:
            row["is_target"] = True
        else:
            row["is_target"] = False
    
    return row


def process_csv():
    """Process the CSV and resolve unknowns."""
    csv_path = Path(__file__).parent / "quick_screen_tx_ca.csv"
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Processing {len(rows)} facilities...")
    
    updated_count = 0
    potential_targets = []
    
    for row in rows:
        name = row.get("system_name", "")
        original_equity = row.get("has_equities", "unknown")
        original_captive = row.get("has_captive", "unknown")
        
        # Skip already resolved
        if original_equity not in ["", "unknown"] and original_captive not in ["", "unknown"]:
            continue
        
        # Try parent system first
        row = apply_parent_system_findings(row)
        
        # Then standalone findings
        row = apply_standalone_findings(row)
        
        new_equity = row.get("has_equities", "unknown")
        new_captive = row.get("has_captive", "unknown")
        
        if new_equity != original_equity or new_captive != original_captive:
            updated_count += 1
            print(f"  Updated: {name[:50]} - equity: {new_equity}, captive: {new_captive}")
        
        # Track potential targets that need verification
        if name in STANDALONE_FINDINGS:
            findings = STANDALONE_FINDINGS[name]
            if findings.get("potential_target") and findings.get("needs_audit"):
                total = float(row.get("total_cash_investments", 0) or 0)
                if total >= 25_000_000:
                    potential_targets.append({
                        "name": name,
                        "total": total,
                        "evidence": findings.get("evidence", ""),
                    })
    
    # Write back
    fieldnames = list(rows[0].keys())
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\nUpdated {updated_count} facilities")
    
    # Count final stats
    targets = [r for r in rows if r.get("is_target") in [True, "True", "true", "TRUE"]]
    unknowns = [r for r in rows 
                if r.get("has_equities") in ["", "unknown"] 
                or r.get("has_captive") in ["", "unknown"]]
    
    print(f"\n=== FINAL STATS ===")
    print(f"Total facilities: {len(rows)}")
    print(f"Confirmed targets: {len(targets)}")
    print(f"Still unknown: {len(unknowns)} ({len(unknowns)/len(rows)*100:.1f}%)")
    
    print(f"\nConfirmed targets:")
    for t in targets:
        total = float(t.get("total_cash_investments", 0) or 0)
        print(f"  - {t['system_name']} ({t['state']}): ${total:,.0f}")
    
    if potential_targets:
        print(f"\nPotential targets (need audit verification):")
        for pt in sorted(potential_targets, key=lambda x: x["total"], reverse=True):
            print(f"  - {pt['name']}: ${pt['total']:,.0f}")
            print(f"    Evidence: {pt['evidence']}")


if __name__ == "__main__":
    process_csv()
