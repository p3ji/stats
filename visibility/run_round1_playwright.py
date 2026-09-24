"""Automated capture harness for Round 1 re-audit using Playwright (Amendments A2, A11, A12).

Captures the ordinary Bing SERP (bing_serp_ai) for all 26 experiment queries:
  - Wave 1: 11 queries (7 treatment, 4 control)
  - Wave 2: 15 queries (10 treatment, 5 control)

Features:
  1. High-resolution full-page screenshot evidence (.png).
  2. Verbatim answer and SERP text evidence (.txt).
  3. Automatic detection of ai_module state: populated / empty / absent (A12).
  4. Mismatched-load detection via content-word relevance guard (A12).
  5. Automatic cookie-consent modal dismissal and Bing b_content unhiding.
  6. Outputs skeleton CSV rows ready for blinded coding (A3).

Usage:
  # Test a single query:
  python visibility/run_round1_playwright.py --id POP-001 --run 1
  
  # Run a full pass (all 26 queries for run 1):
  python visibility/run_round1_playwright.py --run 1
  
  # Run pass 2 and pass 3:
  python visibility/run_round1_playwright.py --run 2
  python visibility/run_round1_playwright.py --run 3
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "visibility" / "results"
EVIDENCE_DIR = RESULTS / "round1_evidence"
BROWSER_PROFILE = REPO / "visibility" / "cache" / "playwright_bing_profile"

ENGINE = "bing_serp_ai"
SERP = "https://www.bing.com/search?q={}"
DATE = "2026-08-31"

FIELDS = [
    "run_date", "engine", "wave", "run", "id", "subject", "arm", "query_asked",
    "ai_module", "answerable", "citation_class", "cited_sources", "answer_value",
    "statcan_value", "statcan_vintage_cited", "best_available_vintage",
    "value_match", "evidence", "screenshot", "note",
]

QUERIES = [
    # Wave 1 Treatment (7)
    {"wave": 1, "id": "SOC-004", "subject": "society_and_community", "arm": "treatment", "query": "are charitable donations declining in canada"},
    {"wave": 1, "id": "LAB-002", "subject": "labour", "arm": "treatment", "query": "average salary in canada by age"},
    {"wave": 1, "id": "LAB-003", "subject": "labour", "arm": "treatment", "query": "average salary in canada by province"},
    {"wave": 1, "id": "SOC-001", "subject": "society_and_community", "arm": "treatment", "query": "volunteering in canada statistics"},
    {"wave": 1, "id": "SOC-002", "subject": "society_and_community", "arm": "treatment", "query": "what percentage of canadians volunteer"},
    {"wave": 1, "id": "SOC-024", "subject": "society_and_community", "arm": "treatment", "query": "who does more housework men or women canada"},
    {"wave": 1, "id": "DIG-014", "subject": "digital_economy_and_society", "arm": "treatment", "query": "how many businesses in canada use artificial intelligence"},
    # Wave 1 Control (4)
    {"wave": 1, "id": "LAB-014", "subject": "labour", "arm": "control", "query": "how many canadians work in the public sector"},
    {"wave": 1, "id": "SOC-010", "subject": "society_and_community", "arm": "control", "query": "do canadians trust the government"},
    {"wave": 1, "id": "SOC-016", "subject": "society_and_community", "arm": "control", "query": "how religious is canada"},
    {"wave": 1, "id": "SOC-005", "subject": "society_and_community", "arm": "control", "query": "loneliness in canada statistics"},
    # Wave 2 Treatment (10)
    {"wave": 2, "id": "HEA-024", "subject": "health", "arm": "treatment", "query": "self rated mental health canada"},
    {"wave": 2, "id": "HEA-001", "subject": "health", "arm": "treatment", "query": "mental health in canada statistics"},
    {"wave": 2, "id": "HEA-016", "subject": "health", "arm": "treatment", "query": "how many canadians have a family doctor"},
    {"wave": 2, "id": "HEA-017", "subject": "health", "arm": "treatment", "query": "how many canadians don't have a family doctor"},
    {"wave": 2, "id": "HEA-025", "subject": "health", "arm": "treatment", "query": "does income affect health in canada"},
    {"wave": 2, "id": "POP-001", "subject": "population_and_demography", "arm": "treatment", "query": "population of canada"},
    {"wave": 2, "id": "POP-002", "subject": "population_and_demography", "arm": "treatment", "query": "population of canada by province"},
    {"wave": 2, "id": "IMM-001", "subject": "immigration_and_ethnocultural_diversity", "arm": "treatment", "query": "how many immigrants in canada"},
    {"wave": 2, "id": "IMM-013", "subject": "immigration_and_ethnocultural_diversity", "arm": "treatment", "query": "what percentage of canada population is foreign born"},
    {"wave": 2, "id": "IMM-014", "subject": "immigration_and_ethnocultural_diversity", "arm": "treatment", "query": "which cities do most immigrants settle in canada"},
    # Wave 2 Control (5)
    {"wave": 2, "id": "HEA-019", "subject": "health", "arm": "control", "query": "unmet health care needs canada"},
    {"wave": 2, "id": "HEA-002", "subject": "health", "arm": "control", "query": "mental health in canadian youth"},
    {"wave": 2, "id": "IMM-007", "subject": "immigration_and_ethnocultural_diversity", "arm": "control", "query": "visible minorities in canada percentage"},
    {"wave": 2, "id": "IMM-008", "subject": "immigration_and_ethnocultural_diversity", "arm": "control", "query": "largest visible minority in canada"},
    {"wave": 2, "id": "IMM-010", "subject": "immigration_and_ethnocultural_diversity", "arm": "control", "query": "ethnic groups in canada percentages"},
]

STOPWORDS = {"a", "an", "the", "in", "of", "on", "by", "to", "is", "are", "do",
             "does", "how", "what", "who", "many", "much", "more", "and", "or"}


def _relevance(query: str, text: str) -> float:
    """Fraction of the query's content words present in the captured text (A12)."""
    words = [w for w in "".join(c if c.isalnum() else " " for c in query.lower()).split()
             if w not in STOPWORDS and len(w) > 2]
    if not words:
        return 1.0
    present = set(re.findall(r"[a-z0-9]+", text.lower()))
    return sum(1 for w in words if w in present) / len(words)


