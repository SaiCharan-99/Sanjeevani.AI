/** Wireframe 2 — Intake + consent. Phase 3 — live. Consent is mandatory and
 * blocks progression; no camera before consent (absolute rule 7). Village
 * field autocompletes from prior sessions (specs.md §2). On submit, calls
 * POST /api/session/start (backend rejects consent: false) and hands the
 * real session/person id to the scan flow via sessionStore. */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { setLanguage, setPersonId, setSessionId } from "../capture/sessionStore";
import { Cta, Field, FootNote, IconBtn, Seg, Tag, Top } from "../components/Primitives";

const MIN_AGE = 0;
const MAX_AGE = 120;

function isValidAge(raw: string): boolean {
  if (!/^\d+$/.test(raw.trim())) return false;
  const age = Number(raw);
  return Number.isInteger(age) && age >= MIN_AGE && age <= MAX_AGE;
}

export default function Screen2Intake() {
  const navigate = useNavigate();
  const [consent, setConsent] = useState(false);
  const [gender, setGender] = useState<"male" | "female" | "other">("male");
  const [lang, setLang] = useState<"en" | "te" | "hi">("te");
  const [name, setName] = useState("Ramesh Kumar");
  const [age, setAge] = useState("52");
  const [village, setVillage] = useState("Kadiri Rural");
  const [villageSuggestions, setVillageSuggestions] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ageValid = isValidAge(age);

  useEffect(() => {
    if (village.trim().length < 2) {
      setVillageSuggestions([]);
      return;
    }
    let cancelled = false;
    api
      .villageAutocomplete(village.trim())
      .then((res) => {
        if (!cancelled) setVillageSuggestions(res.villages.filter((v) => v.toLowerCase() !== village.toLowerCase()));
      })
      .catch(() => {
        if (!cancelled) setVillageSuggestions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [village]);

  async function handleSubmit() {
    if (!consent || !ageValid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.startSession({
        person: { name, age: Number(age), gender, village },
        language: lang,
        consent,
      });
      setSessionId(res.session_id);
      setLanguage(lang); // drives STT + the original-language transcript line on screen 6
      setPersonId(res.person_id);
      navigate("/3");
    } catch {
      setError("Could not start the session. Check the connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        <Tag variant="accent">New intake</Tag>
      </Top>
      <h2 className="text-[26px] font-bold mb-1.5">Register person for scan</h2>
      <p className="text-sm text-text-2 mb-5">Basic details, then consent before we start the camera-based vitals scan.</p>
      <label className="block font-semibold text-[13px] text-text-2 mb-2">Full name</label>
      <Field value={name} onChange={(e) => setName(e.target.value)} className="mb-4.5" />
      <div className="flex gap-2.5 mb-4.5 items-end">
        <div className="flex-1">
          <label className="block font-semibold text-[13px] text-text-2 mb-2">Age</label>
          <Field
            value={age}
            onChange={(e) => setAge(e.target.value)}
            type="number"
            min={MIN_AGE}
            max={MAX_AGE}
            className={!ageValid ? "border-bad" : ""}
          />
          {!ageValid && <p className="text-[11px] text-bad mt-1">Age must be a whole number, 0–120</p>}
        </div>
        <div className="flex-[2]">
          <label className="block font-semibold text-[13px] text-text-2 mb-2">Gender</label>
          <div className="flex gap-2.5">
            <Seg label="Male" active={gender === "male"} onClick={() => setGender("male")} />
            <Seg label="Female" active={gender === "female"} onClick={() => setGender("female")} />
            <Seg label="Other" active={gender === "other"} onClick={() => setGender("other")} />
          </div>
        </div>
      </div>
      <label className="block font-semibold text-[13px] text-text-2 mb-2">Village</label>
      <Field value={village} onChange={(e) => setVillage(e.target.value)} className="mb-1.5" />
      {villageSuggestions.length > 0 && (
        <div className="flex gap-2 flex-wrap mb-3">
          {villageSuggestions.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => {
                setVillage(v);
                setVillageSuggestions([]);
              }}
              className="h-8 px-3 rounded-full border border-line bg-surface text-text-2 text-xs"
            >
              {v}
            </button>
          ))}
        </div>
      )}
      <div className="mb-4.5" />
      <label className="block font-semibold text-[13px] text-text-2 mb-2">Conversation language</label>
      <div className="flex gap-2.5 mb-4.5">
        <Seg label="English" active={lang === "en"} onClick={() => setLang("en")} />
        <Seg label="తెలుగు" active={lang === "te"} onClick={() => setLang("te")} />
        <Seg label="हिन्दी" active={lang === "hi"} onClick={() => setLang("hi")} />
      </div>
      <label
        onClick={() => setConsent((c) => !c)}
        className="flex gap-3.5 items-start p-4.5 rounded-r-lg border border-accent-dim bg-accent-soft cursor-pointer"
      >
        <span className={`w-6.5 h-6.5 rounded-lg flex items-center justify-center flex-shrink-0 font-bold text-[15px] ${consent ? "bg-accent text-accent-ink" : "border-2 border-text-3 text-transparent"}`}>
          ✓
        </span>
        <p className="text-sm leading-relaxed">
          I have explained the purpose of this assessment. This person consents to a camera-based scan and to a recording
          of our conversation.
        </p>
      </label>
      {error && <p className="text-[13px] text-bad mt-3">{error}</p>}
      <Cta disabled={!consent || !ageValid || submitting} onClick={handleSubmit}>
        {submitting ? "Starting…" : "Continue to scan →"}
      </Cta>
      <FootNote>🔒 Video never leaves the device</FootNote>
    </>
  );
}
