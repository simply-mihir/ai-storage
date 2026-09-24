#!/usr/bin/env python3
"""CI guard: verify homepage baked stats match the live KB/engine values.

Exit 0 if every stat matches, exit 1 with a diff if any have drifted.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


def extract_baked(html: str) -> dict[str, str]:
    """Pull every data-stat element's text content from the HTML."""
    pattern = re.compile(r'data-stat="([^"]+)"[^>]*>([^<]*)<')
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(html)}


def compute_expected() -> dict[str, str]:
    from storage_advisor.architecture.builder import _SLOT_DEFAULTS
    from storage_advisor.domain.problems import ProblemId
    from storage_advisor.kb.loader import discover_families, flatten

    families = discover_families()
    effective = flatten(families)
    categories: dict[str, int] = {}
    for fam in families:
        cat = fam.category.value if hasattr(fam.category, "value") else str(fam.category)
        categories[cat] = categories.get(cat, 0) + 1

    expected: dict[str, str] = {
        "techniques": str(len(effective)),
        "hero-techniques": str(len(effective)),
        "detectors": str(len(ProblemId)),
        "services": str(len(_SLOT_DEFAULTS)),
        "catalog-tag": f"CATALOG OF {len(effective)} TECHNIQUES",
    }
    for cat, count in categories.items():
        expected[f"cat-{cat}"] = str(count)
    return expected


def main() -> int:
    html = INDEX.read_text(encoding="utf-8")
    baked = extract_baked(html)
    expected = compute_expected()

    drifted: list[str] = []
    for key, want in expected.items():
        got = baked.get(key)
        if got is None:
            drifted.append(f"  MISSING  data-stat={key!r}  expected={want!r}")
        elif got != want:
            drifted.append(f"  DRIFT    data-stat={key!r}  baked={got!r}  expected={want!r}")

    if drifted:
        print("Homepage stat drift detected:", file=sys.stderr)
        for line in drifted:
            print(line, file=sys.stderr)
        return 1

    print(f"All {len(expected)} homepage stats match.", file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
