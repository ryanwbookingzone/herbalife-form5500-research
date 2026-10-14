#!/usr/bin/env python3
"""
Healthcare System Financial Extraction Pipeline
================================================
Extracts financial data from audited statements and interim reports for
US government hospital systems and nonprofit healthcare organizations.

Designed for systems with >$25M cash+investments.

Usage:
    python extract_healthcare_financials.py \
        --config configs/sarasota.json \
        --output-dir ./output
        
    python extract_healthcare_financials.py \
        --org-name "Organization Name" \
        --org-id "ORG-ID" \
        --pdfs "path/to/audit.pdf,path/to/interim.pdf" \
        --output-dir "./output"
        
Environment Variables (for Frappe auth):
    FRAPPE_API_KEY - API key
    FRAPPE_API_SECRET - API secret
    (Or use --frappe-token for combined token)
"""

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse
import tempfile

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class ExtractionPattern:
    """Pattern for extracting a financial metric."""
    metric_name: str
    category: str  # cash_and_investments, portfolio_policy, self_insurance, debt, ratings, revenue, other
    patterns: List[str]  # Regex patterns to match
    value_type: str  # currency, number, text, percentage
    page_hints: List[str] = field(default_factory=list)  # Keywords to find relevant page


@dataclass
class OrgConfig:
    """Configuration for extracting data from a specific organization."""
    org_name: str
    org_id: str
    segment: str  # Healthcare, Government, Municipal, Nonprofit
    state: str
    country: str = "United States"
    fiscal_year_end_month: int = 9  # September = 9
    pdf_sources: List[Dict[str, str]] = field(default_factory=list)  # [{url, type, fiscal_year}]
    extraction_patterns: List[Dict] = field(default_factory=list)
    expected_values: Dict[str, str] = field(default_factory=dict)


@dataclass
class FinancialFigure:
    """Represents a single financial figure extracted from source documents."""
    metric_name: str
    value_text: str
    value_numeric: Optional[float]
    as_of_date: str
    fiscal_year: str
    period_type: str  # annual, interim, quarterly
    source_url: str
    source_domain: str
    pdf_page: int
    source_quote: str
    category: str
    verified: bool = False
    expected_value: Optional[str] = None
    match_status: str = 'not_checked'
    screenshot_path: Optional[str] = None
    
    def content_hash(self) -> str:
        """Generate unique hash for deduplication."""
        content = f"{self.metric_name}|{self.value_text}|{self.as_of_date}|{self.source_url}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Default extraction patterns for healthcare financials
DEFAULT_PATTERNS = [
    ExtractionPattern(
        metric_name="Cash and Cash Equivalents",
        category="cash_and_investments",
        patterns=[
            r"Cash and cash equivalents[^\d]*\$?\s*([\d,]+(?:\.\d{2})?)",
            r"Cash and equivalents[^\d]*\$?\s*([\d,]+(?:\.\d{2})?)",
        ],
        value_type="currency",
        page_hints=["Balance Sheet", "Assets"]
    ),
    ExtractionPattern(
        metric_name="Board Designated Investments",
        category="cash_and_investments",
        patterns=[
            r"Board designated investments[^\d]*\$?\s*([\d,]+(?:\.\d{2})?)",
            r"Board-designated investments[^\d]*\$?\s*([\d,]+(?:\.\d{2})?)",
        ],
        value_type="currency",
        page_hints=["Balance Sheet", "Noncurrent assets"]
    ),
    ExtractionPattern(
        metric_name="Restricted Investments",
        category="cash_and_investments",
        patterns=[
            r"Restricted investments[^\d]*\$?\s*([\d,]+(?:\.\d{2})?)",
        ],
        value_type="currency",
        page_hints=["Balance Sheet", "Noncurrent assets"]
    ),
    ExtractionPattern(
        metric_name="Total Operating Revenue",
        category="revenue",
        patterns=[
            r"Total operating revenues?[^\d]*\$?\s*([\d,]+(?:\.\d{2})?)",
        ],
        value_type="currency",
        page_hints=["Statement of Revenues", "Operating revenues"]
    ),
    ExtractionPattern(
        metric_name="Days Cash on Hand",
        category="cash_and_investments",
        patterns=[
            r"Days cash on hand[^\d]*([\d]+(?:\.\d)?)",
        ],
        value_type="number",
        page_hints=["Ratios", "Liquidity"]
    ),
    ExtractionPattern(
        metric_name="Total Long-Term Debt",
        category="debt",
        patterns=[
            r"Long.term debt.*?([\d,]+(?:\.\d{2})?)",
            r"Total.*debt.*?([\d,]+(?:\.\d{2})?)",
        ],
        value_type="currency",
        page_hints=["Balance Sheet", "Liabilities", "Long-term debt"]
    ),
    ExtractionPattern(
        metric_name="Professional Liability Reserve",
        category="self_insurance",
        patterns=[
            r"Professional liabilit(?:y|ies)[^\d]*([\d,]+(?:\.\d{2})?)",
            r"malpractice.*accrued[^\d]*\$?\s*([\d,]+(?:\.\d{2})?)",
        ],
        value_type="currency",
        page_hints=["Malpractice", "Self-insur", "Professional liability"]
    ),
    ExtractionPattern(
        metric_name="Fitch Rating",
        category="ratings",
        patterns=[
            r"Fitch.*(?:rating|affirmed)[^\w]*(AA[+-]?|A[+-]?|BBB[+-]?)",
            r"Fitch[:\s]*(AA[+-]?|A[+-]?|BBB[+-]?)",
        ],
        value_type="text",
        page_hints=["Rating", "Credit"]
    ),
    ExtractionPattern(
        metric_name="Moody's Rating",
        category="ratings",
        patterns=[
            r"Moody(?:'s)?.*(?:rating|affirmed|upgraded)[^\w]*(Aa[123]|A[123]|Baa[123])",
            r"Moody(?:'s)?[:\s]*(Aa[123]|A[123]|Baa[123])",
        ],
        value_type="text",
        page_hints=["Rating", "Credit", "Moody"]
    ),
]


