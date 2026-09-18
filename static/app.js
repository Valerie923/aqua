/* StreamCheck — single-page multi-step form.
 *
 * Flow: Site → Photos → Section A → B → C → D → Review → Done.
 * Option lists come from /api/form-options so the UI mirrors the Pydantic
 * schema exactly. Photos are sent to /api/analyze as soon as the citizen
 * leaves the Photos screen; the AI's reading is shown on the Review screen.
 */

// ---------------------------------------------------------------------------
// Question wording (official form) — labels and help text per field.
// ---------------------------------------------------------------------------
const SECTIONS = [
  {
    key: "section_a",
    title: "Section A — What do you see from where you stand (ca. 100 m)?",
    fields: [
      { name: "channel_form", label: "Channel form", options: "channel_form" },
      { name: "bottom_type", label: "Bottom type", options: "bottom_type" },
      { name: "bank_type", label: "Bank type", options: "bank_type" },
      { name: "habitats", label: "Habitats", help: "Select all that apply.", options: "habitats", multi: true },
      { name: "natural_debris", label: "Natural debris", help: "Select all that apply.", options: "natural_debris", multi: true },
      { name: "water_flow", label: "Water flow", options: "water_flow" },
    ],
  },
  {
    key: "section_b",
    title: "Section B — Water and pressures",
    fields: [
      { name: "water_aspect", label: "Water aspect", options: "water_aspect" },
      { name: "water_withdrawal", label: "Water withdrawal", help: "Is water being taken out of the stream?", options: "yes_no" },
      { name: "barriers", label: "Barriers", help: "Dams or transversal artificial barriers.", options: "yes_no" },
      { name: "draining_pipes", label: "Draining pipes", help: "Pipes draining polluted water.", options: "yes_no" },
      { name: "sewage_discharge", label: "Sewage discharge", options: "yes_no" },
      { name: "construction", label: "Construction", help: "Works in the stream.", options: "yes_no" },
      { name: "water_height_m", label: "Water height (metres)", help: "Estimate, e.g. 0.3. Leave blank if you cannot tell.", type: "number", optional: true },
    ],
  },
  {
    key: "section_c",
    title: "Section C — Riparian zone (5–10 m from banktop)",
    lead: "Left and right are defined looking downstream.",
    fields: [
      { name: "impervious_left", label: "Impervious surface — left bank", help: "More than 1/3 covered by roads, sidewalks or buildings?", options: "yes_no" },
      { name: "impervious_right", label: "Impervious surface — right bank", help: "More than 1/3 covered by roads, sidewalks or buildings?", options: "yes_no" },
      { name: "vegetation_left", label: "Vegetation — left bank", options: "yes_no" },
      { name: "vegetation_type_left", label: "Vegetation type — left bank", options: "vegetation_type", optional: true },
      { name: "vegetation_right", label: "Vegetation — right bank", options: "yes_no" },
      { name: "vegetation_type_right", label: "Vegetation type — right bank", options: "vegetation_type", optional: true },
      { name: "invasive_species", label: "Invasive species", options: "yes_no" },
      { name: "invasive_species_which", label: "Which ones?", type: "text", optional: true },
      { name: "vegetation_cuts", label: "Vegetation cuts", help: "Recent cuts on the banks.", options: "yes_no" },
    ],
  },
  {
    key: "section_d",
    title: "Section D — Feedback",
    fields: [
      { name: "overall_assessment", label: "Overall assessment", options: "overall_assessment", showHelpPerOption: "overall_assessment_help" },
      { name: "feelings", label: "How does this place make you feel?", help: "0 = not at all, 5 = very strongly.", type: "feelings" },
    ],
  },
];

const PHOTO_ROLES = [
  { role: "upstream", label: "Upstream", sub: "Looking up the stream" },
  { role: "downstream", label: "Downstream", sub: "Looking down the stream" },
  { role: "context", label: "Surroundings", sub: "Step back, show the banks" },
  { role: "biodiversity", label: "Biodiversity (optional)", sub: "A plant, animal or habitat" },
];

const FIELD_LABEL = {};
SECTIONS.forEach((s) => s.fields.forEach((f) => (FIELD_LABEL[f.name] = f.label)));
FIELD_LABEL.vegetation_type_left = "Vegetation type — left";
FIELD_LABEL.vegetation_type_right = "Vegetation type — right";
FIELD_LABEL.invasive_species_which = "Which invasive species";
FIELD_LABEL.feelings = "Your feelings";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  step: 0,
  options: null,
  sites: [],
  site: { name: "", lat: "", lon: "" },
  photos: {}, // role -> File
  photoPreviews: {}, // role -> object URL
  analysis: null, // AnalysisResult from /api/analyze
  analysisPromise: null,
  answers: { section_a: {}, section_b: {}, section_c: {}, section_d: { feelings: {} } },
  flags: [], // audit trail: every flag shown, with the citizen's decision
  checking: null, // section key while the "Quick check" screen is showing
  reliability: null,
  suggestion: null, // rule-based suggested overall assessment (from /api/check)
  oneHealth: null, // rule-based One Health risks (from /api/check)
  submission: null,
  error: "",
};