def _detect_ai_module(page, b_results_text: str) -> tuple[str, str]:
    """Detect state of the inline AI module: populated, empty, or absent (A12).
    Returns (ai_module_state, answer_text)."""
    # On Bing SERP, the inline AI module is rendered as li.b_ans or li.b_top before organic li.b_algo
    first_li = page.query_selector("#b_results > li")
    if not first_li:
        return "absent", ""
        
    cls = first_li.get_attribute("class") or ""
    text = first_li.inner_text().strip()
    
    # Check if first_li is an answer module
    if "b_ans" in cls or "b_top" in cls:
        # Check for AI synthesis signatures (thumbs up/down, Copilot, or multi-source synthesis)
        is_ai = ("Like" in text and "Dislike" in text) or "copilot" in text.lower() or "generated with ai" in text.lower()
        if is_ai and len(text) > 60:
            return "populated", text
        elif is_ai:
            return "empty", ""
            
    # Also check if any top container has the AI module
    ai_box = page.query_selector("#b_results > li.b_ans, #ans_top, .b_subModule")
    if ai_box:
        box_text = ai_box.inner_text().strip()
        if ("Like" in box_text and "Dislike" in box_text) or "copilot" in box_text.lower():
            if len(box_text) > 60:
                return "populated", box_text
            else:
                return "empty", ""
                
    return "absent", ""


