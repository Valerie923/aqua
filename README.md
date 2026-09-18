# StreamCheck

**An AI "second pair of eyes" for citizen scientists assessing urban streams.**
Built for the OneAquaHealth IEEE Global Hackathon 2026 — Track 3 (AI-Supported Assessment),
with Track 7 (Digital Health Standards) via FHIR export.

## The problem

Citizen scientists using the OneAquaHealth app answer ~25 questions about a stream from
where they stand. Answers are honest but inconsistent: two people at the same spot disagree
on "muddy" vs "clear", on channel shape, on whether the banks are "artificial". Bad data
quality weakens every One Health decision built on top of it.

## The solution

StreamCheck mirrors the official form exactly (same fields, same options, same wording).
When the citizen uploads their photos, a vision model reads them and predicts what each
photo-readable answer should be, with a confidence and a one-sentence, plain-language reason
("the water looks brown and cloudy"). Where the AI disagrees with the citizen, it says so
gently and asks them to keep or change their answer. **The human always makes the final
call.** Every flag and decision is logged, each submission gets a reliability score, and the
result can be exported as HL7 FHIR.

Fields a photo cannot answer (water withdrawal, sewage discharge, water height, invasive
species, feelings) are marked *human only* and never guessed.

## Architecture

```
 phone browser (static/)                     FastAPI (app/)
 ┌─────────────────────┐   POST /api/analyze  ┌──────────────────────┐   images + system prompt
 │ multi-step form     │ ───────────────────▶ │ routers/analyze.py   │ ─────────────────────────▶ Gemini (Google AI API)
 │ one section/screen  │ ◀─────────────────── │  └ vision/           │ ◀───────────────────────── strict JSON: value,
 │ camera capture      │   predictions JSON   │     base.py (iface)  │                            confidence, evidence
 │                     │                      │     gemini_provider  │
 │                     │  POST /api/submissions│     anthropic_provider│
                                              │     null_provider    │
 │ review + submit     │ ───────────────────▶ │ routers/submissions  │ ──▶ SQLite (db.py, one `submissions` table)
 └─────────────────────┘                      │ schemas.py = the form│
                                              └──────────────────────┘
```

- `app/schemas.py` is the single source of truth: the official form as Pydantic models.
  The frontend fetches its option lists from `/api/form-options`, and the vision prompt is
  built from the same enums, so the three can never drift apart.
- `app/vision/base.py` is a one-method interface. Gemini is the default provider (free
  tier); a Claude provider is included to prove the swap is one file. The provider is chosen
  by which API key is set. An on-device model would be one more file.
- The AI is zero-shot: no training data, no fine-tuning. The model is told to be
  conservative, to use low confidence when unsure, and to write evidence in everyday words.
- Structured output: the API is asked for JSON constrained to the `VisionPredictions`
  schema. A malformed answer is an error, never a silent bad prediction.
- If the AI is unavailable (no key, rate limit, refusal), the form still works and the
  citizen is told plainly why there is no AI reading. Results are never faked.
- `app/rules.py` is deterministic and unit-tested: it compares answers with the AI reading,
  runs the consistency rules, and computes the reliability score. No AI call happens there.

## Human in the loop (Phase 2)

After each section the app calls `POST /api/check` with the answers so far. Three kinds of
flag can come back, each with a plain-language message:

| Kind | When | Buttons |
|---|---|---|
| AI disagrees | citizen's answer differs from the AI's and AI confidence ≥ 0.7 | Keep my answer / Change to "…" |
| AI suggestion | citizen answered "Not sure" and AI confidence ≥ 0.5 | Keep "Not sure" / Use "…" |
| Consistency rule | answers contradict each other | Keep as is / Go back and fix |

Agreement shows a small green tick under the question and never interrupts. Every flag and
the citizen's decision is stored with the submission as an audit trail, together with the
answers as originally entered and the final answers. The human's choice is always final.

Consistency rules (all in `app/rules.py`):

- water flow is "Dry" but a water height above 0 was given
- no vegetation on a bank, but a vegetation type was chosen for that bank
- overall "Good" despite sewage discharge, draining pipes, an artificial bottom, or foam /
  altered colour
- overall "Poor" although bed and banks are natural, water is clear and no pressure was reported

## One Health insight (Phase 3)

Both parts are rule-based (`app/insights.py`), deterministic and unit-tested. No AI is involved,
so every line can be traced back to the citizen's own answers.

