"""Named Cypher constants. Never write Cypher inline in business logic (CLAUDE.md).

Every query used by graph/client.py, graph/seed.py or any api/ module lives here.
"""

# ---------------------------------------------------------------------------
# Schema application
# ---------------------------------------------------------------------------

APPLY_SCHEMA_STATEMENTS_MARKER = "SPLIT_ON_SEMICOLON"  # see client.py::apply_schema

# ---------------------------------------------------------------------------
# KB seed — Kaggle layer
# ---------------------------------------------------------------------------

MERGE_KB_DISEASE = """
MERGE (d:KB:Disease {slug: $slug})
ON CREATE SET d.name = $name, d.source = $source
SET d.description = coalesce($description, d.description)
"""

MERGE_KB_SYMPTOM = """
MERGE (s:KB:Symptom {slug: $slug})
ON CREATE SET s.name = $name, s.source = $source
SET s.severity = coalesce($severity, s.severity),
    s.aliases = coalesce($aliases, s.aliases)
"""

MERGE_KB_PRECAUTION = """
MERGE (p:KB:Precaution {slug: $slug})
SET p.text = $text
"""

MERGE_PRESENTS_WITH_KAGGLE = """
MATCH (d:KB:Disease {slug: $disease_slug})
MATCH (s:KB:Symptom {slug: $symptom_slug})
MERGE (d)-[r:PRESENTS_WITH]->(s)
SET r.frequency = $frequency, r.weight = $weight, r.source = 'kaggle'
"""

MERGE_REQUIRES_PRECAUTION = """
MATCH (d:KB:Disease {slug: $disease_slug})
MATCH (p:KB:Precaution {slug: $precaution_slug})
MERGE (d)-[r:REQUIRES_PRECAUTION]->(p)
SET r.order = $order
"""

# ---------------------------------------------------------------------------
# KB seed — curated layer (overrides Kaggle on same slug/edge)
# ---------------------------------------------------------------------------

MERGE_KB_DISEASE_CURATED = """
MERGE (d:KB:Disease {slug: $slug})
SET d.name = $name,
    d.source = 'curated',
    d.description = $description,
    d.why_it_occurs = $why_it_occurs,
    d.mitigation = $mitigation,
    d.endemic_regions = $endemic_regions,
    d.review = $review
"""

MERGE_KB_SYMPTOM_CURATED = """
MERGE (s:KB:Symptom {slug: $slug})
ON CREATE SET s.source = 'curated'
SET s.name = coalesce($name, s.name),
    s.severity = coalesce($severity, s.severity)
"""

MERGE_PRESENTS_WITH_CURATED = """
MATCH (d:KB:Disease {slug: $disease_slug})
MATCH (s:KB:Symptom {slug: $symptom_slug})
MERGE (d)-[r:PRESENTS_WITH]->(s)
SET r.weight = $weight,
    r.typical_stage = $typical_stage,
    r.screening_rule = $screening_rule,
    r.min_duration_days = $min_duration_days,
    r.source = 'curated'
"""

MERGE_KB_TEST = """
MERGE (t:KB:DiagnosticTest {slug: $slug})
SET t.name = $name
"""

MERGE_CONFIRMED_BY = """
MATCH (d:KB:Disease {slug: $disease_slug})
MATCH (t:KB:DiagnosticTest {slug: $test_slug})
MERGE (d)-[r:CONFIRMED_BY]->(t)
SET r.priority = $priority
"""

MERGE_KB_EXPOSURE = """
MERGE (e:KB:Exposure {slug: $slug})
SET e.name = $name
"""

MERGE_RISK_FACTOR = """
MATCH (d:KB:Disease {slug: $disease_slug})
MATCH (e:KB:Exposure {slug: $exposure_slug})
MERGE (d)-[r:RISK_FACTOR]->(e)
SET r.weight = $weight
"""

MERGE_KB_STAGE = """
MERGE (st:KB:Stage {slug: $slug})
SET st.name = $name, st.order = $order
"""

MERGE_HAS_STAGE = """
MATCH (d:KB:Disease {slug: $disease_slug})
MATCH (st:KB:Stage {slug: $stage_slug})
MERGE (d)-[:HAS_STAGE]->(st)
"""

MERGE_KB_VITALTYPE = """
MERGE (v:KB:VitalType {slug: $slug})
SET v.name = $name
"""

MERGE_MEASURED_BY = """
MATCH (s:KB:Symptom {slug: $symptom_slug})
MATCH (v:KB:VitalType {slug: $vital_slug})
MERGE (s)-[r:MEASURED_BY]->(v)
SET r.direction = $direction
"""

