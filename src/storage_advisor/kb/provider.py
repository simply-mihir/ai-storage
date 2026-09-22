"""KB provider — single entry point for the engine's technique list.

Unions legacy YAML entries with v2 ``flat_view()`` output.  On exact
ID collision the v2 version wins.  The result iterates over legacy
entries and substitutes v2 content where an effective technique ID
matches, keeping the engine-visible technique set identical to the
legacy registry.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from storage_advisor.kb.compat import flat_view


def _find_legacy_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / "configs" / "techniques.yaml",
        Path.cwd() / "configs" / "techniques.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


_DEFAULT_LEGACY_PATH = _find_legacy_path()


def _load_legacy_entries(path: Path | None = None) -> list[dict]:
    """Load raw technique dicts from the legacy YAML KB."""
    kb_path = path or _DEFAULT_LEGACY_PATH
    if not kb_path.exists():
        return []
    raw = yaml.safe_load(kb_path.read_text())
    if not isinstance(raw, dict) or "techniques" not in raw:
        return []
    entries = raw["techniques"]
    return entries if isinstance(entries, list) else []


def get_techniques(legacy_path: Path | None = None) -> list[dict]:
    """Return the engine-visible technique list in legacy dict shape.

    Algorithm:
      1. Load legacy YAML entries (the engine's "technique registry").
      2. Load v2 ``flat_view()`` entries.
      3. For each legacy entry, substitute the v2 version if an exact
         ID match exists (v2 wins on collision).
      4. v2-only entries (no matching legacy ID) are excluded — they
         become engine-visible when explicitly registered.

    This keeps the technique count and ID set identical to the legacy
    YAML, while allowing v2 families to provide enriched content.
    """
    legacy = _load_legacy_entries(legacy_path)
    v2_entries = flat_view()
    v2_by_id: dict[str, dict] = {e["id"]: e for e in v2_entries}

    result: list[dict] = []
    for entry in legacy:
        eid = entry["id"]
        if eid in v2_by_id:
            result.append(v2_by_id[eid])
        else:
            result.append(entry)
    return result
