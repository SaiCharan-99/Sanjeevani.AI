// Sanjeevani graph schema — constraints and indexes.
// Idempotent: uses IF NOT EXISTS everywhere. Applied on startup by graph/client.py.
//
// :KB subgraph (read-only at runtime, written only by seed.py)
CREATE CONSTRAINT kb_disease_slug IF NOT EXISTS FOR (d:Disease) REQUIRE d.slug IS UNIQUE;
CREATE CONSTRAINT kb_symptom_slug IF NOT EXISTS FOR (s:Symptom) REQUIRE s.slug IS UNIQUE;
CREATE CONSTRAINT kb_precaution_slug IF NOT EXISTS FOR (p:Precaution) REQUIRE p.slug IS UNIQUE;
CREATE CONSTRAINT kb_test_slug IF NOT EXISTS FOR (t:DiagnosticTest) REQUIRE t.slug IS UNIQUE;
CREATE CONSTRAINT kb_exposure_slug IF NOT EXISTS FOR (e:Exposure) REQUIRE e.slug IS UNIQUE;
CREATE CONSTRAINT kb_stage_slug IF NOT EXISTS FOR (st:Stage) REQUIRE st.slug IS UNIQUE;
CREATE CONSTRAINT kb_vitaltype_slug IF NOT EXISTS FOR (v:VitalType) REQUIRE v.slug IS UNIQUE;
CREATE CONSTRAINT kb_medication_slug IF NOT EXISTS FOR (m:Medication) REQUIRE m.slug IS UNIQUE;
CREATE CONSTRAINT kb_sideeffect_slug IF NOT EXISTS FOR (se:SideEffect) REQUIRE se.slug IS UNIQUE;

// :PHI subgraph (written only by the app at runtime)
CREATE CONSTRAINT phi_person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE;
CREATE CONSTRAINT phi_session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE;
CREATE CONSTRAINT phi_village_id IF NOT EXISTS FOR (v:Village) REQUIRE v.village_id IS UNIQUE;
CREATE CONSTRAINT phi_reading_id IF NOT EXISTS FOR (r:Reading) REQUIRE r.reading_id IS UNIQUE;
CREATE CONSTRAINT phi_utterance_id IF NOT EXISTS FOR (u:Utterance) REQUIRE u.utterance_id IS UNIQUE;
CREATE CONSTRAINT phi_finding_id IF NOT EXISTS FOR (f:Finding) REQUIRE f.finding_id IS UNIQUE;
CREATE CONSTRAINT phi_assessment_id IF NOT EXISTS FOR (a:Assessment) REQUIRE a.assessment_id IS UNIQUE;

CREATE INDEX kb_disease_review IF NOT EXISTS FOR (d:Disease) ON (d.review);
CREATE INDEX phi_person_village IF NOT EXISTS FOR (p:Person) ON (p.village);
CREATE INDEX phi_session_person IF NOT EXISTS FOR (s:Session) ON (s.person_id);
