/** Wireframe 16 — Knowledge graph. Default: explainability view (Phase 6,
 * live). Developer-mode toggle (Phase 7, live) fetches
 * `GET /api/synthesis/explain?full=true` and renders the actual traversed
 * node/edge path with D3-force — this is the proof-it's-real beat for the
 * pitch (specs.md §2 "16 — Knowledge graph"). One route for both depths per
 * progress.md decisions log 2026-09-21. Composed from the component
 * vocabulary — the wireframe file does not carry this screen's markup
 * verbatim. */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, IconBtn, Kv, Note, Seg, Tag, Top } from "../components/Primitives";
import GraphViz from "../components/GraphViz";
import type { ExplainResponse } from "../api/types";
import { api } from "../api/client";
import { getSessionId } from "../capture/sessionStore";

const EMPTY_RESULT: ExplainResponse = {
  consideration: "",
  score: 0,
  edges: [],
  nodes: [],
  graph_edges: [],
};

function roleTag(role: string) {
  if (role === "strongest") return <Tag variant="bad">strongest</Tag>;
  if (role === "supporting") return <Tag variant="warn">supporting</Tag>;
  return <Tag variant="mute">context</Tag>;
}

export default function Screen16Graph() {
  const navigate = useNavigate();
  const [devMode, setDevMode] = useState(false);
  const [data, setData] = useState<ExplainResponse>(EMPTY_RESULT);
  const [devData, setDevData] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [devLoading, setDevLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .explain(getSessionId(), false)
      .then((r) => {
        if (!cancelled && r.edges.length > 0) setData(r);
      })
      .catch(() => {
        /* backend unreachable — no explainability data to show yet */
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!devMode || devData) return;
    let cancelled = false;
    setDevLoading(true);
    api
      .explain(getSessionId(), true)
      .then((r) => {
        if (!cancelled) setDevData(r);
      })
      .catch(() => {
        /* no live Neo4j / backend reachable this session — the graph simply
         * shows nothing rather than a fabricated traversal (rule 11). */
      })
      .finally(() => !cancelled && setDevLoading(false));
    return () => {
      cancelled = true;
    };
  }, [devMode, devData]);

  const hasData = data.consideration.length > 0;
  const diseaseLabel = data.consideration.replace(/_/g, " ");

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        <Tag variant="accent">Explainability</Tag>
      </Top>
      <h2 className="text-[26px] font-bold mb-1.5 capitalize">{hasData ? diseaseLabel : "No consideration yet"}</h2>
      <p className="text-sm text-text-2 mb-5">
        {hasData ? `Score ${data.score.toFixed(2)} — evidence contributing to this consideration.` : "Runs after an assessment has been generated for this session."}
      </p>
      <div className="flex gap-2.5 mb-4">
        <Seg label="Explain view" active={!devMode} onClick={() => setDevMode(false)} />
        <Seg label="Developer mode" active={devMode} onClick={() => setDevMode(true)} />
      </div>

      {!devMode && (
        <Card className="h-[220px] flex items-center justify-center bg-surface-2 text-text-3 text-sm">
          Force-graph of top consideration + evidence
        </Card>
      )}

      {devMode && (
        <Card className="bg-surface-2 p-2">
          {devLoading && !devData ? (
            <div className="h-[220px] flex items-center justify-center text-text-3 text-sm">Running the real Neo4j traversal…</div>
          ) : (
            <GraphViz nodes={devData?.nodes ?? []} edges={devData?.graph_edges ?? []} />
          )}
        </Card>
      )}

      {loading && !devMode && <Note>Loading explainability data…</Note>}

      {data.edges.map((e) => (
        <Card key={e.evidence}>
          <Kv
            left={
              <div>
                <h3 className="font-semibold">{e.evidence}</h3>
                <p className="text-text-2 text-[13px]">{e.source}</p>
                {e.screening_rule && <p className="text-text-3 text-[11px] mt-1">{e.screening_rule}</p>}
              </div>
            }
            right={roleTag(e.role)}
          />
        </Card>
      ))}
      <Note>Remove any symptom on the review screen and the graph recalculates.</Note>
    </>
  );
}
