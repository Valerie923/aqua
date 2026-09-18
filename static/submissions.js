/* StreamCheck — "My submissions": list of past assessments + a map of sites.
 * Marker colour = rule-based suggested overall assessment. */

const COLOURS = { Good: "#15803d", Moderate: "#b45309", Poor: "#b91c1c" };

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) node.append(c instanceof Node ? c : document.createTextNode(c));
  return node;
}

function scoreClass(s) {
  return s == null ? "" : s >= 75 ? "good" : s >= 50 ? "mid" : "low";
}

function fmtDate(iso) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function renderList(subs, map, markers) {
  const list = document.getElementById("list");
  list.innerHTML = "";
  if (subs.length === 0) {
    list.append(el("p", { class: "help" }, "No submissions yet. Start a new assessment to see it here."));
    return;
  }
  for (const s of subs) {
    const site = s.final_answers?.site || s.answers.site;
    const overall = (s.final_answers || s.answers).section_d.overall_assessment;
    const suggested = s.suggested_overall?.value;
    const risk = s.one_health?.risk_level || "unknown";
    const card = el("div", { class: "card", role: "button", tabindex: "0" });
    card.append(el("div", { class: "sub-site" }, site.name));
    card.append(el("div", { class: "sub-score " + scoreClass(s.reliability_score) }, s.reliability_score == null ? "—" : String(s.reliability_score)));
    const meta = el("div", { class: "sub-meta" });
    meta.append(el("span", { class: "pill " + risk }, `One Health: ${risk}`));
    meta.append(el("span", { class: "pill" }, `You: ${overall}`));
    meta.append(el("span", { class: "pill" }, `Suggested: ${suggested || "n/a"}`));
    meta.append(el("div", {}, `${fmtDate(s.created_at)} · reliability ${s.reliability_score ?? "n/a"}/100`));
    card.append(meta);
    const focus = () => {
      if (map && markers[s.id]) {
        map.setView([site.lat, site.lon], 15);
        markers[s.id].openPopup();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    };
    card.addEventListener("click", focus);
    card.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); focus(); } });
    list.append(card);
  }
}

function renderMap(subs) {
  const mapEl = document.getElementById("map");
  if (typeof L === "undefined") {
    mapEl.innerHTML = "";
    mapEl.append(el("p", { class: "map-fallback" }, "Map could not load (no connection to the map tiles). The list below still works."));
    return { map: null, markers: {} };
  }
  const map = L.map("map", { scrollWheelZoom: false }).setView([1.3521, 103.8198], 11); // Singapore
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  const markers = {};
  const points = [];
  for (const s of subs) {
    const site = s.final_answers?.site || s.answers.site;
    const suggested = s.suggested_overall?.value;
    const m = L.circleMarker([site.lat, site.lon], {
      radius: 10, color: "#fff", weight: 2, fillColor: COLOURS[suggested] || "#9ca3af", fillOpacity: 0.95,
    }).addTo(map);
    m.bindPopup(
      `<strong>${site.name}</strong><br>${fmtDate(s.created_at)}<br>` +
      `Suggested: ${suggested || "n/a"} · You: ${(s.final_answers || s.answers).section_d.overall_assessment}<br>` +
      `Reliability ${s.reliability_score ?? "n/a"}/100 · One Health: ${s.one_health?.risk_level || "unknown"}`
    );
    markers[s.id] = m;
    points.push([site.lat, site.lon]);
  }
  if (points.length) map.fitBounds(points, { padding: [30, 30], maxZoom: 14 });
  return { map, markers };
}

async function boot() {
  let subs = [];
  try {
    subs = await fetch("/api/submissions").then((r) => r.json());
  } catch {
    document.getElementById("list").textContent = "Could not load submissions.";
    return;
  }
  const { map, markers } = renderMap(subs);
  renderList(subs, map, markers);
}

boot();
