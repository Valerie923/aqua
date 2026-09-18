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
| POST | `/api/submissions` | `{photo_set_id, answers}` → stored submission (AI predictions attached server-side) |
| GET | `/api/submissions[/{id}]` | list / fetch |

## How it fits into OneAquaHealth

StreamCheck is designed as a **validation layer**, not a replacement app. It takes exactly
the inputs the official Citizen Science App already collects (photos + form) and returns
per-field predictions with evidence, flags, and a reliability score. That can sit inside
their existing app as a step between "answer" and "submit". The FHIR export (Phase 4) lets
validated observations flow into health information systems using a standard they already
target.

## Status

- [x] Phase 1 — form mirroring the official app + AI photo reading with evidence
- [ ] Phase 2 — human-in-the-loop flags, consistency rules, audit trail, reliability score
- [ ] Phase 3 — One Health risk card, suggested overall assessment, submissions map
- [ ] Phase 4 — HL7 FHIR R4 export + send to HAPI sandbox
- [ ] Phase 5 — demo mode, About page, accessibility pass

## Limitations

- The vision model is zero-shot and has not been validated against expert labels. Its
  confidence is self-reported, not calibrated. Treat it as a prompt for the citizen to look
  again, not as ground truth.
- Left/right bank orientation depends on the citizen taking the downstream photo correctly.
- Short video from the official form is not used.
- Photos are stored on local disk; a production deployment would use object storage.
- On-device inference is future work; today every reading needs a network call.
