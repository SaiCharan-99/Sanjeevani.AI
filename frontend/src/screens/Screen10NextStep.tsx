/** Wireframe 10 — Next step (agent suggestion, "the wow beat"). Phase 5 —
 * live. Fetches the real ranked suggestions from the trigger engine
 * (`GET /api/secondlook/suggest`), which reads this session's reported
 * canonical symptoms. The priority card's rationale quotes the actual
 * triggering symptoms (specs.md §2). If `facial_asymmetry` is triggered it is
 * always first and labelled a red flag (architecture.md §8). */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { SecondLookSuggestion } from "../api/types";
import { Card, Cta, IconBtn, Kv, Note, Pill, PillRow, Sec, Tag, Top } from "../components/Primitives";
import { getSessionId, setChosenFeature, storeSecondLookSuggestions } from "../capture/sessionStore";

function durationChip(feature: string): string {
  if (feature === "facial_asymmetry") return "⏱ 15 sec";
  if (feature === "gait_balance") return "⏱ 15 sec";
  if (feature === "guided_range_of_motion") return "⏱ 15-20 sec";
  return "⏱ 20 sec";
}

export default function Screen10NextStep() {
  const navigate = useNavigate();
  const sessionId = getSessionId();
  const [suggestions, setSuggestions] = useState<SecondLookSuggestion[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .suggestSecondLook(sessionId)
      .then((res) => {
        if (cancelled) return;
        setSuggestions(res.suggestions);
        storeSecondLookSuggestions(res.suggestions);
      })
      .catch(() => !cancelled && setSuggestions([]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const priority = suggestions?.[0];
  const rest = suggestions?.slice(1) ?? [];
  const isRedFlag = priority?.feature === "facial_asymmetry";

  function startCapture(feature: string) {
    setChosenFeature(feature);
    navigate("/11");
  }

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate("/9")}>‹</IconBtn>
        <Tag variant="accent">Adaptive protocol</Tag>
      </Top>
      <h2 className="text-[26px] font-bold mb-1.5">Recommended next step</h2>
      <p className="text-sm text-text-2 mb-5">One extra capture will sharpen the screening decision.</p>

      {loading && <Note title="Reading the reported symptoms">Choosing the highest-value next capture…</Note>}

      {!loading && !priority && (
        <Note title="No adaptive capture proposed">
          Nothing in the reported symptoms triggers an extra capture this session.
        </Note>
      )}

      {priority && (
        <Card className={isRedFlag ? "border-bad bg-bad-soft" : "border-accent-dim bg-accent-soft"}>
          <Tag variant={isRedFlag ? "bad" : "accent"}>{isRedFlag ? "Red flag — priority" : "Priority"}</Tag>
          <h3 className="text-[19px] mt-2.5 font-semibold capitalize">
            {priority.feature.replace(/_/g, " ")}
          </h3>
          <p>{priority.rationale}</p>
          <PillRow>
            <Pill>{durationChip(priority.feature)}</Pill>
            <Pill>📷 Camera</Pill>
            <Pill>{priority.instruction.split(".")[0]}</Pill>
          </PillRow>
        </Card>
      )}

      {rest.length > 0 && <Sec title="Also suggested" right="Optional" />}
      {rest.map((s) => (
        <Card key={s.feature}>
          <Kv
            left={
              <div>
                <h3 className="font-semibold capitalize">{s.feature.replace(/_/g, " ")}</h3>
                <p className="text-text-2 text-[13px]">{s.rationale}</p>
              </div>
            }
            right={<Tag variant="mute">Optional</Tag>}
          />
        </Card>
      ))}

      {priority && (
        <Note tone="warn">
          Skipping this capture will leave the related screening signal at low confidence.
        </Note>
      )}

      <Cta disabled={!priority} onClick={() => priority && startCapture(priority.feature)}>
        Start capture →
      </Cta>
      <Cta ghost onClick={() => navigate("/12")}>
        Skip to findings
      </Cta>
    </>
  );
}
