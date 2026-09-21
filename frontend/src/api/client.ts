/** Typed API client — the only place `fetch` appears (CLAUDE.md: no fetch in
 * components). One method per endpoint in specs.md §3. */

import type {
  DiseaseEdgesOut,
  ExplainResponse,
  ExtractResponse,
  PainPointsSaveRequest,
  PainPointsSaveResponse,
  PendingSession,
  PersonProfileResponse,
  ReportGenerateResponse,
  SecondLookSubmitRequest,
  SecondLookSubmitResponse,
  SecondLookSuggestResponse,
  SessionCompleteRequest,
  SessionCompleteResponse,
  SessionSaveRequest,
  SessionSaveResponse,
  SessionStartRequest,
  SessionStartResponse,
  SymptomOut,
  SynthesisResultResponse,
  TranscribeResponse,
  VillageAutocompleteResponse,
  VillageSummaryResponse,
  VitalsProcessRequest,
  VitalsProcessResponse,
} from "./types";

export const BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const payload = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `API error ${res.status} on ${path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  startSession: (body: SessionStartRequest) =>
    request<SessionStartResponse>("/api/session/start", { method: "POST", body: JSON.stringify(body) }),

  pendingSessions: () => request<{ sessions: PendingSession[] }>("/api/session/pending"),

  saveReading: (body: SessionSaveRequest) =>
    request<SessionSaveResponse>("/api/session/save", { method: "POST", body: JSON.stringify(body) }),

  completeSession: (body: SessionCompleteRequest) =>
    request<SessionCompleteResponse>("/api/session/complete", { method: "POST", body: JSON.stringify(body) }),

  villageAutocomplete: (prefix: string) =>
    request<VillageAutocompleteResponse>(`/api/village/autocomplete?prefix=${encodeURIComponent(prefix)}`),

  processVitals: (body: VitalsProcessRequest) =>
    request<VitalsProcessResponse>("/api/vitals/process", { method: "POST", body: JSON.stringify(body) }),

  /** Multipart audio + session_id + language (specs.md §3). Multipart, so it
   * bypasses `request()`'s JSON content-type — still the only place fetch lives. */
  transcribe: async (sessionId: string, language: string, audio: Blob): Promise<TranscribeResponse> => {
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("language", language);
    form.append("audio", audio, "consultation.webm");
    const res = await fetch(`${BASE_URL}/api/consult/transcribe`, { method: "POST", body: form });
    if (!res.ok) {
      const payload = (await res.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(payload?.detail ?? `API error ${res.status} on /api/consult/transcribe`);
    }
    return (await res.json()) as TranscribeResponse;
  },

  extractPainPoints: (sessionId: string) =>
    request<ExtractResponse>(`/api/consult/extract?session_id=${encodeURIComponent(sessionId)}`, { method: "POST" }),

  savePainPoints: (body: PainPointsSaveRequest) =>
    request<PainPointsSaveResponse>("/api/consult/painpoints", { method: "POST", body: JSON.stringify(body) }),

  suggestSecondLook: (sessionId: string) =>
    request<SecondLookSuggestResponse>(`/api/secondlook/suggest?session_id=${encodeURIComponent(sessionId)}`),

  submitSecondLook: (body: SecondLookSubmitRequest) =>
    request<SecondLookSubmitResponse>("/api/secondlook/submit", { method: "POST", body: JSON.stringify(body) }),

  runSynthesis: (sessionId: string) =>
    request<{ job_id: string; status: string }>(`/api/synthesis/run?session_id=${encodeURIComponent(sessionId)}`, {
      method: "POST",
    }),

  synthesisResult: (sessionId: string) =>
    request<SynthesisResultResponse>(`/api/synthesis/result?session_id=${encodeURIComponent(sessionId)}`),

  explain: (sessionId: string, full = false) =>
    request<ExplainResponse>(`/api/synthesis/explain?session_id=${encodeURIComponent(sessionId)}&full=${full}`),

  generateReport: (sessionId: string) =>
    request<ReportGenerateResponse>("/api/report/generate", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),

  getPerson: (personId: string) => request<PersonProfileResponse>(`/api/person/${encodeURIComponent(personId)}`),

  getVillageSummary: (villageId: string) =>
    request<VillageSummaryResponse>(`/api/village/${encodeURIComponent(villageId)}/summary`),

  listSymptoms: () => request<SymptomOut[]>("/api/kb/symptoms"),

  getDisease: (slug: string) => request<DiseaseEdgesOut>(`/api/kb/diseases/${encodeURIComponent(slug)}`),
};
