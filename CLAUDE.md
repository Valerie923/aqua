# StreamCheck — OneAquaHealth IEEE Global Hackathon 2026

## What we're building
A mobile-friendly web app that acts as an AI "second pair of eyes" for citizen scientists
doing urban stream assessments. The citizen uploads the same photos and answers the same
questions as the official OneAquaHealth Citizen Science App (apps.oneaquahealth.eu). Our AI
reads the photos, predicts what the answers should be, and flags disagreements with the
citizen's answers — with a plain-language explanation. The human always makes the final call.
Every submission gets a reliability score, a One Health risk summary, and can be exported as
HL7 FHIR JSON.

Primary track: Track 3 (AI-Supported Assessment). Secondary: Track 7 (Digital Health
Standards) via FHIR export. Team: 2 students. Deadline: 1 Oct 2026. Must be deployable with a
public live link for judges.

## Judging criteria (design every decision around these)
- 30% Impact & alignment with OneAquaHealth mission (better data quality → better One Health decisions)
- 20% Innovation (explainable, human-in-the-loop, not "another dashboard")
- 20% Technical implementation (clean architecture, real APIs, working end to end)
- 15% Usability (simple, one thing per screen, works on phone, plain language)
- 15% Feasibility & scalability (drop-in layer for their existing app, standards-based output)

## Ground rules
- MVP first. Build in the phase order below. Do NOT start a later phase until the earlier one
  works end to end and is committed. Ask me before adding any feature not listed here.
- Keep code simple and readable. I need to explain every file to judges. Prefer boring tech.
- Never fake results. If the AI is unsure, say unsure. No hardcoded demo answers.
- Mirror the official form exactly — same field names, same options, same wording. Their
  judges know the form; ours must be recognisably the same.
- Commit after every working step with clear messages. Work on a feature branch and open a PR.
- Write a README as we go (problem, solution, architecture diagram, how to run, how it fits
  into OneAquaHealth, limitations).
- Keep every AI explanation in the citizen's words ("water looks brown and cloudy"), not ML
  jargon. That is the usability 15%.
- Do NOT fine-tune or train our own image model. Use a vision LLM zero-shot; it predicts the
  exact form fields and writes out why (explainable AI for free). Frame on-device models as
  future work.

## Stack
- Backend: Python, FastAPI, Pydantic models. Vision via Gemini API (google-genai SDK, image
  input, JSON constrained to a schema) because the free tier costs nothing. A Claude provider
  is kept as a second implementation. Keep the vision provider behind one interface.
- Frontend: single-page vanilla HTML/CSS/JS (or React if clearly simpler), mobile-first,
  `<input type="file" accept="image/*" capture="environment">` for phone camera.
- Storage: SQLite via SQLAlchemy. One `submissions` table storing raw answers, AI predictions,
  flags, final answers, reliability score.
- Deploy: Render or Hugging Face Spaces (Docker). Env var for API key.
- Tests: pytest for the rule engine, FHIR mapper, and scoring. These must be deterministic.

## The official form (replicate this exactly as a Pydantic schema)
Site: name, lat, lon (allow user to add a new site; seed a few Singapore sites e.g. Bishan
canal, Sungei Ulu Pandan, Kallang River, plus keep the field free-text).
Photos: upstream, downstream, surrounding context, biodiversity element (optional), short video (optional, can skip).

Section A — "What do you see from where you stand (ca. 100m)?"
- channel_form: Flat / U Shape / V Shape / not_sure
- bottom_type: Natural / Artificial (concrete or stones with concrete) / not_sure
- bank_type: Natural / Artificial (concrete or stones with concrete) / Laid stones with no concrete / not_sure
- habitats: multi-select (use: riffles, pools, submerged vegetation, emergent vegetation, overhanging vegetation, roots, woody debris, gravel/cobbles, sand/silt, none)
- natural_debris: multi-select (leaves, branches, logs, none)
- water_flow: Fast (waves/high velocity) / Slow / Stagnant-intermittent / Dry / not_sure

Section B
- water_aspect: Clear-transparent / Muddy-turbid / Has foam / Has colours-altered colour / not_sure
- water_withdrawal: yes/no/not_sure
- barriers (dams or transversal artificial barriers): yes/no/not_sure
- draining_pipes (pipes draining polluted water): yes/no/not_sure
- sewage_discharge: yes/no/not_sure
- construction (works in stream): yes/no/not_sure
- water_height_m: float

Section C — riparian zone (5–10 m from banktop), left/right defined looking downstream
- impervious_left, impervious_right (>1/3 covered by roads/sidewalks/buildings): yes/no/not_sure
- vegetation_left, vegetation_right: yes/no/not_sure
- vegetation_type_left, vegetation_type_right: Herbs / Shrubs / Trees / not_sure
- invasive_species: yes/no + free text "which ones"
- vegetation_cuts (recent cuts on banks): yes/no/not_sure