MERGE_SYMPTOM_ALIAS = """
MATCH (s:KB:Symptom {slug: $slug})
SET s.aliases = coalesce(s.aliases, []) + $alias
"""

# ---------------------------------------------------------------------------
# Validation / read queries (used by seed test and api/kb.py)
# ---------------------------------------------------------------------------

COUNT_KB_NODES = "MATCH (n:KB) RETURN labels(n) AS labels, count(n) AS n"

GET_DISEASE_WITH_EDGES = """
MATCH (d:KB:Disease {slug: $slug})
OPTIONAL MATCH (d)-[pw:PRESENTS_WITH]->(s:KB:Symptom)
OPTIONAL MATCH (d)-[:REQUIRES_PRECAUTION]->(p:KB:Precaution)
OPTIONAL MATCH (d)-[:CONFIRMED_BY]->(t:KB:DiagnosticTest)
RETURN d,
       collect(DISTINCT {symptom: s.slug, weight: pw.weight}) AS symptoms,
       collect(DISTINCT p.text) AS precautions,
       collect(DISTINCT t.name) AS tests
"""

LIST_SYMPTOMS = "MATCH (s:KB:Symptom) RETURN s.slug AS slug, s.name AS name, s.severity AS severity, s.aliases AS aliases ORDER BY s.slug"

RESOLVE_ALIAS = """
MATCH (s:KB:Symptom)
WHERE s.slug = $term OR $term IN coalesce(s.aliases, [])
RETURN s.slug AS slug LIMIT 1
"""

GET_TB_SCREENING_EDGE = """
MATCH (d:KB:Disease {slug: 'tuberculosis'})-[r:PRESENTS_WITH]->(s:KB:Symptom {slug: 'cough'})
RETURN r.screening_rule AS screening_rule, r.min_duration_days AS min_duration_days, r.weight AS weight
"""

DISEASE_HAS_SYMPTOM_DESC_PRECAUTION = """
MATCH (d:KB:Disease)
OPTIONAL MATCH (d)-[:PRESENTS_WITH]->(s:KB:Symptom)
OPTIONAL MATCH (d)-[:REQUIRES_PRECAUTION]->(p:KB:Precaution)
RETURN d.slug AS slug, d.description AS description,
       count(DISTINCT s) AS symptom_count, count(DISTINCT p) AS precaution_count
"""

SYMPTOM_HAS_SEVERITY = "MATCH (s:KB:Symptom) RETURN s.slug AS slug, s.severity AS severity"

# ---------------------------------------------------------------------------
# PHI writes (stubs used by api/ modules in Phase 1; full graph writes land Phase 3+)
# ---------------------------------------------------------------------------

CREATE_PERSON_AND_SESSION = """
MERGE (v:PHI:Village {village_id: $village_id})
ON CREATE SET v.name = $village_name
MERGE (p:PHI:Person {person_id: $person_id})
ON CREATE SET p.name = $name, p.age = $age, p.gender = $gender
MERGE (p)-[:LIVES_IN]->(v)
CREATE (s:PHI:Session {
  session_id: $session_id, language: $language, consent: $consent,
  created_at: $created_at, status: 'running'
})
MERGE (p)-[:HAD_SESSION]->(s)
RETURN p.person_id AS person_id, s.session_id AS session_id
"""

# ---------------------------------------------------------------------------
# PHI — continuous session persistence (Tier 2, architecture.md §6). Written
# during the session, not only at the end, so a mid-session crash loses nothing.
# ---------------------------------------------------------------------------

CREATE_SESSION_READING = """
MATCH (s:PHI:Session {session_id: $session_id})
CREATE (r:PHI:Reading {
  reading_id: $reading_id, vital: $vital, value: $value, unit: $unit,
  quality: $quality, tier: $tier, created_at: $created_at
})
CREATE (s)-[:CAPTURED]->(r)
RETURN r.reading_id AS reading_id
"""

MARK_SESSION_STATUS = """
MATCH (s:PHI:Session {session_id: $session_id})
SET s.status = $status
RETURN s.session_id AS session_id
"""

COMPLETE_SESSION = """
MATCH (s:PHI:Session {session_id: $session_id})
SET s.status = 'done_unopened',
    s.completed_at = $completed_at,
    s.top_findings = $top_findings,
    s.recommendations = $recommendations
RETURN s.session_id AS session_id
"""

LIST_PENDING_SESSIONS = """
MATCH (p:PHI:Person)-[:HAD_SESSION]->(s:PHI:Session)
WHERE s.status IN ['queued', 'running', 'done_unopened']
RETURN s.session_id AS session_id, p.name AS person_name, s.status AS status
ORDER BY s.created_at DESC
"""

