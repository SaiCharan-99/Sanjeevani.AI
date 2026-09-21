/** Hand-written TypeScript types mirroring backend/app/models.py field-for-field.
 * No `any` anywhere (CLAUDE.md). Regenerate manually if the Pydantic models change. */

export type Gender = "male" | "female" | "other";
export type Language = "en" | "te" | "hi";
export type Tier = "reliable" | "approximate" | "trend_only" | "not_implemented";
export type Priority = "high" | "medium" | "low";
export type ReviewStatus = "approved" | "pending";

export interface PersonIn {
  name: string;
  age: number;
  gender: Gender;
  village: string;
}

export interface SessionStartRequest {
  person: PersonIn;
  language: Language;
  consent: boolean;
}

export interface SessionStartResponse {
  session_id: string;
  person_id: string;
}

export interface PendingSession {
  session_id: string;
  person_name: string;
  status: "queued" | "running" | "done_unopened";
}

export interface ROITrace {
  r: number[];
  g: number[];
  b: number[];
}

export interface VitalsProcessRequest {
  session_id: string;
  fps: number;
  duration_s: number;
  traces: Record<"forehead" | "cheek_l" | "cheek_r", ROITrace>;
  motion_score: number;
  timestamps: number[];
}

export interface VitalReading {
  value: number;
  unit: string;
  quality: number;
  tier: Tier;
}

export interface BPTrendReading {
  direction: "elevated" | "stable" | "low";
  quality: number;
  tier: "trend_only";
}

export interface PassiveFindings {
  pallor_score: number;
  facial_tension: number;
  blink_rate: number;
}

export interface VitalsProcessResponse {
  heart_rate: VitalReading;
  respiration_rate: VitalReading;
  spo2: VitalReading;
  bp_trend: BPTrendReading;
  passive_findings: PassiveFindings;
  overall_quality: number;
  retake_recommended: boolean;
}

export type ResponseSource = "live" | "golden_path_cache";

export interface TranscriptTurn {
  speaker: "officer" | "person";
  text: string;
  start_s: number;
  /** the same utterance in the session language; screen 6 renders it above the
   * English line. Extension to the specs.md §3 shape. */
  text_original?: string | null;
}

export interface TranscribeResponse {
  turns: TranscriptTurn[];
  language_detected: Language;
  source: ResponseSource;
}

export interface PainPoint {
  symptom: string;
  canonical: string | null;
  duration_days?: number | null;
  confidence: number;
  verbatim: string;
  verbatim_original?: string | null;
  unmapped_text?: string | null;
}

export interface ExtractResponse {
  pain_points: PainPoint[];
  red_flags: string[];
  red_flag_messages?: string[];
  source?: ResponseSource;
}

export interface PainPointsSaveRequest {
  session_id: string;
  pain_points: PainPoint[];
  edited_by?: string;
}

export interface PainPointsSaveResponse {
  session_id: string;
  saved: number;
  red_flags: string[];
}

export interface SecondLookSuggestion {
  feature: string;
  priority: Priority;
  rationale: string;
  instruction: string;
  triggered_by: string[];
}

export interface SecondLookSuggestResponse {
  suggestions: SecondLookSuggestion[];
}

export interface LandmarkFrame {
  t: number;
  pose?: Record<string, [number, number, number]>;
  face?: Record<string, [number, number, number]>;
}

export interface SecondLookSubmitRequest {
  session_id: string;
  feature: string;
  landmark_series: LandmarkFrame[];
}

export interface SecondLookSubmitResponse {
  findings: Finding[];
}

export interface Finding {
  feature: string;
  value: number;
  unit: string;
  method: string;
  interpretation: string;
  confidence: number;
  limitations: string;
}

export interface ReasoningStep {
  evidence: string;
  edge: string;
  weight: number;
  note?: string | null;
}

export interface Consideration {
  disease: string;
  score: number;
  rank: number;
  reasoning_chain: ReasoningStep[];
  recommended_tests: string[];
  priority: Priority;
  review: ReviewStatus;
}

