"""Symptom normalisation — extracted terms to `:KB:Symptom` canonical slugs.

The graph is English-only and its canonical term **is** the slug (CLAUDE.md,
"Knowledge-base data conventions"). Resolution goes through
`data/seed/curated/symptom_aliases.csv`, reusing `graph.seed.load_curated_aliases`
so there is exactly one loader for that file.

Runtime **never** creates `:KB:Symptom` nodes. An unresolvable term keeps
`canonical = None` and is carried as `unmapped_text` for the officer to map by
hand on screen 9.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.graph.seed import load_curated_aliases


def _key(term: str) -> str:
    """Loose match key: lowercase, punctuation dropped, whitespace collapsed."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s_]", " ", (term or "").lower())).strip()


@lru_cache(maxsize=1)
def alias_map() -> dict[str, str]:
    """`{normalised alias -> slug}`, including each slug as its own alias and a
    spaced form of the slug ("night sweats" -> `night_sweats`)."""
    out: dict[str, str] = {}
    for alias, slug in load_curated_aliases():
        out.setdefault(_key(alias), slug)
        out.setdefault(_key(slug), slug)
        out.setdefault(_key(slug.replace("_", " ")), slug)
    return out


def resolve_symptom(term: str | None) -> str | None:
    """Return the canonical slug for `term`, or None if it does not resolve.

    Tried in order: exact alias, slugified form, then the longest alias that is
    contained in the term (so "exertional chest tightness felt today" still
    resolves). Never invents a slug.
    """
    if not term:
        return None
    mapping = alias_map()
    k = _key(term)
    if k in mapping:
        return mapping[k]
    underscored = k.replace(" ", "_")
    if underscored in mapping:
        return mapping[underscored]
    best: tuple[int, str] | None = None
    for alias, slug in mapping.items():
        if len(alias) >= 4 and alias in k and (best is None or len(alias) > best[0]):
            best = (len(alias), slug)
    return best[1] if best else None