# ---------------------------------------------------------------------------
# PHI — person memory (Tier 3, architecture.md §6)
# ---------------------------------------------------------------------------

GET_PERSON_FOR_SUMMARY = """
MATCH (p:PHI:Person {person_id: $person_id})-[:LIVES_IN]->(v:PHI:Village)
RETURN p.person_id AS person_id, p.name AS name, p.age AS age, p.gender AS gender,
       v.village_id AS village_id, v.name AS village_name
"""

LIST_PERSON_SESSIONS_WITH_READINGS = """
MATCH (p:PHI:Person {person_id: $person_id})-[:HAD_SESSION]->(s:PHI:Session)
OPTIONAL MATCH (s)-[:CAPTURED]->(r:PHI:Reading)
WITH s, collect(CASE WHEN r IS NULL THEN null ELSE
  {vital: r.vital, value: r.value, unit: r.unit, quality: r.quality, tier: r.tier}
  END) AS readings
RETURN s.session_id AS session_id, s.created_at AS created_at, s.status AS status,
       coalesce(s.top_findings, []) AS top_findings,
       coalesce(s.recommendations, []) AS recommendations,
       [x IN readings WHERE x IS NOT NULL] AS readings
ORDER BY s.created_at DESC
"""

VILLAGE_AUTOCOMPLETE = """
MATCH (v:PHI:Village)
WHERE toLower(v.name) CONTAINS toLower($prefix)
RETURN DISTINCT v.name AS name
ORDER BY v.name
LIMIT 10
"""

# ---------------------------------------------------------------------------
# PHI — consultation (Phase 4). The join between person data and the knowledge
# graph: every :REPORTS edge carries confidence + verbatim (architecture.md §5
# "The join"; CLAUDE.md rule 6). Runtime never creates :KB nodes — the MATCH on
# :KB:Symptom simply finds nothing when the slug is unknown, and the utterance
# keeps its unmapped_text.
# ---------------------------------------------------------------------------

CREATE_UTTERANCE = """
MATCH (s:PHI:Session {session_id: $session_id})
MERGE (u:PHI:Utterance {utterance_id: $utterance_id})
SET u.speaker = $speaker, u.text = $text, u.text_original = $text_original,
    u.start_s = $start_s, u.language = $language, u.created_at = $created_at
MERGE (s)-[:TRANSCRIBED]->(u)
RETURN u.utterance_id AS utterance_id
"""

CREATE_UTTERANCE_REPORTS_SYMPTOM = """
MATCH (s:PHI:Session {session_id: $session_id})
MERGE (u:PHI:Utterance {utterance_id: $utterance_id})
SET u.speaker = 'person', u.text = $verbatim, u.text_original = $verbatim_original,
    u.language = $language, u.created_at = $created_at,
    u.unmapped_text = $unmapped_text, u.duration_days = $duration_days,
    u.source = $source
MERGE (s)-[:TRANSCRIBED]->(u)
WITH u
OPTIONAL MATCH (sym:KB:Symptom {slug: $slug})
FOREACH (_ IN CASE WHEN sym IS NULL THEN [] ELSE [1] END |
  MERGE (u)-[rep:REPORTS]->(sym)
  SET rep.confidence = $confidence, rep.verbatim = $verbatim
)
RETURN u.utterance_id AS utterance_id
"""

DELETE_SESSION_UTTERANCES = """
MATCH (s:PHI:Session {session_id: $session_id})-[:TRANSCRIBED]->(u:PHI:Utterance)
DETACH DELETE u
"""

LIST_SESSION_REPORTED_SYMPTOMS = """
MATCH (s:PHI:Session {session_id: $session_id})-[:TRANSCRIBED]->(u:PHI:Utterance)
OPTIONAL MATCH (u)-[rep:REPORTS]->(sym:KB:Symptom)
RETURN u.utterance_id AS utterance_id, u.text AS verbatim,
       u.unmapped_text AS unmapped_text, sym.slug AS slug, rep.confidence AS confidence
"""

# ---------------------------------------------------------------------------
# PHI — second look (Phase 5). Face-mesh / pose capture findings and the join
# into the knowledge graph. Every :INDICATES edge carries confidence
# (architecture.md §5 "The join"; CLAUDE.md rule 6). Runtime never creates
# :KB:Symptom nodes here either — an unmatched slug simply writes no edge.
# ---------------------------------------------------------------------------