export interface RiskModelOutput {
  name: string;
  score: number;
  /** null for the documented rule-based scorers (no trained artifact exists —
   * progress.md Open questions, resolved 2026-09-21). `metric` carries the
   * disclosure string instead. */
  f1?: number | null;
  metric?: string | null;
  basis?: string | null;
  inputs: string[];
  disclaimer: string;
}

export interface SynthesisResultResponse {
  considerations: Consideration[];
  risk_models: RiskModelOutput[];
}

export interface ExplainEdge {
  evidence: string;
  source: "reported" | "inferred" | "capture" | "village";
  confidence?: number | null;
  role: "strongest" | "supporting" | "context";
  edge?: string | null;
  weight?: number | null;
  screening_rule?: string | null;
}

/** Developer-mode graph node/edge (screen 16, Phase 7) — populated only when
 * `full=true`. Pure pass-through of the same reasoning-chain data `edges`
 * already carries, shaped for a force-graph renderer. Mirrors
 * backend/app/models.py GraphNode / GraphEdgeOut field-for-field. */
export interface GraphNode {
  id: string;
  label: string;
  type: "person" | "disease" | "symptom" | "context";
  highlighted: boolean;
}

export interface GraphEdgeOut {
  id: string;
  source: string;
  target: string;
  relationship: string;
  weight?: number | null;
  confidence?: number | null;
  role: "strongest" | "supporting" | "context";
  highlighted: boolean;
}

export interface ExplainResponse {
  consideration: string;
  score: number;
  edges: ExplainEdge[];
  nodes: GraphNode[];
  graph_edges: GraphEdgeOut[];
}

export interface SessionSummary {
  date: string;
  kind: string;
  outcome: string;
}

export interface VitalSeriesPoint {
  date: string;
  value: number | string;
}

export interface PersonSummary {
  demographics: Record<string, unknown>;
  village_context: Record<string, unknown>;
  chronic_flags: Record<string, unknown>[];
  vital_baselines: Record<string, number | null>;
  last_session: { date: string; top_findings: string[]; recommendations: string[] } | null;
  open_followups: Record<string, unknown>[];
}

export interface PersonProfileResponse {
  person_id: string;
  name: string;
  age: number;
  gender: Gender;
  village: string;
  sessions: SessionSummary[];
  vital_series: Record<string, VitalSeriesPoint[]>;
  summary?: PersonSummary | null;
}

export interface SessionSaveRequest {
  session_id: string;
  vital: string;
  value: number;
  unit: string;
  quality: number;
  tier: Tier;
}

export interface SessionSaveResponse {
  reading_id: string;
}

export interface SessionCompleteRequest {
  session_id: string;
  top_findings?: string[];
  recommendations?: string[];
}

export interface SessionCompleteResponse {
  session_id: string;
  status: string;
}

export interface VillageAutocompleteResponse {
  villages: string[];
}

export interface TopSymptom {
  slug: string;
  count: number;
}

export interface VillageTrendPoint {
  month: string;
  screened: number;
  referred: number;
}

export interface Hamlet {
  name: string;
  screened: number;
  referred: number;
  status: "ok" | "attention";
}

export interface VillageAlert {
  kind: "cluster";
  disease_group: string;
  count: number;
  baseline_multiple: number;
  window_days: number;
  ward: string;
  suggestion: string;
}

export interface VillageSummaryResponse {
  population: number;
  screened_quarter: number;
  referred: number;
  followups_due: number;
  top_symptoms: TopSymptom[];
  trend: VillageTrendPoint[];
  hamlets: Hamlet[];
  alerts: VillageAlert[];
}

export interface SymptomOut {
  slug: string;
  name: string;
  severity: number | null;
  aliases: string[];
}

export interface DiseaseEdgesOut {
  slug: string;
  name: string;
  review: ReviewStatus;
  symptoms: string[];
  precautions: string[];
  tests: string[];
}

export interface ReportGenerateResponse {
  artifact_id: string;
  pdf_url: string;
}
