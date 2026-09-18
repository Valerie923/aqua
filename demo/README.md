# Demo mode

Demo mode runs the **real** pipeline on **real** photos. Nothing is pre-computed: the vision
model reads the photos live, the rule engine flags what it flags, and the score is whatever it
comes out as. That is deliberate — judges should see the product, not a recording.

## 1. Add photos (once)

Put your own photos of each site here, named by role:

```
demo/photos/bishan_park/upstream.jpg
demo/photos/bishan_park/downstream.jpg
demo/photos/bishan_park/context.jpg
demo/photos/bishan_park/biodiversity.jpg   (optional)
demo/photos/concrete_canal/...
demo/photos/rochor_canal/...
```

Any scenario folder that has at least the three required photos becomes available in the app
under **Photos → "Or try demo photos"**. JPEG or PNG; phone photos are fine (they are
downscaled before being sent to the model). Take them yourself or use photos you have the
right to publish. Commit them so the deployed site has them.

`demo/scenarios.json` holds each scenario's site and the citizen's answers used by the seed
script. The answers are ordinary citizen answers, including a couple of "Not sure" and at
least one answer we expect a photo to contradict — that is the moment the video should open on.

## 2. Seed the "My submissions" page (optional)

```bash
export GEMINI_API_KEY=...
python scripts/seed_demo.py           # runs each scenario with photos through the real pipeline
python scripts/seed_demo.py --reset   # remove earlier demo submissions first
```

Seeded submissions are tagged "Demo" in the list and map. Because no human is present when
the script runs, every flag it raises is recorded with the decision "kept" and the submission
notes say so. Anything a judge submits through the form is a normal submission.

## 3. Walk-through for judges (about 30 seconds)

1. Open the app, pick a known site, tap Next.
2. Tap **"Or try demo photos"** and pick a scenario. The AI starts reading immediately.
3. Answer Section A quickly, deliberately giving one wrong answer (e.g. "Clear-transparent"
   on the concrete canal). Tap Next.
4. The **Quick check** shows what the AI saw and why, in plain words. Keep or change.
5. Continue to the end: reliability score, One Health card, Export FHIR.