const STEPS = ["site", "photos", "section_a", "section_b", "section_c", "section_d", "review", "done"];

const $ = (sel) => document.querySelector(sel);
const app = $("#app");

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
async function boot() {
  const [opts, sites, health] = await Promise.all([
    fetch("/api/form-options").then((r) => r.json()),
    fetch("/api/sites").then((r) => r.json()),
    fetch("/api/health").then((r) => r.json()),
  ]);
  state.options = opts;
  state.sites = sites;
  if (!health.ai_configured) setAiStatus("AI reading is off on this server", "off");
  $("#btn-back").addEventListener("click", back);
  $("#btn-next").addEventListener("click", next);
  render();
}

function setAiStatus(text, cls) {
  const el = $("#ai-status");
  el.textContent = text;
  el.className = "ai-status " + (cls || "");
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function render() {
  const step = STEPS[state.step];
  $("#progress-bar").style.width = `${(state.step / (STEPS.length - 1)) * 100}%`;
  app.innerHTML = "";
  state.error = "";

  if (state.checking) {
    renderCheck(state.checking);
    $("#btn-back").style.visibility = "visible";
    const nextBtn = $("#btn-next");
    nextBtn.textContent = "Continue";
    nextBtn.disabled = pendingFlags(state.checking).length > 0;
    window.scrollTo(0, 0);
    return;
  }
  const renderers = {
    site: renderSite,
    photos: renderPhotos,
    section_a: () => renderSection(SECTIONS[0]),
    section_b: () => renderSection(SECTIONS[1]),
    section_c: () => renderSection(SECTIONS[2]),
    section_d: () => renderSection(SECTIONS[3]),
    review: renderReview,
    done: renderDone,
  };
  renderers[step]();

  $("#btn-back").style.visibility = state.step === 0 || step === "done" ? "hidden" : "visible";
  const nextBtn = $("#btn-next");
  nextBtn.disabled = false;
  nextBtn.textContent = step === "review" ? "Submit" : step === "done" ? "Start a new assessment" : "Next";
  window.scrollTo(0, 0);
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) node.append(c instanceof Node ? c : document.createTextNode(c));
  return node;
}

function heading(title, lead) {
  app.append(el("h1", {}, title));
  if (lead) app.append(el("p", { class: "lead" }, lead));
}

// --- Site ------------------------------------------------------------------
function renderSite() {
  heading("Where are you?", "Pick a site or type a new one.");
  const card = el("div", { class: "card" });

  const select = el("select", { id: "site-select", "aria-label": "Known sites" });
  select.append(el("option", { value: "" }, "— choose a known site —"));
  state.sites.forEach((s, i) => select.append(el("option", { value: i }, s.name)));
  select.addEventListener("change", () => {
    const s = state.sites[select.value];
    if (s) {
      state.site = { ...s };
      nameInput.value = s.name;
      latInput.value = s.lat;
      lonInput.value = s.lon;
    }
  });
  card.append(el("div", { class: "field" }, [el("label", { for: "site-select" }, "Known sites"), select]));

  const nameInput = el("input", { type: "text", id: "site-name", value: state.site.name, placeholder: "e.g. Kallang River at Bishan Park", oninput: (e) => (state.site.name = e.target.value) });
  card.append(el("div", { class: "field" }, [el("label", { for: "site-name" }, "Site name"), nameInput]));

  const latInput = el("input", { type: "number", step: "any", id: "site-lat", value: state.site.lat, placeholder: "1.3620", oninput: (e) => (state.site.lat = e.target.value) });
  const lonInput = el("input", { type: "number", step: "any", id: "site-lon", value: state.site.lon, placeholder: "103.8450", oninput: (e) => (state.site.lon = e.target.value) });
  card.append(
    el("div", { class: "field" }, [
      el("span", { class: "q" }, "Coordinates"),
      el("div", { class: "row" }, [
        el("div", {}, [el("label", { for: "site-lat", class: "help" }, "Latitude"), latInput]),
        el("div", {}, [el("label", { for: "site-lon", class: "help" }, "Longitude"), lonInput]),
      ]),
    ])
  );
  const geoBtn = el("button", { type: "button", class: "btn btn-secondary btn-inline", onclick: () => useMyLocation(latInput, lonInput, geoBtn) }, "Use my location");
  card.append(geoBtn);
  card.append(el("p", { id: "site-error", class: "error" }));
  app.append(card);
}