CREATE_FINDING = """
MATCH (s:PHI:Session {session_id: $session_id})
MERGE (f:PHI:Finding {finding_id: $finding_id})
SET f.feature = $feature, f.value = $value, f.unit = $unit, f.method = $method,
    f.interpretation = $interpretation, f.confidence = $confidence,
    f.limitations = $limitations, f.created_at = $created_at
MERGE (s)-[:OBSERVED]->(f)
RETURN f.finding_id AS finding_id
"""

CREATE_FINDING_INDICATES_SYMPTOM = """
MATCH (f:PHI:Finding {finding_id: $finding_id})
OPTIONAL MATCH (sym:KB:Symptom {slug: $slug})
FOREACH (_ IN CASE WHEN sym IS NULL THEN [] ELSE [1] END |
  MERGE (f)-[rel:INDICATES]->(sym)
  SET rel.confidence = $confidence
)
RETURN f.finding_id AS finding_id
"""

# ---------------------------------------------------------------------------
# Synthesis (Phase 6) — disease candidate traversal, capped, never dumps the
# whole KB. Scores are computed in agents/synthesis.py from these rows, not in
# Cypher, so the scoring formula stays in one place and is unit-testable.
# ---------------------------------------------------------------------------

CANDIDATE_DISEASES_FOR_SYMPTOMS = """
MATCH (d:KB:Disease)-[r:PRESENTS_WITH]->(s:KB:Symptom)
WHERE s.slug IN $slugs
WITH d, collect({symptom: s.slug, weight: r.weight, screening_rule: r.screening_rule,
                  min_duration_days: r.min_duration_days, typical_stage: r.typical_stage}) AS matched
MATCH (d)-[:PRESENTS_WITH]->(all_s:KB:Symptom)
WITH d, matched, count(DISTINCT all_s) AS total_symptoms
OPTIONAL MATCH (d)-[:CONFIRMED_BY]->(t:KB:DiagnosticTest)
WITH d, matched, total_symptoms, collect(DISTINCT {slug: t.slug, name: t.name, priority: t.priority}) AS tests
RETURN d.slug AS slug, d.name AS name, d.description AS description,
       d.review AS review, d.endemic_regions AS endemic_regions,
       matched AS matched_symptoms, total_symptoms AS total_symptoms, tests AS tests
ORDER BY d.slug
"""

DISEASE_FINDING_EDGES = """
MATCH (d:KB:Disease {slug: $disease_slug})-[r:PRESENTS_WITH]->(s:KB:Symptom)
WHERE s.slug IN $slugs
RETURN s.slug AS slug, r.weight AS weight, r.screening_rule AS screening_rule,
       r.min_duration_days AS min_duration_days
"""

# ---------------------------------------------------------------------------
# Village dashboard (Phase 7, screen 17). Aggregates only — no person
# identifiers ever leave these rows (specs.md §2 screen 17). `$prefix` matches
# `VILLAGE_AUTOCOMPLETE`'s own substring convention: distinct :PHI:Village
# nodes (e.g. "Kadiri Main" / "Kadiri West" / "Peddapuram") are treated as
# hamlets/wards of whatever village name the officer searched by.
# ---------------------------------------------------------------------------

VILLAGE_MATCHING_SESSIONS = """
MATCH (v:PHI:Village)<-[:LIVES_IN]-(p:PHI:Person)-[:HAD_SESSION]->(s:PHI:Session)
WHERE toLower(v.name) CONTAINS toLower($prefix)
OPTIONAL MATCH (s)-[:TRANSCRIBED]->(u:PHI:Utterance)-[:REPORTS]->(sym:KB:Symptom)
WITH v, s, collect(DISTINCT sym.slug) AS symptoms
RETURN v.name AS village_name, s.session_id AS session_id, s.created_at AS created_at,
       s.status AS status, coalesce(s.recommendations, []) AS recommendations,
       symptoms
ORDER BY s.created_at DESC
"""

DISTINCT_PERSON_COUNT_FOR_VILLAGE = """
MATCH (v:PHI:Village)<-[:LIVES_IN]-(p:PHI:Person)
WHERE toLower(v.name) CONTAINS toLower($prefix)
RETURN count(DISTINCT p) AS n
"""

# Symptom set + mitigation copy for a single curated disease-cluster label
# (only `waterborne_illness` exists — CLAUDE.md rule 11, do not invent more
# cluster groups). The suggestion string on the alert comes from this real
# curated field, never authored by the endpoint.
DISEASE_SYMPTOM_SLUGS = """
MATCH (d:KB:Disease {slug: $slug})
OPTIONAL MATCH (d)-[:PRESENTS_WITH]->(s:KB:Symptom)
RETURN collect(DISTINCT s.slug) AS slugs, d.mitigation AS mitigation
"""
