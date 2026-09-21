/** Developer-mode force-graph (screen 16, Phase 7). Renders the node/edge
 * list from `GET /api/synthesis/explain?full=true` — this is the ONLY place
 * that endpoint's `nodes`/`graph_edges` are consumed. The browser never opens
 * a Bolt connection to Neo4j (CLAUDE.md rule 5, generalised): every node/edge
 * here was already computed server-side by `agents/reasoning.py` and served
 * as plain JSON.
 *
 * D3-force (not neovis.js) was chosen — see progress.md Decisions log,
 * 2026-09-21 — precisely because neovis.js drives its layout off a live
 * Bolt/websocket connection from the browser to Neo4j, which the CLAUDE.md
 * "never stream video to the backend" boundary generalises against for any
 * direct client -> database channel. D3 lays out the same JSON the REST API
 * already returns.
 *
 * The traversed path (every element in `nodes`/`graph_edges` — the rank-1
 * consideration's reasoning chain) renders in full colour with a glow; the
 * spec's "context" role (village priors, never `strongest`) renders dimmer
 * per specs.md §7. There is no separate "rest of the graph" fetch — showing
 * unrelated :KB nodes here would mean querying the whole knowledge base into
 * the client, which CLAUDE.md's graph conventions forbid regardless of UI. */
import { useEffect, useRef } from "react";
import { forceCenter, forceLink, forceManyBody, forceSimulation, type SimulationNodeDatum } from "d3-force";
import { drag } from "d3-drag";
import { select } from "d3-selection";
import type { GraphEdgeOut, GraphNode } from "../api/types";

type SimNode = GraphNode & SimulationNodeDatum;

const NODE_COLOR: Record<GraphNode["type"], string> = {
  person: "#84D3B8", // --accent
  disease: "#E08A7E", // --bad (the consideration being explained)
  symptom: "#E3B461", // --warn (evidence)
  context: "#728880", // --text-3 (village context — dimmer, never "strongest")
};

const ROLE_STROKE: Record<GraphEdgeOut["role"], string> = {
  strongest: "#84D3B8",
  supporting: "#E3B461",
  context: "#3A4A44",
};

export default function GraphViz({
  nodes,
  edges,
  width = 620,
  height = 320,
}: {
  nodes: GraphNode[];
  edges: GraphEdgeOut[];
  width?: number;
  height?: number;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
    const svg = select(svgRef.current);
    svg.selectAll("*").remove();

    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }));
    const nodeById = new Map(simNodes.map((n) => [n.id, n]));
    const simLinks = edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ ...e }));

    const linkGroup = svg.append("g").attr("stroke-linecap", "round");
    const nodeGroup = svg.append("g");

    const linkSel = linkGroup
      .selectAll("line")
      .data(simLinks)
      .join("line")
      .attr("stroke", (d) => (d.highlighted ? ROLE_STROKE[d.role] : "#25382F"))
      .attr("stroke-width", (d) => (d.role === "strongest" ? 3 : d.role === "supporting" ? 2 : 1))
      .attr("stroke-opacity", (d) => (d.highlighted ? 0.9 : 0.3))
      .attr("stroke-dasharray", (d) => (d.role === "context" ? "3,3" : null));

    const nodeSel = nodeGroup
      .selectAll<SVGGElement, SimNode>("g")
      .data(simNodes)
      .join("g")
      .style("cursor", "grab")
      .call(
        drag<SVGGElement, SimNode>()
          .on("start", (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    nodeSel
      .append("circle")
      .attr("r", (d) => (d.type === "disease" || d.type === "person" ? 16 : 11))
      .attr("fill", (d) => NODE_COLOR[d.type])
      .attr("fill-opacity", (d) => (d.highlighted ? 1 : 0.35))
      .attr("stroke", "#0E1512")
      .attr("stroke-width", 2);

    nodeSel
      .append("text")
      .text((d) => (d.label.length > 22 ? d.label.slice(0, 20) + "…" : d.label))
      .attr("x", 0)
      .attr("y", (d) => (d.type === "disease" || d.type === "person" ? 30 : 24))
      .attr("text-anchor", "middle")
      .attr("font-size", 11)
      .attr("fill", "#A7BCB5");

    const sim = forceSimulation(simNodes)
      .force(
        "link",
        forceLink(simLinks as any)
          .id((d: any) => d.id)
          .distance(90)
          .strength(0.6)
      )
      .force("charge", forceManyBody().strength(-220))
      .force("center", forceCenter(width / 2, height / 2))
      .on("tick", () => {
        linkSel
          .attr("x1", (d: any) => d.source.x)
          .attr("y1", (d: any) => d.source.y)
          .attr("x2", (d: any) => d.target.x)
          .attr("y2", (d: any) => d.target.y);
        nodeSel.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
      });

    return () => {
      sim.stop();
    };
  }, [nodes, edges, width, height]);

  if (nodes.length === 0) {
    return (
      <div className="h-[220px] flex items-center justify-center text-text-3 text-sm">
        No traversal data for this session yet.
      </div>
    );
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      role="img"
      aria-label="Knowledge graph traversal for this session"
    />
  );
}