def capture_query(page, item: dict, run: int, date: str) -> dict:
    qid = item["id"]
    wave = item["wave"]
    query = item["query"]
    arm = item["arm"]
    subject = item["subject"]
    
    print(f"[{qid}] Wave {wave} Run {run}: '{query}'")
    
    ts = int(time.time())
    url = f"{SERP.format(urllib.parse.quote_plus(query))}&setlang=en-ca&cc=CA&cb={ts}"
    
    # Navigate
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)
    
    # Handle cookie consent if visible
    try:
        accept_btn = page.query_selector("#bnp_btn_accept, button:has-text('Accept')")
        if accept_btn:
            accept_btn.click()
            time.sleep(0.5)
    except Exception:
        pass
        
    # Unhide b_content if Bing injected visibility: hidden
    page.evaluate("let el = document.getElementById('b_content'); if (el) el.style.visibility = 'visible';")
    time.sleep(1)
    
    # Get page text
    results_el = page.query_selector("#b_results")
    text = results_el.inner_text() if results_el else page.inner_text("body")
    
    # Relevance check (A12 guard against mismatched first loads)
    rel = _relevance(query, text)
    if rel < 0.4:
        print(f"  Warning: low relevance ({rel:.0%}), triggering reload...")
        page.goto(f"{url}&retry=1", wait_until="domcontentloaded")
        time.sleep(3)
        page.evaluate("let el = document.getElementById('b_content'); if (el) el.style.visibility = 'visible';")
        text = (page.query_selector("#b_results") or page).inner_text()
        rel = _relevance(query, text)
        print(f"  Post-reload relevance: {rel:.0%}")
        
    # Detect AI module state
    ai_module, ans_text = _detect_ai_module(page, text)
    print(f"  ai_module: {ai_module} (relevance: {rel:.0%}, page_chars: {len(text)})")
    
    # Save evidence
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    base_name = f"bing_serp_ai_w{wave}_{qid}_run{run}_{date}"
    evidence_file = f"{base_name}.txt"
    screenshot_file = f"{base_name}.png"
    
    # Full-page screenshot
    screenshot_path = EVIDENCE_DIR / screenshot_file
    page.screenshot(path=str(screenshot_path), full_page=True)
    
    # Text evidence file
    evidence_path = EVIDENCE_DIR / evidence_file
    with open(evidence_path, "w", encoding="utf-8") as f:
        f.write(f"# query: {query}\n")
        f.write(f"# id: {qid}\n")
        f.write(f"# wave: {wave}\n")
        f.write(f"# run: {run}\n")
        f.write(f"# date: {date}\n")
        f.write(f"# url: {url}\n")
        f.write(f"# ai_module: {ai_module}\n")
        f.write(f"# relevance: {rel:.2f}\n\n")
        if ans_text:
            f.write("=== AI MODULE EXTRACTED TEXT ===\n")
            f.write(ans_text + "\n\n")
        f.write("=== FULL SERP TEXT ===\n")
        f.write(text + "\n")
        
    return {
        "run_date": date,
        "engine": ENGINE,
        "wave": wave,
        "run": run,
        "id": qid,
        "subject": subject,
        "arm": arm,
        "query_asked": query,
        "ai_module": ai_module,
        "answerable": "",
        "citation_class": "",
        "cited_sources": "",
        "answer_value": "",
        "statcan_value": "",
        "statcan_vintage_cited": "",
        "best_available_vintage": "",
        "value_match": "",
        "evidence": evidence_file,
        "screenshot": screenshot_file,
        "note": f"relevance={rel:.2f}",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=int, choices=[1, 2, 3], default=1, help="Pass / run number (1, 2, or 3)")
    p.add_argument("--wave", type=int, choices=[1, 2], help="Filter to specific wave")
    p.add_argument("--id", help="Run a single query ID for testing")
    p.add_argument("--headless", action="store_true", help="Run in headless mode")
    p.add_argument("--date", default=DATE, help="Run date string")
    args = p.parse_args()

    # Filter queries
    qs = QUERIES
    if args.wave:
        qs = [q for q in qs if q["wave"] == args.wave]
    if args.id:
        qs = [q for q in qs if q["id"] == args.id]
        
    print(f"Starting Round 1 capture on {ENGINE}: {len(qs)} queries for run {args.run}")
    
    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            channel="msedge",
            headless=args.headless,
            locale="en-CA",
            timezone_id="America/Toronto",
            geolocation={"latitude": 45.4215, "longitude": -75.6972},
            permissions=["geolocation"],
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        captured_rows = []
        for item in qs:
            row = capture_query(page, item, run=args.run, date=args.date)
            captured_rows.append(row)
            # Brief pause between queries
            time.sleep(1.5)
            
        context.close()

    # Append to CSV
    csv_file = RESULTS / f"round1_bing_serp_ai_{args.date}.csv"
    file_exists = csv_file.exists()
    
    with open(csv_file, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerows(captured_rows)
        
    print(f"\nSuccessfully captured {len(captured_rows)} items -> {csv_file}")
    print(f"Evidence files written to -> {EVIDENCE_DIR}")


if __name__ == "__main__":
    main()