function useMyLocation(latInput, lonInput, btn) {
  if (!navigator.geolocation) return;
  btn.disabled = true;
  btn.textContent = "Locating…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      state.site.lat = pos.coords.latitude.toFixed(5);
      state.site.lon = pos.coords.longitude.toFixed(5);
      latInput.value = state.site.lat;
      lonInput.value = state.site.lon;
      btn.disabled = false;
      btn.textContent = "Use my location";
    },
    () => {
      btn.disabled = false;
      btn.textContent = "Location unavailable — type it in";
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

// --- Photos ----------------------------------------------------------------
function renderPhotos() {
  heading("Take your photos", "Same photos as the OneAquaHealth app. Our AI will read them while you fill in the form.");
  const grid = el("div", { class: "photo-grid" });
  for (const p of PHOTO_ROLES) {
    const input = el("input", { type: "file", accept: "image/*", capture: "environment", id: `photo-${p.role}` });
    const tile = el("label", { class: "photo-tile" + (state.photos[p.role] ? " filled" : ""), for: `photo-${p.role}` });
    if (state.photoPreviews[p.role]) tile.append(el("img", { src: state.photoPreviews[p.role], alt: "" }));
    tile.append(el("span", { class: "tile-label" }, (state.photos[p.role] ? "✓ " : "📷 ") + p.label));
    tile.append(el("span", { class: "tile-sub" }, p.sub));
    tile.append(input);
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (!file) return;
      state.photos[p.role] = file;
      if (state.photoPreviews[p.role]) URL.revokeObjectURL(state.photoPreviews[p.role]);
      state.photoPreviews[p.role] = URL.createObjectURL(file);
      state.analysis = null; // photos changed, previous reading no longer valid
      state.analysisPromise = null;
      render();
    });
    grid.append(tile);
  }
  app.append(grid);
  app.append(el("p", { class: "help", style: "margin-top:12px" }, "Upstream, downstream and surroundings are needed for the AI reading. Short video is skipped in this prototype."));
  app.append(el("p", { id: "photo-error", class: "error" }));
}

// --- Sections --------------------------------------------------------------
function renderSection(section) {
  heading(section.title, section.lead);
  if (section.key === "section_d") app.append(renderSuggestionCard());
  const card = el("div", { class: "card" });
  const answers = state.answers[section.key];
  for (const f of section.fields) card.append(renderField(f, answers));
  card.append(el("p", { id: "section-error", class: "error" }));
  app.append(card);
}

function renderField(f, answers) {
  const wrap = el("div", { class: "field", "data-field": f.name });
  wrap.append(el("span", { class: "q", id: `q-${f.name}` }, f.label + (f.optional ? " (optional)" : "")));
  if (f.help) wrap.append(el("p", { class: "help" }, f.help));

  if (f.type === "number" || f.type === "text") {
    const input = el("input", { type: f.type, step: f.type === "number" ? "any" : undefined, min: f.type === "number" ? "0" : undefined, "aria-labelledby": `q-${f.name}`, value: answers[f.name] ?? "" });
    input.addEventListener("input", (e) => (answers[f.name] = e.target.value));
    wrap.append(input);
    return wrap;
  }

  if (f.type === "feelings") {
    for (const feeling of ["joy", "serenity", "anger", "fear"]) {
      const row = el("div", { class: "field" });
      row.append(el("span", { class: "q", style: "font-weight:500" }, feeling[0].toUpperCase() + feeling.slice(1)));
      const group = el("div", { class: "options", role: "radiogroup", "aria-label": feeling });
      for (const score of state.options.feeling_scores) {
        const label = score === "not_applicable" ? "N/A" : String(score);
        const chip = el("button", { type: "button", class: "chip", role: "radio", "aria-checked": String(answers.feelings[feeling] === score) }, label);
        chip.addEventListener("click", () => {
          answers.feelings[feeling] = score;
          group.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-checked", "false"));
          chip.setAttribute("aria-checked", "true");
        });
        group.append(chip);
      }
      row.append(group);
      wrap.append(row);
    }
    return wrap;
  }

  // Single or multi choice rendered as big chips.
  const values = state.options[f.options];
  const isAiField = state.options.ai_readable_fields.includes(f.name);
  const group = el("div", { class: "options", role: f.multi ? "group" : "radiogroup", "aria-labelledby": `q-${f.name}` });
  for (const v of values) {
    const selected = f.multi ? (answers[f.name] || []).includes(v) : answers[f.name] === v;
    const chip = el("button", { type: "button", class: "chip", role: f.multi ? "checkbox" : "radio", "aria-checked": String(selected) }, displayOption(v));
    chip.addEventListener("click", () => {
      if (f.multi) {
        let list = answers[f.name] || [];
        if (v === "none") list = list.includes("none") ? [] : ["none"];
        else list = list.includes(v) ? list.filter((x) => x !== v) : [...list.filter((x) => x !== "none"), v];
        answers[f.name] = list;
        group.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-checked", String(list.includes(c.dataset.value))));
      } else {
        answers[f.name] = v;
        group.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-checked", "false"));
        chip.setAttribute("aria-checked", "true");
      }
      if (isAiField) updateTick(wrap, f.name, answers[f.name]);
    });
    chip.dataset.value = v;
    group.append(chip);
  }
  wrap.append(group);
  if (isAiField) updateTick(wrap, f.name, answers[f.name]);

  if (f.showHelpPerOption) {
    const helpMap = state.options[f.showHelpPerOption];
    const list = el("dl", { class: "summary", style: "margin-top:10px" });
    for (const v of values) {
      list.append(el("dt", {}, v));
      list.append(el("dd", {}, helpMap[v]));
    }
    wrap.append(list);
  }
  return wrap;
}

