# Deploy

How to get Sanjeevani off localhost for the pitch: Neo4j on AuraDB, the
backend on Render, the frontend on Vercel. `docker compose up` remains the
demo-day safety net (see `docs/demo.md`) — this is the "credibility from the
URL" leg of the Phase-0 decision log, not a replacement for it.

Env var names are fixed by the code already (`backend/app/graph/client.py`,
`docker-compose.yml`) — do not rename them when deploying:
`NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`, `GEMINI_API_KEY` (+ optional
`GEMINI_MODEL` / `GEMINI_STT_MODEL`), `SANJEEVANI_FIXTURE_MODE`,
`VITE_API_BASE_URL`. See `.env.example` at the repo root for the full list.

---

## 1. Neo4j AuraDB (free tier)

1. Go to https://console.neo4j.io, sign in, **New instance** -> **AuraDB
   Free**.
2. Name it (e.g. `sanjeevani`), region doesn't matter for a hackathon demo.
   On creation, Aura shows the credentials **once** — copy them immediately:
   - Connection URI: `neo4j+s://<id>.databases.neo4j.io` (note `neo4j+s://`,
     not `bolt://` — this is TLS, which `AsyncGraphDatabase.driver()` in
     `backend/app/graph/client.py` handles transparently; the driver takes any
     `neo4j://` / `neo4j+s://` / `bolt://` scheme without code changes).
   - Username: `neo4j`
   - Password: the generated one (or set your own).
3. Set locally for a one-off seed run:
   ```
   export NEO4J_URI="neo4j+s://<id>.databases.neo4j.io"
   export NEO4J_USER="neo4j"
   export NEO4J_PASSWORD="<the password>"
   ```
   (PowerShell: `$env:NEO4J_URI = "neo4j+s://..."` etc.)
4. Seed it — same command as local, `graph/client.py` reads whatever
   `NEO4J_URI` is set to:
   ```
   cd backend
   pip install -e ".[dev]"
   python -m app.graph.seed
   ```
5. Verify in the Aura browser console (or `cypher-shell`):
   ```
   MATCH (d:KB:Disease) RETURN count(d);
   MATCH (d:KB:Disease {slug:'tuberculosis'})-[r:PRESENTS_WITH]->(:KB:Symptom {slug:'cough'})
   RETURN r.screening_rule;
   ```
   Expect 41 Kaggle + 10 curated diseases and the NTEP screening-rule string.
6. AuraDB Free auto-pauses after inactivity. If the demo has been idle for a
   while, open the Aura console and resume the instance a few minutes before
   going on stage — same spirit as the Render cold-start warm-up below.

The seed script and driver were already AuraDB-compatible — `GraphClient`
takes whatever URI it's given and the official driver handles `neo4j+s://`
natively; nothing in `seed.py` assumes `bolt://` or localhost.

---

## 2. Backend on Render

### Option A — Blueprint (`render.yaml`, recommended)

1. Push this repo to GitHub (Render deploys from a repo, not a local
   directory).
2. Render dashboard -> **New** -> **Blueprint** -> pick the repo. Render
   reads `render.yaml` at the repo root and creates a `sanjeevani-backend`
   Docker web service from `backend/Dockerfile`.
3. Render will prompt for the env vars marked `sync: false` in `render.yaml`
   — fill in `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` (from step 1 above)
   and `GEMINI_API_KEY`. **Enter these as Render secrets in the dashboard —
   never commit them.**
4. Deploy. Render builds `backend/Dockerfile` and exposes it on
   `https://sanjeevani-backend.onrender.com` (or whatever name you gave it).
5. Confirm boot: `curl https://<your-render-url>/health` -> `{"status":"ok"}`.
   The app boots with **no** Neo4j/Gemini reachable too (graceful fallback
   everywhere) — a 200 here doesn't by itself confirm the graph is wired, only
   that the process is up.

### Option B — manual dashboard steps (no `render.yaml`)

1. **New** -> **Web Service** -> connect the repo.
2. Runtime: **Docker**. Root directory: `backend`. Dockerfile path:
   `backend/Dockerfile` (or just `Dockerfile` if root directory is already
   `backend`).
3. Health check path: `/health`.
4. Add the same environment variables as above under **Environment**, as
   secrets.
5. Plan: Free is enough for a demo (cold starts — see §4 below).
6. Create Web Service; Render builds and deploys.

`backend/Dockerfile` already has everything a Render Docker deploy needs — it
installs from `pyproject.toml`, copies `app/` and `tests/`, exposes 8000, and
runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`, which is exactly what
Render's Docker runtime expects (`$PORT` — Render sets `PORT=10000` internally
and proxies from its edge; if you deploy to a plan where Render enforces its
own `$PORT`, change the `CMD` to `uvicorn app.main:app --host 0.0.0.0 --port
$PORT` — the free-tier Docker runtime as configured here binds container port
8000 directly, which Render's Docker services support without a `$PORT`
requirement, but check the current Render docs if the build fails on port
binding).

---

## 3. Frontend on Vercel

1. Vercel dashboard -> **Add New** -> **Project** -> import the repo, set
   **Root Directory** to `frontend`.
2. Framework preset: **Vite**. Build command `npm run build` (or `vite
   build`), output directory `dist` — Vercel autodetects both from
   `frontend/package.json` / `frontend/vite.config.ts`.
3. Environment variable: `VITE_API_BASE_URL` = `https://<your-render-url>`
   (no trailing slash). `frontend/src/api/client.ts` already reads this via
   `import.meta.env.VITE_API_BASE_URL` (falls back to
   `http://localhost:8000` only when unset) — **no code change was needed
   here**, it was already wired to an env var, not hardcoded.
