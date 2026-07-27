"""Capture harness for re-baseline and re-audit rounds (amendments A2, A11).

This does NOT judge whether an engine cited StatCan -- that stays a human call.
It removes the three places manual capture goes wrong:

  1. Query drift. Phrasing is replayed verbatim from the wave's own baseline CSV,
     so a re-audit cannot silently ask a slightly different question.
  2. Lost evidence. Every run's raw answer text is written to evidence/ under a
     deterministic name before any coding happens.
  3. Eyeballed modal coding. A2 requires 3 runs per query and the modal code;
     `summarize` computes it and flags disagreement instead of trusting a glance.

Surface is pinned to the ordinary Bing SERP per A11 -- see docs/mirror_experiment.md.

Usage:
  python visibility/rebaseline.py plan --wave 1
  python visibility/rebaseline.py record --wave 1 --id SOC-004 --run 1 < answer.txt
  python visibility/rebaseline.py summarize --wave 1
"""

import argparse
import csv
import datetime
import os
import sys
import urllib.parse
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO, "visibility", "results")
EVIDENCE = os.path.join(RESULTS, "rebaseline_evidence")

# A11: the single primary surface for both waves.
ENGINE = "bing_serp_ai"
SERP = "https://www.bing.com/search?q={}"
RUNS_PER_QUERY = 3  # A2 noise floor

# Source of truth for query phrasing, per wave. Replaying from the baseline CSV
# (rather than re-deriving from queries.yaml) guarantees the re-run asks exactly
# what the "before" measurement asked.
BASELINE = {
    1: "baseline_bing_copilot_2026-07-19.csv",
    2: "baseline_bing_wave2_2026-07-22.csv",
}

FIELDS = [
    "run_date", "engine", "wave", "run", "id", "subject", "arm", "query_asked",
    "answerable", "citation_class", "cited_sources", "answer_value",
    "statcan_value", "statcan_vintage_cited", "best_available_vintage",
    "value_match", "evidence", "note",
]


def _queries(wave):
    """Return [(id, subject, arm, query_asked)] replayed from the wave's baseline."""
    path = os.path.join(RESULTS, BASELINE[wave])
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    seen, out = set(), []
    for r in rows:
        qid = r["id"]
        if qid in seen:
            continue
        seen.add(qid)
        out.append((qid, r.get("subject", ""), r.get("arm", "tbd"), r["query_asked"]))
    return out


def _outfile(wave, date):
    return os.path.join(RESULTS, f"rebaseline_wave{wave}_{ENGINE}_{date}.csv")


def cmd_plan(args):
    qs = _queries(args.wave)
    print(f"Wave {args.wave} re-baseline -- {len(qs)} queries x {RUNS_PER_QUERY} runs "
          f"= {len(qs) * RUNS_PER_QUERY} captures")
    print(f"Surface: ordinary Bing SERP (A11). Engine label: {ENGINE}\n")
    for run in range(1, RUNS_PER_QUERY + 1):
        print(f"--- run {run} ---")
        for qid, _subject, _arm, q in qs:
            print(f"  {qid}  {SERP.format(urllib.parse.quote_plus(q))}")
        print()
    print("Run the three passes separately, not back to back per query -- consecutive\n"
          "identical queries can be served from cache and would understate the noise floor.")


def cmd_record(args):
    date = args.date or datetime.date.today().isoformat()
    qs = {q[0]: q for q in _queries(args.wave)}
    if args.id not in qs:
        sys.exit(f"unknown id {args.id!r} for wave {args.wave}; "
                 f"known: {', '.join(sorted(qs))}")
    qid, subject, arm, query = qs[args.id]

    text = sys.stdin.read()
    if not text.strip():
        sys.exit("no evidence text on stdin -- pipe the captured answer in")

    os.makedirs(EVIDENCE, exist_ok=True)
    ev = f"{ENGINE}_w{args.wave}_{qid}_run{args.run}_{date}.txt"
    with open(os.path.join(EVIDENCE, ev), "w", encoding="utf-8") as fh:
        fh.write(f"# query: {query}\n# url: {SERP.format(urllib.parse.quote_plus(query))}\n"
                 f"# captured: {date} run {args.run}\n\n{text}")

    out = _outfile(args.wave, date)
    new = not os.path.exists(out)
    with open(out, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({
            "run_date": date, "engine": ENGINE, "wave": args.wave, "run": args.run,
            "id": qid, "subject": subject, "arm": arm, "query_asked": query,
            "evidence": ev,
            # left blank deliberately -- coded by hand, blind to arm (A3)
            "answerable": "", "citation_class": "", "cited_sources": "",
            "answer_value": "", "statcan_value": "", "statcan_vintage_cited": "",
            "best_available_vintage": "", "value_match": "", "note": "",
        })
    print(f"evidence -> {os.path.join('visibility/results/rebaseline_evidence', ev)}")
    print(f"row      -> {os.path.relpath(out, REPO)} (coding fields blank -- fill by hand)")


def cmd_summarize(args):
    import glob
    pat = os.path.join(RESULTS, f"rebaseline_wave{args.wave}_{ENGINE}_*.csv")
    files = sorted(glob.glob(pat))
    if not files:
        sys.exit(f"no capture files matching {os.path.relpath(pat, REPO)}")
    rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            rows += list(csv.DictReader(fh))

    by_q = defaultdict(list)
    for r in rows:
        by_q[r["id"]].append(r)

    uncoded = [r for r in rows if not r.get("citation_class", "").strip()]
    if uncoded:
        print(f"WARNING: {len(uncoded)}/{len(rows)} captures are not yet coded.\n")

    print(f"Wave {args.wave} modal coding across runs ({ENGINE})\n")
    unstable = 0
    for qid in sorted(by_q):
        codes = [r["citation_class"].strip() for r in by_q[qid] if r["citation_class"].strip()]
        if not codes:
            print(f"  {qid:9s} (uncoded, {len(by_q[qid])} captures)")
            continue
        c = Counter(codes)
        modal, n = c.most_common(1)[0]
        flag = ""
        if len(c) > 1:
            unstable += 1
            flag = f"   <-- UNSTABLE {dict(c)}"
        if len(codes) < RUNS_PER_QUERY:
            flag += f"   (only {len(codes)}/{RUNS_PER_QUERY} runs)"
        print(f"  {qid:9s} {modal:9s} {n}/{len(codes)}{flag}")

    print(f"\n{unstable}/{len(by_q)} queries flipped between runs.")
    print("That fraction IS the noise floor (A2): a post-treatment change smaller than\n"
          "it is not evidence of a treatment effect.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("plan", help="print the ordered capture work-list with SERP URLs")
    a.add_argument("--wave", type=int, required=True, choices=sorted(BASELINE))
    a.set_defaults(func=cmd_plan)

    b = sub.add_parser("record", help="save one capture's evidence + CSV skeleton row")
    b.add_argument("--wave", type=int, required=True, choices=sorted(BASELINE))
    b.add_argument("--id", required=True)
    b.add_argument("--run", type=int, required=True)
    b.add_argument("--date")
    b.set_defaults(func=cmd_record)

    c = sub.add_parser("summarize", help="modal coding across runs + noise floor")
    c.add_argument("--wave", type=int, required=True, choices=sorted(BASELINE))
    c.set_defaults(func=cmd_summarize)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