// --- AI agreement ticks -------------------------------------------------------
function aiValueFor(field) {
  const p = state.analysis?.ai_available && state.analysis.predictions[field];
  return p ? p.value : undefined;
}
function sameValue(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    const x = new Set(a || []), y = new Set(b || []);
    return x.size === y.size && [...x].every((v) => y.has(v));
  }
  return a === b;
}
function refreshTicks() {
  // Called when the AI reading arrives while the citizen is already answering.
  const step = STEPS[state.step];
  if (!step.startsWith("section_")) return;
  for (const wrap of app.querySelectorAll("[data-field]")) {
    const field = wrap.dataset.field;
    if (state.options.ai_readable_fields.includes(field)) updateTick(wrap, field, state.answers[step][field]);
  }
}
function updateTick(wrap, field, value) {
  let tick = wrap.querySelector(".tick");
  const ai = aiValueFor(field);
  const show = ai !== undefined && value !== undefined && value !== "" && sameValue(value, ai);
  if (!tick) {
    tick = el("span", { class: "tick", role: "status" }, "✓ Matches what the AI saw");
    wrap.append(tick);
  }
  tick.style.display = show ? "inline-block" : "none";
}

function displayOption(v) {
  return v === "not_sure" ? "Not sure" : v === "yes" ? "Yes" : v === "no" ? "No" : v;
}

// --- Suggested overall assessment (rule-based, citizen's pick is final) --------
function renderSuggestionCard() {
  const sug = state.suggestion;
  const card = el("div", { class: "card suggestion" });
  card.append(el("div", { class: "flag-title" }, "💡 Our suggestion"));
  if (!sug || !sug.value) {
    card.append(el("p", { class: "help" }, (sug && sug.message) || "No suggestion available."));
    return card;
  }
  card.append(el("p", { class: "flag-msg" }, [
    "Based on your answers this stream looks ",
    el("strong", { class: "overall " + sug.value.toLowerCase() }, `"${sug.value}"`),
    sug.reasons.length ? " because:" : ": you reported no pressures.",
  ]));
  if (sug.reasons.length) {
    const ul = el("ul", { class: "reasons" });
    sug.reasons.forEach((r) => ul.append(el("li", {}, r)));
    card.append(ul);
  }
  if (sug.not_sure_fields.length) card.append(el("p", { class: "help" }, `${sug.not_sure_fields.length} answer(s) you were not sure about were left out.`));
  card.append(el("p", { class: "help" }, "This is worked out from your own answers by fixed rules, not by the AI. Your pick below is what counts."));
  return card;
}