def parse_currency(text: str) -> Optional[float]:
    """Parse currency string to float."""
    if not text:
        return None
    cleaned = re.sub(r'[,$\s]', '', str(text))
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]
    multiplier = 1
    if cleaned.upper().endswith('B'):
        multiplier = 1_000_000_000
        cleaned = cleaned[:-1]
    elif cleaned.upper().endswith('M'):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]
    elif cleaned.upper().endswith('K'):
        multiplier = 1_000
        cleaned = cleaned[:-1]
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pdftotext."""
    result = subprocess.run(
        ['pdftotext', '-layout', pdf_path, '-'],
        capture_output=True, text=True
    )
    return result.stdout


def render_pdf_page(pdf_path: str, page_num: int, output_path: str, dpi: int = 110) -> bool:
    """Render a specific PDF page to PNG."""
    result = subprocess.run(
        ['pdftoppm', '-png', '-r', str(dpi), '-f', str(page_num), '-l', str(page_num), 
         pdf_path, output_path.replace('.png', '')],
        capture_output=True
    )
    expected_file = f"{output_path.replace('.png', '')}-{page_num}.png"
    if os.path.exists(expected_file):
        os.rename(expected_file, output_path)
        return True
    single_page_file = f"{output_path.replace('.png', '')}.png"
    if os.path.exists(single_page_file):
        os.rename(single_page_file, output_path)
        return True
    return False


def find_page_for_content(pdf_text: str, search_terms: List[str]) -> Optional[int]:
    """Find the page number containing specific content."""
    pages = pdf_text.split('\f')
    for i, page in enumerate(pages, 1):
        if all(term.lower() in page.lower() for term in search_terms):
            return i
    for i, page in enumerate(pages, 1):
        if any(term.lower() in page.lower() for term in search_terms):
            return i
    return None


def download_pdf(url: str, output_dir: Path) -> Optional[str]:
    """Download PDF from URL."""
    if not HAS_REQUESTS:
        print("Warning: requests library not available, skipping download")
        return None
    try:
        filename = url.split('/')[-1].split('?')[0]
        if not filename.endswith('.pdf'):
            filename = hashlib.md5(url.encode()).hexdigest()[:8] + '.pdf'
        output_path = output_dir / filename
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(resp.content)
        return str(output_path)
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None


def extract_with_pattern(pdf_text: str, pattern: ExtractionPattern) -> List[Tuple[str, int, str]]:
    """Extract values matching a pattern, return list of (value, page_num, quote)."""
    results = []
    pages = pdf_text.split('\f')
    
    for page_num, page_text in enumerate(pages, 1):
        # Check if page might be relevant
        is_relevant = not pattern.page_hints or any(
            hint.lower() in page_text.lower() for hint in pattern.page_hints
        )
        if not is_relevant:
            continue
            
        for regex in pattern.patterns:
            matches = re.finditer(regex, page_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                value = match.group(1) if match.groups() else match.group(0)
                # Get surrounding context for quote
                start = max(0, match.start() - 50)
                end = min(len(page_text), match.end() + 50)
                quote = page_text[start:end].replace('\n', ' ').strip()
                results.append((value, page_num, quote))
    
    return results


def extract_figures_generic(
    pdf_text: str,
    pdf_url: str,
    fiscal_year: str,
    period_type: str,
    as_of_date: str,
    patterns: List[ExtractionPattern],
    expected_values: Dict[str, str] = None
) -> List[FinancialFigure]:
    """Extract figures using pattern matching."""
    figures = []
    expected_values = expected_values or {}
    domain = urlparse(pdf_url).netloc
    
    for pattern in patterns:
        matches = extract_with_pattern(pdf_text, pattern)
        if matches:
            # Take the first match (could be enhanced to pick best)
            value, page_num, quote = matches[0]
            
            if pattern.value_type == 'currency':
                numeric = parse_currency(value)
                value_text = f"${value}" if not value.startswith('$') else value
            elif pattern.value_type == 'number':
                numeric = float(re.sub(r'[^\d.]', '', value)) if value else None
                value_text = value
            else:
                numeric = None
                value_text = value
            
            expected = expected_values.get(pattern.metric_name)
            match_status = 'not_checked'
            if expected:
                # Simple match check
                if expected.lower() in value_text.lower() or value_text.lower() in expected.lower():
                    match_status = 'match'
                else:
                    match_status = 'mismatch'
            
            figures.append(FinancialFigure(
                metric_name=pattern.metric_name,
                value_text=value_text,
                value_numeric=numeric,
                as_of_date=as_of_date,
                fiscal_year=fiscal_year,
                period_type=period_type,
                source_url=pdf_url,
                source_domain=domain,
                pdf_page=page_num,
                source_quote=quote[:200],
                category=pattern.category,
                verified=True,
                expected_value=expected,
                match_status=match_status
            ))
    
    return figures


def load_org_config(config_path: str) -> OrgConfig:
    """Load organization configuration from JSON file."""
    with open(config_path) as f:
        data = json.load(f)
    return OrgConfig(**data)


def write_figures_csv(figures: List[FinancialFigure], output_path: str):
    """Write figures to CSV file."""
    fieldnames = [
        'metric_name', 'value_text', 'value_numeric', 'as_of_date', 'fiscal_year',
        'period_type', 'category', 'verified', 'expected_value', 'match_status',
        'source_url', 'pdf_page', 'source_quote', 'screenshot_path', 'content_hash'
    ]
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for fig in figures:
            row = {
                'metric_name': fig.metric_name,
                'value_text': fig.value_text,
                'value_numeric': fig.value_numeric,
                'as_of_date': fig.as_of_date,
                'fiscal_year': fig.fiscal_year,
                'period_type': fig.period_type,
                'category': fig.category,
                'verified': fig.verified,
                'expected_value': fig.expected_value,
                'match_status': fig.match_status,
                'source_url': fig.source_url,
                'pdf_page': fig.pdf_page,
                'source_quote': fig.source_quote[:200] if fig.source_quote else '',
                'screenshot_path': fig.screenshot_path,
                'content_hash': fig.content_hash()
            }
            writer.writerow(row)


def generate_match_report(figures: List[FinancialFigure], org_name: str) -> str:
    """Generate verification report."""
    report_lines = [
        "=" * 80,
        f"FINANCIAL FIGURE VERIFICATION REPORT: {org_name}",
        "=" * 80,
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "-" * 80,
        "SUMMARY",
        "-" * 80,
    ]
    
    matches = [f for f in figures if f.match_status == 'match']
    mismatches = [f for f in figures if f.match_status == 'mismatch']
    unchecked = [f for f in figures if f.match_status == 'not_checked']
    
    report_lines.append(f"Total figures: {len(figures)}")
    report_lines.append(f"Matches: {len(matches)}")
    report_lines.append(f"Mismatches: {len(mismatches)}")
    report_lines.append(f"Not checked: {len(unchecked)}")
    report_lines.append("")
    
    if mismatches:
        report_lines.append("-" * 80)
        report_lines.append("MISMATCHES (requires review)")
        report_lines.append("-" * 80)
        for fig in mismatches:
            report_lines.append(f"\n{fig.metric_name}:")
            report_lines.append(f"  Extracted: {fig.value_text}")
            report_lines.append(f"  Expected:  {fig.expected_value}")
            report_lines.append(f"  Source:    Page {fig.pdf_page}")
    
    report_lines.append("\n" + "-" * 80)
    report_lines.append("ALL FIGURES BY CATEGORY")
    report_lines.append("-" * 80)
    
    categories = {}
    for fig in figures:
        if fig.category not in categories:
            categories[fig.category] = []
        categories[fig.category].append(fig)
    
    for cat, cat_figures in sorted(categories.items()):
        report_lines.append(f"\n{cat.upper().replace('_', ' ')}:")
        for fig in cat_figures:
            status = "✓" if fig.match_status == 'match' else "✗" if fig.match_status == 'mismatch' else "?"
            report_lines.append(f"  [{status}] {fig.metric_name}: {fig.value_text} ({fig.as_of_date})")
    
    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(description='Extract healthcare system financial data')
    parser.add_argument('--config', help='Path to organization config JSON file')
    parser.add_argument('--org-name', help='Organization name (if no config)')
    parser.add_argument('--org-id', help='Organization identifier (if no config)')
    parser.add_argument('--pdfs', help='Comma-separated PDF paths or URLs (if no config)')
    parser.add_argument('--output-dir', default='./output', help='Output directory')
    parser.add_argument('--frappe-url', help='Frappe base URL')
    parser.add_argument('--frappe-token', help='Frappe API token')
    parser.add_argument('--skip-screenshots', action='store_true')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = output_dir / 'screenshots'
    screenshots_dir.mkdir(exist_ok=True)
    
    # Load configuration
    if args.config:
        config = load_org_config(args.config)
        org_name = config.org_name
        org_id = config.org_id
        pdf_sources = config.pdf_sources
    elif args.org_name and args.pdfs:
        org_name = args.org_name
        org_id = args.org_id or org_name.replace(' ', '-')[:20]
        pdf_sources = [{'url': p.strip(), 'type': 'audit', 'fiscal_year': 'FY2025'} 
                       for p in args.pdfs.split(',')]
    else:
        parser.error("Either --config or --org-name and --pdfs are required")
    
    print(f"Processing: {org_name}")
    print(f"Output directory: {output_dir}")
    
    all_figures = []
    
    # Process each PDF source
    for source in pdf_sources:
        url = source['url']
        pdf_type = source.get('type', 'audit')
        fiscal_year = source.get('fiscal_year', 'FY2025')
        as_of_date = source.get('as_of_date', '2025-09-30')
        period_type = 'annual' if pdf_type == 'audit' else 'interim'
        
        print(f"\nProcessing: {url}")
        
        # Download or use local file
        if url.startswith('http'):
            pdf_path = download_pdf(url, output_dir)
            if not pdf_path:
                continue
        else:
            pdf_path = url
        
        # Extract text
        pdf_text = extract_text_from_pdf(pdf_path)
        if not pdf_text:
            print(f"  Warning: Could not extract text from {pdf_path}")
            continue
        
        print(f"  Extracted {len(pdf_text)} characters")
        
        # Extract figures using default patterns
        figures = extract_figures_generic(
            pdf_text=pdf_text,
            pdf_url=url,
            fiscal_year=fiscal_year,
            period_type=period_type,
            as_of_date=as_of_date,
            patterns=DEFAULT_PATTERNS
        )
        
        print(f"  Found {len(figures)} figures")
        all_figures.extend(figures)
        
        # Generate screenshots for key pages
        if not args.skip_screenshots:
            pages_to_capture = set()
            for fig in figures:
                pages_to_capture.add(fig.pdf_page)
            
            for page_num in sorted(pages_to_capture)[:5]:  # Limit to 5 pages
                screenshot_name = f"{Path(pdf_path).stem}_page{page_num}.png"
                screenshot_path = screenshots_dir / screenshot_name
                if render_pdf_page(pdf_path, page_num, str(screenshot_path)):
                    print(f"  Screenshot: {screenshot_name}")
                    for fig in figures:
                        if fig.pdf_page == page_num:
                            fig.screenshot_path = str(screenshot_path)
    
    if not all_figures:
        print("No figures extracted")
        return 1
    
    # Write outputs
    csv_path = output_dir / 'financial_figures.csv'
    write_figures_csv(all_figures, str(csv_path))
    print(f"\nWrote CSV: {csv_path}")
    
    report = generate_match_report(all_figures, org_name)
    report_path = output_dir / 'verification_report.txt'
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"Wrote report: {report_path}")
    
    print("\n" + report)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
