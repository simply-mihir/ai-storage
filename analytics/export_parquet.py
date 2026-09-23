"""CLI entry point for analytics.export_parquet."""
from __future__ import annotations

import logging

from storage_advisor.analytics.export_parquet import export, row_count

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    result_dir = export()
    total = row_count(str(result_dir))
    print(f"Exported {total} rows to {result_dir}")