// --- One Health risk card ------------------------------------------------------
const RISK_ICON = { high: "🔴", medium: "🟠", low: "🟢", positive: "🌿", unknown: "⚪" };
function renderOneHealthCard(oh) {
  const card = el("div", { class: "card" });
  card.append(el("h2", { style: "margin-top:0" }, "One Health"));
  if (!oh) {
    card.append(el("p", { class: "help" }, "No One Health summary available."));
    return card;
  }
  card.append(el("p", { class: "risk-summary " + oh.risk_level }, `${RISK_ICON[oh.risk_level] || ""} ${oh.summary}`));
  for (const r of oh.risks) {
    const row = el("div", { class: "risk " + r.level });
    row.append(el("div", { class: "ai-field" }, `${RISK_ICON[r.level] || ""} ${r.title}`));
    row.append(el("p", { class: "flag-msg" }, r.message));
    row.append(el("p", { class: "why" }, r.why_it_matters));
    row.append(el("p", { class: "help" }, "Based on: " + r.fields.map((f) => FIELD_LABEL[f] || f).join(", ")));
    card.append(row);
  }
  card.append(el("p", { class: "help" }, "Rule-based, from your final answers. One Health means people, animals and the environment share one health."));
  return card;
}

// --- Quick check (human-in-the-loop) -----------------------------------------
function pendingFlags(sectionKey) {
  return state.flags.filter((f) => f.section === sectionKey && !f.decision);
}

function renderCheck(sectionKey) {
  const flags = state.flags.filter((f) => f.section === sectionKey);
  heading("Quick check", "Our AI looked at your photos. A few answers are worth a second look. You decide.");
  for (const flag of flags) app.append(renderFlagCard(flag, sectionKey));
  app.append(el("p", { class: "help" }, "Your judgement is final. Every decision here is recorded with the submission."));
}

function renderFlagCard(flag, sectionKey) {
  const card = el("div", { class: "card flag " + flag.kind + (flag.decision ? " decided" : "") });
  const icon = flag.kind === "rule" ? "⚠️" : "👁";
  card.append(el("div", { class: "flag-title" }, `${icon} ${FIELD_LABEL[flag.field] || flag.field}`));
  card.append(el("p", { class: "flag-msg" }, flag.message));
  if (flag.ai_confidence != null) card.append(el("p", { class: "help" }, `AI confidence: ${confidenceWords(flag.ai_confidence)}`));

  const actions = el("div", { class: "flag-actions" });
  const decide = (decision, newValue) => {
    flag.decision = decision;
    if (newValue !== undefined) {
      flag.decided_value = newValue;
      state.answers[sectionKey][flag.field] = newValue;
    }
    render();
  };

  if (flag.decision) {
    const text = {
      kept: "You kept your answer",
      changed: `You changed it to "${displayValue(flag.decided_value)}"`,
      accepted: `You used the AI's answer "${displayValue(flag.decided_value)}"`,
      rejected: "You kept \"Not sure\"",
    }[flag.decision];
    card.append(el("p", { class: "flag-decided" }, `✓ ${text}`));
    actions.append(el("button", { type: "button", class: "btn btn-secondary btn-inline", onclick: () => { flag.decision = null; render(); } }, "Undo"));
  } else if (flag.kind === "ai_disagreement") {
    actions.append(el("button", { type: "button", class: "btn btn-secondary", onclick: () => decide("kept") }, "Keep my answer"));
    actions.append(el("button", { type: "button", class: "btn btn-primary", onclick: () => decide("changed", flag.ai_value) }, `Change to "${displayValue(flag.ai_value)}"`));
  } else if (flag.kind === "ai_suggestion") {
    actions.append(el("button", { type: "button", class: "btn btn-secondary", onclick: () => decide("rejected") }, "Keep \"Not sure\""));
    actions.append(el("button", { type: "button", class: "btn btn-primary", onclick: () => decide("accepted", flag.ai_value) }, `Use "${displayValue(flag.ai_value)}"`));
  } else {
    actions.append(el("button", { type: "button", class: "btn btn-secondary", onclick: () => decide("kept") }, "Keep as is"));
    actions.append(el("button", { type: "button", class: "btn btn-primary", onclick: () => { state.checking = null; render(); } }, "Go back and fix"));
  }
  card.append(actions);
  return card;
}

function displayValue(v) {
  return Array.isArray(v) ? v.join(", ") : displayOption(v);
}

async function runChecks(sectionKey) {
  // Wait for the AI reading if it is still in flight, then ask the server for flags.
  if (state.analysisPromise && !state.analysis) {
    const note = $("#section-error");
    if (note) {
      note.innerHTML = "";
      note.append(el("span", { class: "spinner" }), "Reading your photos…");
    }
    $("#btn-next").disabled = true;
    await state.analysisPromise;
    $("#btn-next").disabled = false;
    if (note) note.innerHTML = "";
  }
  const answered = {};
  for (const s of SECTIONS) if (Object.keys(state.answers[s.key]).some((k) => k !== "feelings")) answered[s.key] = sectionPayload(s.key);
  try {
    const r = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_set_id: state.analysis?.photo_set_id || null, answers: answered, flags: state.flags }),
    });
    if (!r.ok) throw new Error(`Server error ${r.status}`);
    const body = await r.json();
    state.flags = body.flags;
    state.reliability = body.reliability;
    state.suggestion = body.suggested_overall;
    state.oneHealth = body.one_health;
  } catch (e) {
    // The check is a helper, never a blocker: carry on without it.
    console.warn("check failed", e);
  }
  return pendingFlags(sectionKey).length > 0;
}

