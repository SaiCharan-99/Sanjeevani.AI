/** Wireframe 15 — Person profile (specs.md alias S13). Phase 3 — live. BP
 * trend chart is categorical (elevated/stable), never a systolic axis (specs
 * §2 screen 15, rule 2). Reads GET /api/person/{id}, which assembles the
 * Tier 3 summary (architecture.md §6) server-side — this screen only renders
 * `sessions`/`vital_series`/`summary.vital_baselines`, never raw history. */
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { PersonProfileResponse } from "../api/types";
import { getPersonId } from "../capture/sessionStore";
import { Avatar, IconBtn, Item, ListShell, Meta, Sec, Stat, StatRow, Tag, Top } from "../components/Primitives";

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

export default function Screen15Profile() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const personId = params.get("person") ?? getPersonId();
  const [profile, setProfile] = useState<PersonProfileResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getPerson(personId)
      .then((res) => {
        if (!cancelled) setProfile(res);
      })
      .catch(() => {
        if (!cancelled) setProfile(null);
      });
    return () => {
      cancelled = true;
    };
  }, [personId]);

  if (!profile) {
    return (
      <>
        <Top>
          <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        </Top>
        <p className="text-sm text-text-2 text-center py-10">Loading person record…</p>
      </>
    );
  }

  const baselines = Object.entries(profile.summary?.vital_baselines ?? {}).filter(([, v]) => v !== null);

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        {profile.sessions[0]?.outcome.toLowerCase().includes("referred") && <Tag variant="bad">Active referral</Tag>}
      </Top>
      <div className="flex gap-3.5 items-center mb-5">
        <Avatar initials={initialsOf(profile.name)} />
        <div>
          <h2 className="text-[22px] font-bold m-0">{profile.name}</h2>
          <p className="text-[13px] text-text-3">
            {profile.age}y · {profile.gender[0].toUpperCase()} · {profile.village} · {personId}
          </p>
        </div>
      </div>
      <StatRow>
        <Stat label="Visits" value={profile.sessions.length} />
        <Stat label="Open flags" value={profile.summary?.open_followups.length ?? 0} tone="warn" />
        <Stat label="Last seen" value={profile.sessions[0] ? profile.sessions[0].date.slice(0, 10) : "—"} />
      </StatRow>

      {baselines.length > 0 && (
        <>
          <Sec title="Vital baselines" right="rolling median" />
          <ListShell>
            {baselines.map(([vital, value]) => (
              <Item key={vital}>
                <Meta title={vital.replace(/_/g, " ")} subtitle={`across ${profile.sessions.length} sessions`} />
                <span className="font-semibold text-[15px]">{value}</span>
              </Item>
            ))}
          </ListShell>
        </>
      )}

      <Sec title="Timeline" right={`${profile.sessions.length} encounters`} />
      <ListShell>
        {profile.sessions.length === 0 && <Item><Meta title="No sessions recorded yet" /></Item>}
        {profile.sessions.map((s, i) => (
          <Item key={`${s.date}-${i}`}>
            <Avatar initials={s.date.slice(5, 7) || String(i)} />
            <Meta title={s.kind} subtitle={`${s.date.slice(0, 10)} · ${s.outcome}`} />
            {i === 0 && <Tag variant="accent">Latest</Tag>}
          </Item>
        ))}
      </ListShell>

      {Object.keys(profile.vital_series).length > 0 && (
        <>
          <Sec title="Vital trend" right="across visits" />
          <ListShell>
            {Object.entries(profile.vital_series).map(([vital, points]) => (
              <Item key={vital}>
                <Meta
                  title={vital.replace(/_/g, " ")}
                  subtitle={points.map((p) => `${p.date.slice(0, 10)}: ${p.value}`).join("  →  ")}
                />
              </Item>
            ))}
          </ListShell>
        </>
      )}

      <div className="text-center text-accent text-sm font-semibold mt-2">Open knowledge graph →</div>
    </>
  );
}
