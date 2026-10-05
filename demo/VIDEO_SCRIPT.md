# Demo video script (target 3:30 to 4:00; Devpost requires 3 to 5 minutes)

Rule from our brief: the AI must catch a wrong answer **before 0:45**. So the demo starts early
and the explanations come after it.

No slides needed. For the explanation parts, screen-record the **About page** of the live site
(`/about.html`): it already shows the problem, how it fits OneAquaHealth, the architecture
diagram and the limitations.

| Time | Show | Say (keep it short) |
|---|---|---|
| 0:00–0:15 | Live app on a phone, title screen | "Two volunteers at the same canal. One says the water is clear, the other says muddy. Every health decision built on that data inherits the noise. StreamCheck is an AI second pair of eyes that fixes the data while it's collected, without taking the decision away from the citizen." |
| 0:15–0:25 | Site list, then **Or try demo photos** with the Bishan photos. Top right shows "AI is reading your photos". | "Same photos and same questions as the official OneAquaHealth app. While I answer, the AI reads the photos." |
| 0:25–0:40 | Section A. Green ticks appear. Deliberately tap **Bank type: Artificial**. Tap Next. | "Green tick means the AI agrees. Now I'll make a mistake." |
| 0:40–1:05 | **Quick check**: the bank-type card. Pause on the evidence. Tap **Change to Natural**. Also show the channel-form suggestion for "Not sure" and accept it. | "It caught me, and it says why in plain words: the banks are grass sloping to the water. I decide, and my decision is recorded. When I'm not sure, it offers its reading instead of guessing." |
| 1:05–1:35 | Section C Quick check: the AI says impervious "Yes" because of apartment blocks. Tap **Keep my answer**. | "The AI can be wrong too. Those blocks are far outside the 10-metre riparian zone, so I overrule it. That's the point: responsible AI supports judgement, it doesn't replace it." |
| 1:35–1:55 | Section D: **Our suggestion** card, then pick the rating. | "Before I rate the stream, it shows what my own answers add up to, with reasons. My pick is what counts." |
| 1:55–2:30 | Review screen: scroll the **reliability score** breakdown, **What we checked** audit trail, **One Health** card. | "Every submission gets a reliability score with a transparent breakdown, a full audit trail of what was checked and what I decided, and a One Health summary: here, mosquito breeding risk, with dengue relevance in Singapore." |
| 2:30–3:00 | Done screen: **Export FHIR**, open the JSON briefly to show an Observation with the AI-prediction extension and the Provenance. Tap **Send to FHIR sandbox** and show the returned IDs. | "For Track 7, every assessment exports as an HL7 FHIR R4 Bundle: one Observation per question, the AI's confidence and evidence as extensions, and a Provenance record that a human confirmed the values. Here it is accepted by a public FHIR server." |
| 3:00–3:15 | **My submissions** map. | "Assessments land on a map, coloured by condition." |
| 3:15–3:40 | About page: architecture diagram. | "Under the hood: Gemini reads the photos zero-shot, with no training. Everything after that is deterministic, tested rules. The AI provider is swappable, so an on-device model is one file away." |
| 3:40–3:55 | About page: "How it fits" and limitations. | "It's designed as a validation layer for the existing OneAquaHealth app. The AI isn't validated against experts yet, and every submission stores exactly the data needed to do that." |
| 3:55–4:05 | End card: app link and repo link. | "StreamCheck. Human judgement kept, data quality up." |

## Recording tips
- **Phone parts:** use the phone's built-in screen recorder on the live site, in portrait.
- **Laptop parts** (About page, FHIR JSON): use the Windows Game Bar recorder (Win+Alt+R) or OBS.
- **Voice:** record it separately if talking while tapping is awkward, then line it up in CapCut, which is free.
- **Before recording:** open the live link once so the free server is awake, and do a practice run so you know which cards the AI will raise. The AI's wording can change slightly between runs. If it doesn't flag what this script expects, show what it did flag. Never fake a flag.
- **Upload:** YouTube, set to **Unlisted**, and paste that link into Devpost.