function sectionPayload(key) {
  return buildAnswers()[key];
}

// --- Review ----------------------------------------------------------------
function renderReview() {
  heading("Check and submit", "Here is what you entered, and what our AI saw in your photos.");

  const aiCard = el("div", { class: "card", id: "ai-card" });
  aiCard.append(el("h2", { style: "margin-top:0" }, "What the AI saw"));
  app.append(aiCard);
  fillAiCard(aiCard);

  const scoreCard = el("div", { class: "card", id: "score-card" });
  app.append(scoreCard);
  const ohSlot = el("div", { id: "onehealth-slot" });
  app.append(ohSlot);
  fillScoreCard(scoreCard).then(() => ohSlot.append(renderOneHealthCard(state.oneHealth)));

  const card = el("div", { class: "card" });
  card.append(el("h2", { style: "margin-top:0" }, "Your answers"));
  const dl = el("dl", { class: "summary" });
  dl.append(el("dt", {}, "Site"), el("dd", {}, `${state.site.name} (${state.site.lat}, ${state.site.lon})`));
  for (const s of SECTIONS) {
    for (const f of s.fields) {
      const v = state.answers[s.key][f.name];
      if (f.type === "feelings") {
        dl.append(el("dt", {}, f.label), el("dd", {}, Object.entries(v).map(([k, x]) => `${k}: ${x === "not_applicable" ? "N/A" : x}`).join(", ") || "—"));
      } else {
        dl.append(el("dt", {}, f.label), el("dd", {}, Array.isArray(v) ? v.join(", ") || "—" : v === undefined || v === "" ? "—" : displayOption(v)));
      }
    }
  }
  card.append(dl);
  card.append(el("p", { id: "submit-error", class: "error" }));
  app.append(card);
}

async function fillScoreCard(card) {
  card.append(el("h2", { style: "margin-top:0" }, "Reliability"));
  await runChecks("review");
  const r = state.reliability;
  if (!r) {
    card.append(el("p", { class: "help" }, "Could not compute a score right now."));
    return;
  }
  card.append(renderScore(r));
  const decided = state.flags.filter((f) => f.decision);
  const open = state.flags.filter((f) => !f.decision);
  const trail = el("div", { class: "trail" });
  trail.append(el("h2", {}, "What we checked"));
  if (state.flags.length === 0) trail.append(el("p", { class: "help" }, "No disagreements or inconsistencies were found."));
  for (const f of [...open, ...decided]) trail.append(renderTrailRow(f));
  card.append(trail);
}

function renderScore(r) {
  const wrap = el("div", { class: "score" });
  const cls = r.score >= 75 ? "good" : r.score >= 50 ? "mid" : "low";
  wrap.append(el("div", { class: "score-num " + cls }, `${r.score}`), el("div", { class: "score-of" }, "/ 100"));
  const list = el("ul", { class: "score-parts" });
  for (const c of r.components) list.append(el("li", {}, `${c.name}: ${c.points} / ${c.max_points} — ${c.note}`));
  if (!r.ai_available) list.append(el("li", {}, "AI reading was not available, so the score is based on photos and consistency only."));
  wrap.append(list);
  return wrap;
}

function renderTrailRow(f) {
  const row = el("div", { class: "trail-row" });
  const what = f.kind === "rule" ? "Consistency check" : f.kind === "ai_suggestion" ? "AI suggestion" : "AI disagreed";
  const outcome = {
    kept: "kept your answer",
    changed: `changed to "${displayValue(f.decided_value)}"`,
    accepted: `used "${displayValue(f.decided_value)}"`,
    rejected: "kept \"Not sure\"",
  }[f.decision] || "not answered yet";
  row.append(el("div", { class: "ai-field" }, `${FIELD_LABEL[f.field] || f.field} · ${what}`));
  row.append(el("div", { class: "help" }, f.message));
  row.append(el("div", { class: f.decision ? "trail-ok" : "trail-open" }, (f.decision ? "✓ You " : "• ") + outcome));
  return row;
}

function confidenceWords(c) {
  if (c >= 0.8) return "very sure";
  if (c >= 0.6) return "fairly sure";
  if (c >= 0.4) return "unsure";
  return "just a guess";
}

