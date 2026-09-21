"""FastAPI entrypoint. Applies the graph schema on startup (idempotent) and
wires every route module. Boots cleanly with no Neo4j/Gemini available — kb.py
falls back to mock data and providers raise only when actually invoked."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import consult, kb, person, report, secondlook, session, synthesis, vitals, village
from app.graph.client import GraphClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = GraphClient.from_env()
    app.state.graph_client = client
    if await client.verify_connectivity():
        try:
            await client.apply_schema()
        except Exception:
            app.state.graph_client = None  # kb.py falls back to mock data
    else:
        app.state.graph_client = None  # kb.py falls back to mock data
    yield
    if client is not None:
        await client.close()


app = FastAPI(title="Sanjeevani API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (vitals.router, session.router, consult.router, secondlook.router,
               synthesis.router, report.router, person.router, village.router, kb.router):
    app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
