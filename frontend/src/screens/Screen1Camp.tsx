/** Wireframe 1 — Camp dashboard. Phase 3 — live. specs.md §2 "1 — Camp
 * dashboard". Copy substitutions applied per specs.md §8: no BP mmHg,
 * "Anemia screening: high likelihood" not "Severe anemia suspected", no
 * offline/encryption claim. Session counts and the pending badge come from
 * GET /api/session/pending (architecture.md §6 tier 2 — every session written
 * as it happens is what makes this list real, not a snapshot). */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { PendingSession } from "../api/types";
import { Avatar, Cta, FootNote, IconBtn, Item, ListShell, Meta, Sec, Stat, StatRow, Tag, Top } from "../components/Primitives";

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

const STATUS_LABEL: Record<PendingSession["status"], string> = {
  queued: "Synthesis queued",
  running: "Synthesis running",
  done_unopened: "Report ready",
};

export default function Screen1Camp() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<PendingSession[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .pendingSessions()
      .then((res) => {
        if (!cancelled) setSessions(res.sessions);
      })
      .catch(() => {
        if (!cancelled) setSessions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const reportsPending = sessions?.filter((s) => s.status === "done_unopened").length ?? 0;
  const seenToday = sessions?.length ?? 0;

  return (
    <>
      <Top>
        <Tag variant="accent">Kadiri camp · 20 Sep</Tag>
        <IconBtn>⚙</IconBtn>
      </Top>
      <h2 className="text-[26px] font-bold mb-1.5">Good morning, Dr. Meera</h2>
      <p className="text-sm text-text-2 mb-5">
        {sessions === null ? "Loading today's sessions…" : `${seenToday} people seen today. ${reportsPending} reports waiting on you.`}
      </p>
      <StatRow>
        <Stat label="Seen today" value={seenToday} />
        <Stat label="Reports pending" value={reportsPending} tone={reportsPending > 0 ? "warn" : "text"} />
        <Stat label="Referrals" value="—" />
      </StatRow>
      <Cta onClick={() => navigate("/2")}>+ New person</Cta>
      <Sec title="Needs your attention" right={String(reportsPending)} />
      <ListShell>
        {sessions === null && <Item><Meta title="Loading…" /></Item>}
        {sessions?.filter((s) => s.status === "done_unopened").length === 0 && (
          <Item><Meta title="Nothing pending" subtitle="All reports have been reviewed" /></Item>
        )}
        {sessions
          ?.filter((s) => s.status === "done_unopened")
          .map((s) => (
            <Item key={s.session_id}>
              <Avatar initials={initialsOf(s.person_name)} />
              <Meta title={s.person_name} subtitle={s.session_id} />
              <Tag variant="warn">Report ready</Tag>
            </Item>
          ))}
      </ListShell>
      <Sec title="Today's sessions" right={`${seenToday} total`} />
      <ListShell>
        {sessions?.length === 0 && <Item><Meta title="No sessions yet today" /></Item>}
        {sessions?.map((s) => (
          <Item key={s.session_id}>
            <Avatar initials={initialsOf(s.person_name)} tone={s.status === "done_unopened" ? "accent" : "accent"} />
            <Meta title={s.person_name} subtitle={`${STATUS_LABEL[s.status]} · ${s.session_id}`} />
          </Item>
        ))}
      </ListShell>
      <FootNote>🔒 Video never leaves the device</FootNote>
    </>
  );
}