async function fillAiCard(card) {
  const body = el("div");
  card.append(body);
  if (state.analysisPromise && !state.analysis) {
    body.append(el("p", {}, [el("span", { class: "spinner" }), "Reading your photos…"]));
    await state.analysisPromise;
    body.innerHTML = "";
  }
  const a = state.analysis;
  if (!a) {
    body.append(el("p", { class: "notice" }, "No photos were uploaded, so there is no AI reading for this assessment."));
    return;
  }
  if (!a.ai_available) {
    body.append(el("p", { class: "notice" }, a.error || "The AI could not read these photos."));
    return;
  }
  body.append(el("p", { class: "help" }, `Photo quality: ${a.predictions.photo_quality}`));
  for (const name of state.options.ai_readable_fields) {
    const p = a.predictions[name];
    const value = Array.isArray(p.value) ? p.value.join(", ") : displayOption(p.value);
    const row = el("div", { class: "ai-row" });
    row.append(el("div", { class: "ai-field" }, [FIELD_LABEL[name] || name, el("span", { class: "badge" + (p.confidence < 0.6 ? " low" : "") }, confidenceWords(p.confidence))]));
    row.append(el("div", { class: "ai-value" }, value));
    row.append(el("div", { class: "ai-evidence" }, p.evidence));
    body.append(row);
  }
  body.append(el("p", { class: "help", style: "margin-top:10px" }, `Not judged from photos (you decide): ${a.human_only.map((f) => FIELD_LABEL[f] || f).join(", ")}.`));
  body.append(el("p", { class: "help" }, `Model: ${a.model}. This is a second opinion, not a verdict — your answers are what gets submitted.`));
}

// --- Done ------------------------------------------------------------------
function renderDone() {
  app.append(el("div", { class: "done-big" }, "✅"));
  heading("Thank you!", "Your assessment has been saved.");
  const card = el("div", { class: "card" });
  card.append(el("p", {}, ["Submission ID: ", el("code", {}, state.submission.id)]));
  if (state.submission.reliability) card.append(renderScore(state.submission.reliability));
  if (state.submission.one_health) {
    const oh = state.submission.one_health;
    card.append(el("p", { class: "risk-summary " + oh.risk_level, style: "margin-top:12px" }, `${RISK_ICON[oh.risk_level] || ""} One Health: ${oh.summary}`));
  }
  card.append(renderFhirActions(state.submission.id));
  card.append(el("p", {}, el("a", { href: "submissions.html", class: "link" }, "See all submissions and the map →")));
  const n = state.submission.flags.length;
  card.append(el("p", { class: "help" }, n ? `${n} check(s) were raised and your decisions were recorded with the submission.` : "No checks were raised."));
  app.append(card);
}

