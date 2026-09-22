"""Technique Catalog — loads and queries the knowledge base.

The single KB load point for the engine.  Delegates to
``storage_advisor.kb.provider`` which returns the v2 family-level
rollup filtered to engine-visible families.
"""

from __future__ import annotations

from storage_advisor.domain.techniques import Technique
from storage_advisor.exceptions import ConfigurationError
from storage_advisor.kb.provider import get_techniques as _provider_get_techniques


def load_techniques() -> list[Technique]:
    """Load and validate all techniques via the KB provider.

    Raises ConfigurationError if the provider returns nothing or
    any technique fails Pydantic validation.
    """
    entries = _provider_get_techniques()
    if not entries:
        raise ConfigurationError("Knowledge base returned no techniques")

    techniques: list[Technique] = []
    for i, entry in enumerate(entries):
        try:
            techniques.append(Technique(**entry))
        except Exception as e:
            raise ConfigurationError(
                f"Invalid technique at index {i} (id={entry.get('id', '?')}): {e}"
            ) from e

    ids = [t.id for t in techniques]
    duplicates = [tid for tid in ids if ids.count(tid) > 1]
    if duplicates:
        raise ConfigurationError(f"Duplicate technique IDs: {set(duplicates)}")

    return techniques


def get_technique_by_id(
    techniques: list[Technique], technique_id: str
) -> Technique | None:
    """Look up a single technique by ID."""
    for t in techniques:
        if t.id == technique_id:
            return t
    return None


def get_techniques_by_category(
    techniques: list[Technique], category: str
) -> list[Technique]:
    """Filter techniques by category."""
    return [t for t in techniques if t.category == category]
