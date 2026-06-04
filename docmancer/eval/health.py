"""Basic source/index health reports for eval observability."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def source_health_report(agent) -> dict[str, Any]:
    stats = agent.collection_stats()
    db_path = Path(stats.get("db_path") or "")
    report: dict[str, Any] = {
        "sources_count": int(stats.get("sources_count") or 0),
        "sections_count": int(stats.get("sections_count") or 0),
        "sources_by_format": stats.get("sources_by_format") or {},
        "sections_by_format": stats.get("sections_by_format") or {},
        "empty_sections": 0,
        "sparse_sections": 0,
        "duplicate_content_hashes": 0,
        "vector_sqlite_drift": None,
        "warnings": [],
    }
    if not db_path.exists():
        report["warnings"].append("sqlite_db_missing")
        return report
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            report["empty_sections"] = int(conn.execute("SELECT COUNT(*) FROM sections WHERE trim(text) = ''").fetchone()[0])
            report["sparse_sections"] = int(conn.execute("SELECT COUNT(*) FROM sections WHERE token_estimate < 20").fetchone()[0])
            report["duplicate_content_hashes"] = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM (
                      SELECT content_hash FROM sections
                      WHERE content_hash IS NOT NULL AND content_hash <> ''
                      GROUP BY content_hash HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            embedding_rows = int(conn.execute("SELECT COUNT(DISTINCT chunk_id) FROM embedding_upserts").fetchone()[0])
            if embedding_rows:
                report["vector_sqlite_drift"] = abs(int(report["sections_count"]) - embedding_rows)
    except Exception as exc:  # pragma: no cover - defensive health reporter
        report["warnings"].append(f"sqlite_health_error:{type(exc).__name__}:{exc}")
    return report
