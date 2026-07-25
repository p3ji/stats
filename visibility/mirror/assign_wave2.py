"""Wave-2 treatment/control assignment — reproducible, pre-registered.

Follows docs/wave2.md selection rule: gap pool (deduped to table) is randomized
table -> arm with a fresh seeded random.Random, stratified by subject. Only
treatment tables get mirrored; control tables are recorded and held out.

Run: python visibility/mirror/assign_wave2.py
Prints the assignment and (with --write) patches the manifest experiment block.
"""
from __future__ import annotations

import random

SEED = 20260725  # fresh seed, recorded at assignment time (wave-1 used 20260718)

# Curated gap pool from the Bing baseline (baseline_bing_wave2_2026-07-22.csv):
# tables where StatCan publishes the *matching* metric but the engine served it
# via an intermediary / stale vintage / not at all. Cross-org (PHAC/IRCC own the
# metric) and no-table cases are excluded per the wave-2 cross-org caveat.
# (subject, pid, short_title, [matched queries])
POOL = [
    # Health — clean scenario-(b): StatCan's own metric absent from the answer
    ("health", "13100962", "Access to a regular health care provider (SHCAE)", ["HEA-016", "HEA-017"]),
    ("health", "13100465", "Perceived (self-rated) mental health",             ["HEA-024", "HEA-001"]),
    ("health", "13100930", "Mental disorders & substance use (MHACS)",         ["HEA-002"]),
    ("health", "13100836", "Unmet health care needs",                          ["HEA-019"]),
    ("health", "13100971", "Health-adjusted life expectancy by income",        ["HEA-025"]),
    # Immigration — displacement: census figure served, StatCan uncredited
    ("immigration", "98100307", "Immigrant / foreign-born population (census)", ["IMM-001", "IMM-013", "IMM-014"]),
    ("immigration", "98100324", "Visible minority population (census)",         ["IMM-007", "IMM-008", "IMM-010"]),
    # Population — displacement: demographic estimate served, StatCan uncredited
    ("population", "17100009", "Quarterly population estimates",                ["POP-001", "POP-002"]),
]

# Treatment fraction per subject stratum: ceil(n/2) treated, but keep >=1 control
# whenever the stratum has >=2 tables (so every multi-table subject has a holdout).
def split(n: int) -> int:
    if n == 1:
        return 1          # can't hold out a singleton subject; treat it (noted)
    return (n + 1) // 2   # ceil half to treatment, leaving >=1 control


def main() -> None:
    rng = random.Random(SEED)
    subjects: dict[str, list] = {}
    for row in POOL:
        subjects.setdefault(row[0], []).append(row)

    treatment, control = [], []
    for subject in sorted(subjects):
        tables = sorted(subjects[subject], key=lambda r: r[1])  # deterministic order
        rng.shuffle(tables)
        k = split(len(tables))
        treatment += tables[:k]
        control += tables[k:]

    treatment.sort(key=lambda r: r[1])
    control.sort(key=lambda r: r[1])

    print(f"Wave-2 assignment  (seed={SEED}, stratified by subject)\n")
    print("TREATMENT (get mirrors):")
    for s, pid, title, q in treatment:
        print(f"  {pid}  [{s:11}] {title}   {q}")
    print("\nCONTROL (held out, never mirrored):")
    for s, pid, title, q in control:
        print(f"  {pid}  [{s:11}] {title}   {q}")

    print("\n--- manifest snippet ---")
    print("  treatment: [" + ", ".join(f'"{r[1]}"' for r in treatment) + "]")
    print("  control:   [" + ", ".join(f'"{r[1]}"' for r in control) + "]")


if __name__ == "__main__":
    main()
