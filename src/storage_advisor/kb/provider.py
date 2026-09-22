"""KB provider — single entry point for the engine's technique list.

Returns legacy-shaped dicts from the v2 family-level rollup, filtered
to families with ``engine_exposure="legacy"``.  The legacy YAML
registry is no longer used.
"""

from __future__ import annotations

from storage_advisor.kb.compat import flat_view


def get_techniques() -> list[dict]:
    """Return the engine-visible technique list in legacy dict shape.

    Uses v2 ``flat_view()`` (one record per family), filtered to
    families with ``engine_exposure="legacy"``.  The ``engine_exposure``
    field is stripped from the output so the engine sees the same shape
    as the old legacy YAML registry.
    """
    all_entries = flat_view()
    result: list[dict] = []
    for entry in all_entries:
        if entry.get("engine_exposure") != "legacy":
            continue
        cleaned = {k: v for k, v in entry.items() if k != "engine_exposure"}
        result.append(cleaned)
    return result
