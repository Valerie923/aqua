# Devpost submission text (copy-paste)

Each heading below matches a field on the Devpost project form.

---

## Project name
StreamCheck

## Tagline
An AI second pair of eyes for citizen stream assessments. It explains what it sees; the citizen decides.

## Track alignment
**Primary: Track 3, AI-Supported Assessment.** Citizen observations are inconsistent and error-prone. StreamCheck uses AI responsibly to support the assessment without replacing human judgement: AI prompts, validation checks, explainable AI and a human-in-the-loop workflow are the core of the product.

**Secondary: Track 7, Digital Health Standards.** Every assessment exports as an HL7 FHIR R4 Bundle, so validated stream observations can flow into health information systems.

## Inspiration
Citizen science is how OneAquaHealth can monitor many urban streams cheaply, but every One Health decision built on that data inherits its noise. Two volunteers at the same canal can call the same water "clear" and "muddy", or the same banks "natural" and "artificial". We did not want to build another dashboard on top of noisy data. We wanted to improve the data at the moment it is collected, without taking the decision away from the citizen.

## What it does
StreamCheck is a mobile web app that mirrors the questions and options of the OneAquaHealth Citizen Science App.

1. The citizen takes the same photos as in the official app: upstream, downstream and surroundings.
2. While they answer the form, a vision AI reads the photos and predicts every photo-readable answer, with a confidence and one sentence of evidence in everyday words, such as "both banks are covered in grass and slope gently down to the water".
3. After each section, a **Quick check** appears only where it matters:
   - **The AI disagrees** with a confident reading: "Our AI thinks the bank type looks Natural because… Keep your answer or change it?"
   - **The citizen was not sure:** the AI offers its reading and evidence, which they can accept or reject.
   - **Answers contradict each other,** for example a "Dry" stream with a water height: a rule explains which ones.
   - **Agreement** shows a small green tick and never interrupts.
4. **The citizen always decides.** Every flag and every decision, kept or changed, is stored with the submission as an audit trail.
5. Each submission gets a **reliability score** out of 100, with a transparent breakdown: AI agreement, photos, consistency.
6. Before rating the stream Good, Moderate or Poor, the citizen sees a **suggested rating** worked out from their own answers, with the reasons.
7. A **One Health card** turns answers into plain-language notes for people, animals and the environment: mosquito breeding risk with dengue relevance, pollution and germ risk, low biodiversity and heat or flood resilience, and positive wellbeing.
8. Submissions appear on a **map**, and each can be **exported as HL7 FHIR R4** or sent straight to a public FHIR test server.

**Target users:** citizen scientists and community groups doing stream assessments, and the researchers and agencies who use their data.

**Expected impact:** cleaner, more consistent citizen data with a per-submission reliability score, so researchers know which observations to trust. Citizens learn while assessing, because every check explains what to look for. The FHIR output connects ecosystem observations to health systems, which is the One Health link.

## How we built it
- **Backend:** Python and FastAPI. The official form is written once as Pydantic models, and that single schema drives the user interface, the AI prompt and the validation, so they can never drift apart.
- **AI:** Google Gemini 2.5 Flash, used zero-shot. We did not train or fine-tune a model. The model must reply in JSON constrained to our schema, giving a value, confidence and evidence for each field. The prompt tells it to be conservative and to say "not sure" rather than guess. Questions a photo cannot answer, like sewage discharge, are never predicted.
- **Swappable AI provider:** the vision model sits behind a one-method interface. Gemini is the default and a Claude provider proves the swap is one file. An on-device model would be one more file.
- **Deterministic logic:** everything after the photo reading is rule-based: the comparison, consistency rules, reliability score, suggested rating, One Health notes and FHIR mapping. It is covered by 69 automated tests that run without a network.
- **FHIR R4:** a transaction Bundle with a Location for the site, one Observation per question, extensions carrying the AI's confidence, evidence and agreement plus the reliability score, and a Provenance resource recording that a human confirmed the values after an AI-assisted check.
- **Frontend:** plain HTML, CSS and JavaScript, mobile-first, one section per screen, with phone camera capture, large tap targets, keyboard focus states and screen-reader labels. Leaflet and OpenStreetMap power the map.
- **Storage and deployment:** SQLite, Docker, and Render.

## Challenges we ran into
- **The AI can be confidently wrong.** In our first real test the model said "very sure" that apartment blocks were inside the riparian zone, when they were far behind the park. This is exactly why the human must keep the final say. The citizen overruled it, the decision was recorded, and we tightened the prompt so anything beyond 10 m from the bank is ignored.
- **Explanations had to sound human.** Raw model output read "because The stream has…". We reshaped every message so it reads as one natural sentence.
- **Keeping it honest.** We refused to fake any AI result in the demo. If the AI is unavailable, the citizen is told plainly and can still finish the form.

## Accomplishments that we're proud of
- In a real run, the AI caught a wrong answer and explained why in plain words. In the same run, the citizen overruled the AI where it was wrong. Both decisions were preserved in the audit trail.
- A FHIR export that records not only the observations but who decided them and how confident the AI was.
- The whole pipeline works end to end on a phone, and is deployed publicly.

## What we learned
- Responsible AI here means designing for disagreement: showing evidence, asking rather than overriding, and recording the human's choice.
- A vision model's self-reported confidence is not calibrated. A reliability score has to combine it with photos and internal consistency.
- Health data standards like FHIR can carry environmental observations, as long as provenance is explicit.

## What's next for StreamCheck
- **Validate the AI against expert assessments.** Every submission already stores the citizen's answer, the AI's reading and the final decision. That is the dataset needed to measure and calibrate accuracy per question.
- **Integrate as a step inside the official OneAquaHealth app,** between "answer" and "submit".
- **Run an on-device model,** so it works offline at the stream and costs nothing per photo.
- **Agree official FHIR codes** for the form fields with OneAquaHealth and health-system partners.

## Built with
python, fastapi, pydantic, google-gemini, sqlite, sqlalchemy, javascript, html5, css3, leaflet, openstreetmap, hl7-fhir, docker, render

## Try it out
- Live app: https://streamcheck-jhot.onrender.com
- Code: https://github.com/Valerie923/aqua
