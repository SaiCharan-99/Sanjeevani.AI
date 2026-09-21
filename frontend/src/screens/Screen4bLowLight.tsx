/** Wireframe 4b — Live scan, low light / motion. Phase 2 — live, but not a
 * separate route: screen 4 (Screen4LiveScan.tsx) now drives this exact visual
 * state itself from live client quality feedback (face_lost/low_light/
 * high_motion), per specs.md §2 ("Not a separate route — a state of screen
 * 4"). This route is kept only as the wireframe-referenced preview of that
 * state for anyone navigating here directly. */
import { useNavigate } from "react-router-dom";
import { Bar, Camera, ChipPill, Cta, IconBtn, Kv, Tag } from "../components/Primitives";

export default function Screen4bLowLight() {
  const navigate = useNavigate();
  return (
    <Camera>
      <div className="flex justify-between items-center">
        <IconBtn onClick={() => navigate("/3")}>✕</IconBtn>
        <Tag variant="warn">● Acquiring</Tag>
        <IconBtn>☀</IconBtn>
      </div>
      <div className="flex flex-col items-center">
        <div className="relative w-[220px] h-[240px] flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-4 border-warn/40" />
          <div className="flex flex-col items-center justify-center">
            <div className="text-[46px] font-bold tracking-tight">23</div>
            <div className="text-[13px] text-text-3">seconds remaining</div>
            <Tag variant="warn">Scan paused</Tag>
          </div>
        </div>
        <ChipPill tone="warn">☀ Move into better light</ChipPill>
      </div>
      <div>
        <div className="bg-surface/85 border border-line-soft rounded-r-lg p-3.5 mb-3.5">
          <Kv left={<span className="text-[13px] text-text-2">Signal quality</span>} right={<b className="text-[15px]">52%</b>} />
          <div className="mt-2.5"><Bar pct={52} color="bg-warn" /></div>
          <div className="flex justify-between mt-2.5 text-[11.5px] text-text-3">
            <span className="text-warn">Shadow on left cheek</span><span>Motion: Steady</span><span>rPPG: Intermittent</span>
          </div>
        </div>
        <Cta ghost onClick={() => navigate("/4")}>
          Go to live scan →
        </Cta>
      </div>
    </Camera>
  );
}
