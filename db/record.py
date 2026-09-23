"""Record module forwarding."""
from __future__ import annotations

from storage_advisor.db.record import (
    Base,
    SubmittedScenario,
    get_scenario,
    reset,
    save_scenario,
)

__all__ = [
    "Base",
    "SubmittedScenario",
    "get_scenario",
    "reset",
    "save_scenario",
]