Section D — Feedback
- overall_assessment: Good / Moderate / Poor (with the official descriptions shown as help text)
- feelings: joy, serenity, anger, fear — each 0–5 or not_applicable

## Phase 1 — Form + AI photo reading (core, must work first)
1. Multi-step form matching the sections above, one section per screen, progress bar.
2. On photo upload, backend sends upstream + downstream + context photos to the vision model
   with a system prompt that returns STRICT JSON: for each AI-readable field
   (channel_form, bottom_type, bank_type, water_flow, water_aspect, barriers, draining_pipes,
   construction, impervious_left/right, vegetation_left/right, vegetation_type_left/right,
   habitats, natural_debris) return {value, confidence: 0–1, evidence: one sentence
   describing what in the photo supports this}. Fields the AI cannot judge from photos
   (water_withdrawal, sewage_discharge, water_height, invasive species, feelings) are marked
   "human_only".
3. Prompt must tell the model to be conservative: low confidence when photo is ambiguous;
   never invent.

## Phase 2 — Human-in-the-loop validation (the innovation)
1. After the citizen answers a section, compare answers to AI predictions.
   - Disagreement with AI confidence ≥ 0.7 → show a gentle flag: "Our AI thinks this looks
     [Muddy/turbid] because [evidence]. Keep your answer or change it?" Buttons: Keep / Change.
   - Citizen answered "not_sure" → offer AI suggestion with evidence, citizen accepts or rejects.
   - Agreement → small green tick, no interruption.
2. Deterministic consistency rules (rule engine, unit-tested), e.g.:
   - water_flow = Dry but water_height > 0 → flag
   - vegetation_left = No but vegetation_type_left set → flag
   - overall = Good but (sewage_discharge = yes or bottom_type = Artificial or water_aspect = foam/colour) → flag with explanation
3. Log every flag and the human decision (kept/changed). This audit trail is the
   "human judgement preserved" evidence for judges.
4. Reliability score per submission (0–100): based on % of fields with AI agreement,
   unresolved flags, count of not_sure, photo count. Show the formula in README.

## Phase 3 — One Health insight + AI-suggested overall assessment
1. Rule-based suggested overall_assessment (Good/Moderate/Poor) computed from the fields,
   shown to the citizen with reasons, before they pick their own. Their pick is final.
2. One Health risk card (rule-based, plain language, cite the fields that triggered it):
   - stagnant/slow + warm climate + debris/pools → mosquito breeding risk (dengue relevance)
   - sewage/draining pipes/foam/colour → pathogen & pollution risk, avoid contact
   - artificial bottom + no riparian vegetation → low biodiversity, heat & flood resilience concern
   - good vegetation + clear water → positive wellbeing/recreation note
   Include a one-line "why this matters for people, animals, environment" for each.
3. Simple "My submissions" page listing past entries with reliability score and risk level,
   plus a basic map (Leaflet + OpenStreetMap) of sites coloured by suggested assessment.

## Phase 4 — FHIR export (Track 7)
1. Map a submission to HL7 FHIR R4: one Bundle containing a Location resource (site) and one
   Observation per field (code.text = field name, valueString/valueQuantity, effectiveDateTime,
   subject/focus → Location). Add an extension for ai_confidence and reliability_score, and
   a Provenance resource recording that a human confirmed the values.
2. "Export FHIR" button downloads the Bundle JSON; also a "Send to FHIR sandbox" button that
   POSTs to a public HAPI FHIR test server and shows the returned ID.
3. Unit-test the mapper with a fixed submission.

## Phase 5 — Polish for judges
- Demo mode: preload 2–3 sample submissions with real photos so judges can click through in 30 s.
- Clear "How it fits into OneAquaHealth" section in README + in-app About page:
  designed as a validation layer that can sit inside their existing app; FHIR output enables
  integration with health information systems.
- Limitations section: vision model is zero-shot, needs validation against expert labels;
  on-device model is future work.
- Accessibility basics: large tap targets, labels, works without hover.
- Demo video: show the moment AI catches a wrong answer within the first 45 seconds.

## Repo layout
- `app/schemas.py` — the official form as Pydantic models + AI prediction types. Single source of truth for field names and options.
- `app/vision/` — `base.py` (provider interface), `prompt.py`, `gemini_provider.py` (default),
  `anthropic_provider.py` (alternative), `null_provider.py`. `get_provider()` picks by API key.
- `app/rules.py` — deterministic: citizen-vs-AI comparison, consistency rules, reliability score.
- `app/routers/` — `analyze.py` (photos → predictions), `check.py` (flags + score), `submissions.py`, `sites.py`.
- `app/db.py` — SQLAlchemy + SQLite, one `submissions` table.
- `static/` — vanilla HTML/CSS/JS multi-step form.
- `tests/` — pytest, deterministic (no network).