4. Routing: the app uses `HashRouter` (`#/1`, `#/6`, …), so every route
   resolves client-side against the single `index.html` Vercel serves by
   default. **No `vercel.json` rewrite rule is needed** — a hash fragment
   never reaches the server as a path, so there's nothing for Vercel's static
   host to 404 on. (A `vercel.json` would only be needed for a
   `BrowserRouter`-style app with real paths like `/scan`.)
5. Deploy. Vercel gives you HTTPS by default on the `*.vercel.app` domain —
   this is required for `getUserMedia` (camera) to work at all; a plain
   `http://` origin (other than `localhost`) will have the browser silently
   refuse camera access.
6. Confirm: open the Vercel URL, go through screen 1 -> 2, check the browser
   devtools Network tab shows requests going to the Render URL, not
   `localhost:8000`.

---

## 4. Render cold-start warm-up (pre-demo step)

Render's free tier spins the container down after ~15 minutes idle; the next
request pays a cold-start (image pull + FastAPI boot + Neo4j driver
connectivity check), which can take 30-60+ seconds — long enough to kill a
live demo if the first request is the officer's own click.

**Do this 5-10 minutes before going on stage, every time:**
```
curl https://<your-render-url>/health
```
Wait for a `{"status":"ok"}` response, then do a second full round-trip
against a real endpoint (`curl https://<your-render-url>/api/session/pending`)
so the Neo4j driver's connection pool is also warm, not just the process.
Repeat once more right before the pitch starts if there's a gap. This is a
manual step, not automated — there's no monitoring/uptime service in this
build's stack, and a documented manual warm-up is sufficient for a single
pitch slot (see `docs/demo.md`'s pre-demo checklist).

---

## 5. Local fallback (`docker compose up`) — verification

`docker compose config` **is** available in this sandbox (a change from
Phases 1-6's notes, which all recorded no Docker daemon) — ran it and it
validates cleanly. It also flagged the top-level `version: "3.9"` key as
obsolete in current Compose syntax; removed it from `docker-compose.yml`
(cosmetic only, no behaviour change — Compose was ignoring it already).

- `docker compose config` resolves both services correctly: `backend` gets
  `NEO4J_URI=bolt://neo4j:7687` / `NEO4J_USER=neo4j` /
  `NEO4J_PASSWORD=sanjeevani123` (matching the `neo4j` service's
  `NEO4J_AUTH=neo4j/sanjeevani123`) and picks up `GEMINI_API_KEY` from the
  shell/`.env`; `frontend` gets `VITE_API_BASE_URL=http://localhost:8000`.
  No interpolation errors, no missing service references.
- A full `docker compose up` (actually pulling images, building, and booting
  Neo4j/FastAPI/Vite) was **not** run in this sandbox — that needs a Docker
  daemon actually running containers, which this environment doesn't provide
  even though the CLI/config validation works. Run it once on the real demo
  laptop before the pitch.
- `docker-compose.yml` service definitions are internally consistent: the
  `backend` service's `NEO4J_URI=bolt://neo4j:7687` correctly targets the
  `neo4j` service by its compose network name and port 7687 (matching the
  `neo4j` service's exposed `7687:7687`); `NEO4J_USER`/`NEO4J_PASSWORD` match
  the `neo4j` service's `NEO4J_AUTH=neo4j/sanjeevani123`.
- `backend/Dockerfile` paths (`pyproject.toml`, `app/`, `tests/`) all exist
  under `backend/` and match `COPY` sources.
- Backend dependencies: every third-party import in `backend/app/**/*.py`
  (`fastapi`, `neo4j`, `pydantic`, `numpy`, `scipy`, `reportlab`, `yaml`,
  `google.generativeai`) is declared in `backend/pyproject.toml`'s
  `dependencies` and mirrored in the Dockerfile's fallback `uv pip install`
  line — no drift found; nothing added in Phases 2-7 is missing from either.
  (`opencv-python-headless` is declared but not currently imported anywhere —
  pre-existing, not new drift, left alone.)
- `frontend`'s compose service runs `npm install && npm run dev` against the
  live-mounted `./frontend` volume with `VITE_API_BASE_URL=http://localhost:8000`
  already set — consistent with the Vercel env var above.
- **Not verified**: an actual `docker compose config` / `docker compose up`
  run (still blocked — no Docker daemon in this sandbox). Run
  `docker compose config` once before the demo to catch any YAML syntax
  issue, and a full `docker compose up` at least once on the actual demo
  laptop ahead of time.
