"""Neo4j driver wrapper. No ORM (CLAUDE.md). Thin async facade over the official driver."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

SCHEMA_PATH = Path(__file__).parent / "schema.cypher"


class GraphClient:
    """Wraps an AsyncDriver. One instance per process, created in main.py lifespan."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    @classmethod
    def from_env(cls) -> "GraphClient":
        return cls(
            uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            user=os.environ.get("NEO4J_USER", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", "sanjeevani123"),
        )

    async def close(self) -> None:
        await self._driver.close()

    async def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            records = await result.data()
            return records

    async def apply_schema(self) -> None:
        """Applies schema.cypher. Idempotent: every statement uses IF NOT EXISTS."""
        text = SCHEMA_PATH.read_text(encoding="utf-8")
        statements = [
            line.strip()
            for line in text.split(";")
            if line.strip() and not line.strip().startswith("//")
        ]
        async with self._driver.session() as session:
            for stmt in statements:
                await session.run(stmt)

    async def verify_connectivity(self) -> bool:
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False
