"""Remine stages 1-5 — from a Daily date to fact briefs.

Runs to completion with no agent present. That is what makes it testable.

Run: python remine/generate.py --date 260807
"""

import argparse
import sys
from pathlib import Path

# Allow `python remine/generate.py` to work when invoked as a script (not
# via `python -m remine.generate`) by putting the repo root — the parent of
# this package directory — on sys.path so `import remine.*` resolves.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from remine.brief import build_brief, write_brief
from remine.cube import download_cube, fetch_meta, load_cube
from remine.discover import discover
from remine.mentions import find_mentions, load_config
from remine.probes import prepare, run_probes
from remine.rank import gate, rank

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
BRIEFS = ROOT / "briefs"


def generate(date: str, only_pid: int | None = None) -> list[Path]:
    release = discover(date)
    written: list[Path] = []
    for article in release.articles:
        for pid in article.pids:
            if only_pid and pid != only_pid:
                continue
            print(f"[{article.slug}] cube {pid}")
            meta = fetch_meta(pid)
            cfg = load_config(pid)
            df = load_cube(download_cube(pid, meta.release_time, CACHE), pid)
            prepared = prepare(df, cfg)
            dims = [d.name for d in meta.dimensions
                    if d.name not in (cfg.get("filters") or {})
                    and d.name != cfg.get("value_dimension")]
            if not dims:
                raise RuntimeError(
                    f"cube {pid} has no probeable dimensions left after applying "
                    f"filters {cfg.get('filters')} and value dimension "
                    f"{cfg.get('value_dimension')!r} — check surveys.yaml")
            facts = run_probes(prepared, dims, cfg)
            print(f"  {len(facts)} candidate facts")
            facts = gate(facts, prepared, cfg)
            print(f"  {len(facts)} survived the reliability gate")
            if not facts:
                # An empty brief is worse than no brief: it looks like a
                # finished run. The skill layer says never lower the gate to
                # produce output, and that rule has to live here in Python.
                print(f"  SKIPPED {pid}: nothing survived the gate — "
                      f"no brief written")
                continue
            mentions = find_mentions(article.prose, meta, cfg.get("synonyms") or {})
            ranked = rank(facts, mentions, cfg)
            brief = build_brief(article, meta, ranked, mentions, cfg)
            path = write_brief(brief, BRIEFS)
            print(f"  wrote {path}")
            written.append(path)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Remine — build fact briefs for a Daily release")
    ap.add_argument("--date", required=True, help="Daily date as YYMMDD, e.g. 260807")
    ap.add_argument("--pid", type=int, default=None, help="restrict to one 8-digit cube PID")
    args = ap.parse_args()
    paths = generate(args.date, args.pid)
    if not paths:
        raise SystemExit("no briefs written")
    print(f"\n{len(paths)} brief(s) written to {BRIEFS}")


if __name__ == "__main__":
    main()
