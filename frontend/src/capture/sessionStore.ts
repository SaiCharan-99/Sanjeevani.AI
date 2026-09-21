/** Minimal session-id + vitals-result handoff between screens 3/4/5, ahead of
 * the full Phase 3 intake/session wiring. Session creation (`/api/session/start`)
 * is Phase 3; Phase 2 needs a stable id to pass into `/api/vitals/process` so
 * the scan flow is independently testable. Falls back to the golden-path demo
 * session id (specs.md §1) when Phase 3 hasn't set a real one yet. */

import type { Finding, Language, PainPoint, SecondLookSuggestion, TranscriptTurn, VitalsProcessResponse } from "../api/types";

const SESSION_KEY = "sanjeevani_session_id";
const PERSON_KEY = "sanjeevani_person_id";
const VITALS_RESULT_KEY = "sanjeevani_vitals_result";
const DEFAULT_SESSION_ID = "SAN-2026-0982";
const DEFAULT_PERSON_ID = "p_demo";

export function getSessionId(): string {
  try {
    return sessionStorage.getItem(SESSION_KEY) ?? DEFAULT_SESSION_ID;
  } catch {
    return DEFAULT_SESSION_ID;
  }
}

export function setSessionId(id: string): void {
  try {
    sessionStorage.setItem(SESSION_KEY, id);
  } catch {
    /* sessionStorage unavailable (private mode) — session id stays in-memory default */
  }
}

export function getPersonId(): string {
  try {
    return sessionStorage.getItem(PERSON_KEY) ?? DEFAULT_PERSON_ID;
  } catch {
    return DEFAULT_PERSON_ID;
  }
}

export function setPersonId(id: string): void {
  try {
    sessionStorage.setItem(PERSON_KEY, id);
  } catch {
    /* ignore */
  }
}

export function storeVitalsResult(result: VitalsProcessResponse): void {
  try {
    sessionStorage.setItem(VITALS_RESULT_KEY, JSON.stringify(result));
  } catch {
    /* ignore */
  }
}

export function readVitalsResult(): VitalsProcessResponse | null {
  try {
    const raw = sessionStorage.getItem(VITALS_RESULT_KEY);
    return raw ? (JSON.parse(raw) as VitalsProcessResponse) : null;
  } catch {
    return null;
  }
}

/* --- Phase 4: consultation handoff (screens 6 -> 7 -> 8 -> 9) -------------- */


const LANGUAGE_KEY = "sanjeevani_language";
const AUDIO_KEY = "sanjeevani_audio_meta";
const TRANSCRIPT_KEY = "sanjeevani_transcript";
const PAIN_POINTS_KEY = "sanjeevani_pain_points";
const DEFAULT_LANGUAGE: Language = "te"; // golden path is the Telugu consultation

function read<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* sessionStorage unavailable (private mode) */
  }
}

/** The conversation language chosen on screen 2; drives the STT `language`
 * field and the original-language transcript line on screen 6. */
export function getLanguage(): Language {
  return read<Language>(LANGUAGE_KEY) ?? DEFAULT_LANGUAGE;
}

export function setLanguage(language: Language): void {
  write(LANGUAGE_KEY, language);
}

export interface AudioMeta {
  durationS: number;
  mimeType: string;
}

export function storeAudioMeta(meta: AudioMeta): void {
  write(AUDIO_KEY, meta);
}

export function readAudioMeta(): AudioMeta | null {
  return read<AudioMeta>(AUDIO_KEY);
}

export function storeTranscript(turns: TranscriptTurn[]): void {
  write(TRANSCRIPT_KEY, turns);
}

export function readTranscript(): TranscriptTurn[] | null {
  return read<TranscriptTurn[]>(TRANSCRIPT_KEY);
}

export function storePainPoints(points: PainPoint[]): void {
  write(PAIN_POINTS_KEY, points);
}

export function readPainPoints(): PainPoint[] | null {
  return read<PainPoint[]>(PAIN_POINTS_KEY);
}

/* --- Phase 5: second-look handoff (screens 10 -> 11 -> 12) ------------------ */

const SECONDLOOK_SUGGESTIONS_KEY = "sanjeevani_secondlook_suggestions";
const SECONDLOOK_FEATURE_KEY = "sanjeevani_secondlook_chosen_feature";
const SECONDLOOK_FINDINGS_KEY = "sanjeevani_secondlook_findings";

export function storeSecondLookSuggestions(suggestions: SecondLookSuggestion[]): void {
  write(SECONDLOOK_SUGGESTIONS_KEY, suggestions);
}

export function readSecondLookSuggestions(): SecondLookSuggestion[] | null {
  return read<SecondLookSuggestion[]>(SECONDLOOK_SUGGESTIONS_KEY);
}

/** The feature id screen 10's "Start capture" chose, for screen 11 to run. */
export function setChosenFeature(feature: string): void {
  write(SECONDLOOK_FEATURE_KEY, feature);
}

export function getChosenFeature(): string | null {
  return read<string>(SECONDLOOK_FEATURE_KEY);
}

/** Findings accumulate across one or more guided captures before screen 12. */
export function appendSecondLookFindings(findings: Finding[]): void {
  const existing = readSecondLookFindings() ?? [];
  write(SECONDLOOK_FINDINGS_KEY, [...existing, ...findings]);
}

export function readSecondLookFindings(): Finding[] | null {
  return read<Finding[]>(SECONDLOOK_FINDINGS_KEY);
}
