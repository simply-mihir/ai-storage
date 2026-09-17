"""Technique Catalog — loads and queries the knowledge base from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from storage_advisor.domain.techniques import Technique
from storage_advisor.exceptions import ConfigurationError

_DEFAULT_KB_PATH = Path(__file__).resolve().parents[3] / "configs" / "techniques.yaml"


def load_techniques(path: Path | None = None) -> list[Technique]:
    """Load and validate all techniques from the YAML knowledge base.

    Raises ConfigurationError if the file is missing, malformed, or
    any technique fails Pydantic validation.
    """
    kb_path = path or _DEFAULT_KB_PATH
    if not kb_path.exists():
        raise ConfigurationError(f"Knowledge base not found: {kb_path}")

    try:
        raw = yaml.safe_load(kb_path.read_text())
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in knowledge base: {e}") from e

    if not isinstance(raw, dict) or "techniques" not in raw:
        raise ConfigurationError("Knowledge base must contain a 'techniques' key")

    techniques: list[Technique] = []
    for i, entry in enumerate(raw["techniques"]):
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
