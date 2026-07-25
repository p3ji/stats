"""Dump dimensions + members for the wave-2 treatment cubes, to author views.

Uses build_mirror.get_metadata (fetches WDS getCubeMetadata, caches under
visibility/cache/mirror_meta/). Run: python visibility/mirror/inspect_cubes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_mirror import get_metadata  # noqa: E402

PIDS = ["13100465", "13100962", "13100971", "17100009", "98100307"]

for pid in PIDS:
    meta = get_metadata(pid)
    print("=" * 90)
    print(f"{pid}  {meta['cubeTitleEn']}")
    print(f"  freq={meta.get('frequencyCode')}  start={meta.get('cubeStartDate')}  end={meta.get('cubeEndDate')}")
    for d in sorted(meta["dimension"], key=lambda d: d["dimensionPositionId"]):
        members = d["member"]
        print(f"\n  DIM [{d['dimensionPositionId']}] {d['dimensionNameEn']}  ({len(members)} members)")
        for m in members[:40]:
            print(f"      {m['memberId']:>5}  {m['memberNameEn']}")
        if len(members) > 40:
            print(f"      ... (+{len(members) - 40} more)")
    print()