**Suggested overall assessment.** Before the citizen picks Good / Moderate / Poor, the app
shows a suggestion with reasons. Pressure points add up: sewage discharge 5, draining pipes 2,
foam or altered colour 2 (muddy 1), artificial bottom 2, artificial banks 1, no vegetation on
both banks 2 (one bank 1), both banks paved 1, barrier 1, works 1, stagnant or dry 1, no
habitats 1. 0–1 points → Good, 2–4 → Moderate, 5+ → Poor. "Not sure" answers count 0 and are
listed. The citizen's own pick is what gets stored as `overall_assessment`.

**One Health risk card.** Each note cites the answers that triggered it and ends with one
line on why it matters for people, animals and the environment:

| Trigger | Note | Level |
|---|---|---|
| slow or stagnant flow + pools or natural debris | mosquito breeding (dengue relevance in Singapore) | medium |
| sewage, draining pipes, foam or altered colour | pollution and germs, avoid contact | high |
| artificial bottom + a bank with no vegetation | low biodiversity, heat and flood resilience | medium |
| vegetation on both banks + clear water + no pollution signs | good for wellbeing and recreation | positive |

The card's overall level is the worst note present (high > medium > positive > low).

**My submissions** (`static/submissions.html`) lists past entries with reliability and One
Health level, and shows them on a Leaflet + OpenStreetMap map coloured by the suggested
assessment. Clicking an entry centres the map on it.

## Reliability score

Computed server-side per submission, 0–100:

| Component | Max | How |
|---|---|---|
| AI agreement | 50 | 50 × (final answers matching a confident AI reading) ÷ (fields with a confident AI reading). "Confident" means confidence ≥ 0.5 and not "not sure". |
| Photos | 20 | 6 each for upstream, downstream and surroundings; 2 for the biodiversity photo |
| Consistency | 30 | 30 − 10 per unresolved flag − 3 per "Not sure" answer, floored at 0. Unresolved = a consistency rule that still fails on the final answers, or an AI flag never answered. |

If the AI reading was unavailable, the agreement component is dropped and the other two are
rescaled to 100, so citizens are not penalised for our outage. A kept disagreement is not
"unresolved" (the human decided), but it does lower the agreement component.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env            # add your GEMINI_API_KEY (free at aistudio.google.com/apikey)
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload
# open http://localhost:8000
```

Tests (deterministic, no network):

```bash
python -m pytest -q
```

Docker / Render / Hugging Face Spaces:

```bash
docker build -t streamcheck . && docker run -p 8000:8000 -e GEMINI_API_KEY=AIza... streamcheck
```

`render.yaml` describes a one-service deployment; set `GEMINI_API_KEY` in the dashboard.

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | Which vision provider and model are active |
| GET | `/api/form-options` | Option lists straight from the Pydantic schema |
| GET | `/api/sites` | Seeded Singapore sites (site name stays free text) |
| POST | `/api/analyze` | multipart photos (`upstream`, `downstream`, `context`, `biodiversity`) → predictions |
| POST | `/api/check` | `{photo_set_id, answers, flags}` → flags for the answers so far + reliability preview (deterministic) |
| POST | `/api/submissions` | `{photo_set_id, answers, final_answers, flags}` → stored submission with server-computed reliability |
| GET | `/api/submissions[/{id}]` | list / fetch, each with flags, reliability, suggested assessment and One Health |

## How it fits into OneAquaHealth

StreamCheck is designed as a **validation layer**, not a replacement app. It takes exactly
the inputs the official Citizen Science App already collects (photos + form) and returns
per-field predictions with evidence, flags, and a reliability score. That can sit inside
their existing app as a step between "answer" and "submit". The FHIR export (Phase 4) lets
validated observations flow into health information systems using a standard they already
target.

## Status

- [x] Phase 1 — form mirroring the official app + AI photo reading with evidence
- [x] Phase 2 — human-in-the-loop flags, consistency rules, audit trail, reliability score
- [x] Phase 3 — One Health risk card, suggested overall assessment, submissions map
- [ ] Phase 4 — HL7 FHIR R4 export + send to HAPI sandbox
- [ ] Phase 5 — demo mode, About page, accessibility pass

## Limitations

- The vision model is zero-shot and has not been validated against expert labels. Its
  confidence is self-reported, not calibrated. Treat it as a prompt for the citizen to look
  again, not as ground truth.
- The reliability formula weights and the suggested-assessment points are design choices,
  not calibrated against expert data. The One Health notes are indicative, not a health advisory.
- Left/right bank orientation depends on the citizen taking the downstream photo correctly.
- Short video from the official form is not used.
- Photos are stored on local disk; a production deployment would use object storage.
- On-device inference is future work; today every reading needs a network call.