// --- FHIR export (Track 7) ------------------------------------------------------
function renderFhirActions(submissionId) {
  const wrap = el("div", { class: "fhir" });
  wrap.append(el("h2", {}, "Share as a health standard"));
  wrap.append(el("p", { class: "help" }, "HL7 FHIR R4 is the format health information systems exchange. Export this assessment as a FHIR Bundle, or send it to a public test server."));
  const row = el("div", { class: "flag-actions" });
  const status = el("p", { class: "help fhir-status", "aria-live": "polite" });
  const dl = el("a", { class: "btn btn-secondary btn-link", href: `/api/submissions/${submissionId}/fhir`, download: `streamcheck-${submissionId}.fhir.json` }, "Export FHIR (download JSON)");
  const send = el("button", { type: "button", class: "btn btn-primary" }, "Send to FHIR sandbox");
  send.addEventListener("click", async () => {
    send.disabled = true;
    status.innerHTML = "";
    status.append(el("span", { class: "spinner" }), "Sending to the FHIR test server…");
    try {
      const r = await fetch(`/api/submissions/${submissionId}/fhir/send`, { method: "POST" });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Server error ${r.status}`);
      status.textContent = "";
      status.append(el("strong", {}, `Sent to ${body.server}. `), `The server created ${body.created.length} resources: `, el("code", {}, body.created.slice(0, 3).join(", ") + (body.created.length > 3 ? ", …" : "")));
    } catch (e) {
      status.textContent = `Could not send: ${e.message}`;
    }
    send.disabled = false;
  });
  row.append(dl, send);
  wrap.append(row, status);
  return wrap;
}

// ---------------------------------------------------------------------------
// Navigation and validation
// ---------------------------------------------------------------------------
function back() {
  if (state.checking) {
    state.checking = null;
    render();
    return;
  }
  if (state.step > 0) {
    state.step -= 1;
    render();
  }
}

async function next() {
  const step = STEPS[state.step];
  if (step === "site" && !validateSite()) return;
  if (step === "photos") startAnalysis();
  if (state.checking) {
    state.checking = null;
  } else if (step.startsWith("section_")) {
    if (!validateSection(SECTIONS.find((s) => s.key === step))) return;
    if (await runChecks(step)) {
      state.checking = step;
      render();
      return;
    }
  }
  if (step === "review") return submit();
  if (step === "done") return resetAll();
  state.step += 1;
  render();
}

function validateSite() {
  const err = $("#site-error");
  const lat = parseFloat(state.site.lat), lon = parseFloat(state.site.lon);
  if (!state.site.name.trim()) return (err.textContent = "Please give the site a name."), false;
  if (Number.isNaN(lat) || Number.isNaN(lon)) return (err.textContent = "Please enter the coordinates (or use your location)."), false;
  return true;
}

function validateSection(section) {
  const answers = state.answers[section.key];
  const err = $("#section-error");
  for (const f of section.fields) {
    if (f.optional || f.type === "feelings") continue;
    const v = answers[f.name];
    if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) {
      err.textContent = `Please answer "${f.label}" (choose "Not sure" if you cannot tell).`;
      app.querySelector(`[data-field="${f.name}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      return false;
    }
  }
  return true;
}

function startAnalysis() {
  if (state.analysisPromise || Object.keys(state.photos).length === 0) return;
  const form = new FormData();
  for (const [role, file] of Object.entries(state.photos)) form.append(role, file, file.name);
  setAiStatus("AI is reading your photos…", "working");
  state.analysisPromise = fetch("/api/analyze", { method: "POST", body: form })
    .then((r) => r.json())
    .then((res) => {
      state.analysis = res;
      if (res.ai_available) setAiStatus("AI has read your photos", "done");
      else setAiStatus("AI reading unavailable", "off");
      refreshTicks();
    })
    .catch(() => {
      state.analysis = { ai_available: false, error: "Could not reach the server to read the photos." };
      setAiStatus("AI reading unavailable", "off");
    });
}

function buildAnswers() {
  const a = state.answers;
  const num = (v) => (v === "" || v === undefined ? null : Number(v));
  return {
    site: { name: state.site.name.trim(), lat: parseFloat(state.site.lat), lon: parseFloat(state.site.lon) },
    section_a: { ...a.section_a, habitats: a.section_a.habitats || [], natural_debris: a.section_a.natural_debris || [] },
    section_b: { ...a.section_b, water_height_m: num(a.section_b.water_height_m) },
    section_c: { ...a.section_c, vegetation_type_left: a.section_c.vegetation_type_left || null, vegetation_type_right: a.section_c.vegetation_type_right || null, invasive_species_which: a.section_c.invasive_species_which || "" },
    section_d: { overall_assessment: a.section_d.overall_assessment, feelings: { joy: "not_applicable", serenity: "not_applicable", anger: "not_applicable", fear: "not_applicable", ...a.section_d.feelings } },
  };
}

// What the citizen entered before any AI-prompted change (for the audit trail).
function originalAnswers() {
  const raw = buildAnswers();
  for (const f of state.flags) {
    if ((f.decision === "changed" || f.decision === "accepted") && f.section in raw) raw[f.section][f.field] = f.citizen_value;
  }
  return raw;
}

async function submit() {
  const btn = $("#btn-next");
  btn.disabled = true;
  btn.textContent = "Saving…";
  if (state.analysisPromise) await state.analysisPromise;
  try {
    const r = await fetch("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        photo_set_id: state.analysis?.photo_set_id || null,
        answers: originalAnswers(),
        final_answers: buildAnswers(),
        flags: state.flags,
      }),
    });
    if (!r.ok) throw new Error((await r.json()).detail?.[0]?.msg || `Server error ${r.status}`);
    state.submission = await r.json();
    state.step += 1;
    render();
  } catch (e) {
    $("#submit-error").textContent = `Could not save: ${e.message}`;
    btn.disabled = false;
    btn.textContent = "Submit";
  }
}

function resetAll() {
  Object.values(state.photoPreviews).forEach((u) => URL.revokeObjectURL(u));
  Object.assign(state, { step: 0, site: { name: "", lat: "", lon: "" }, photos: {}, photoPreviews: {}, analysis: null, analysisPromise: null, answers: { section_a: {}, section_b: {}, section_c: {}, section_d: { feelings: {} } }, flags: [], checking: null, reliability: null, suggestion: null, oneHealth: null, submission: null });
  setAiStatus("", "");
  render();
}

boot();
