"""
Search engine and filters for the Realtimex Memory System.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from memory.registry import MemoryRecord, MemoryScope, MemoryStatus


@dataclass
class MemorySearchQuery:
    """
    Search parameters for filtering memory records.
    """
    query_text: str | None = None
    tags: list[str] = field(default_factory=list)
    owner: str | None = None
    scope: MemoryScope | None = None
    status: MemoryStatus | None = None
    source: str | None = None
    created_since: datetime | None = None
    created_until: datetime | None = None


class MemorySearcher:
    """
    Filters memory candidates against search criteria.
    """

    def search(self, query: MemorySearchQuery, candidates: list[MemoryRecord]) -> list[MemoryRecord]:
        """
        Filter and rank candidates according to the search query.
        """
        results: list[MemoryRecord] = []

        for rec in candidates:
            # 1. Filter by Scope
            if query.scope is not None and rec.scope != query.scope:
                continue

            # 2. Filter by Status
            if query.status is not None and rec.status != query.status:
                continue

            # 3. Filter by Owner
            if query.owner is not None and rec.owner.lower() != query.owner.lower():
                continue

            # 4. Filter by Source
            if query.source is not None and rec.source.lower() != query.source.lower():
                continue

            # 5. Filter by tags (Must match all query tags if tags are specified)
            if query.tags:
                rec_tags_lower = {t.lower() for t in rec.tags}
                query_tags_lower = {t.lower() for t in query.tags}
                if not query_tags_lower.issubset(rec_tags_lower):
                    continue

            # 6. Filter by Created Since
            if query.created_since is not None and rec.created_at < query.created_since:
                continue

            # 7. Filter by Created Until
            if query.created_until is not None and rec.created_at > query.created_until:
                continue

            # 8. Filter by text matches (content or metadata)
            if query.query_text:
                q_text = query.query_text.lower()
                content_str = str(rec.content).lower()
                metadata_str = str(rec.metadata).lower()
                if q_text not in content_str and q_text not in metadata_str:
                    continue

            results.append(rec)

        return results
