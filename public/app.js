/* Food Hunt UI — renders one trip "view" JSON (from /api/trips/<slug>, the agent stream,
   or inlined by the offline export). No build step, no framework. */
(() => {
  "use strict";
  const IMG = window.__IMG_BASE__ || "";
  const OFFLINE = !!window.__TRIP__ || location.protocol === "file:";
  const DAY_COLORS = ["--d1", "--d2", "--d3", "--d4"].map(v => getComputedStyle(document.documentElement).getPropertyValue(v).trim());
  const KIND = { breakfast: "🌅", meal: "🍛", hotpot: "🍲", snack: "🍣", dessert: "🍧", mall: "🛍️", night_market: "🌙" };
  const TOOL_ICON = { find_place: "📍", geocode: "🧭", rednote_search: "📕", parse_rednote_share: "📕", verify_place: "✅",
    crowd_forecast: "👥", walking_directions: "🚶", plan_trip_spec: "🗺️", food_nearby: "🍜", resolve_google_share_link: "🔗",
    web_search: "🔎", web_fetch: "📄" };

  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dayColor = i => DAY_COLORS[i % DAY_COLORS.length];
  const fmtDate = (iso, wd) => { const d = new Date(iso + "T00:00:00"); return `${wd} ${d.getDate()} ${d.toLocaleString("en", { month: "short" })}`; };
  const km = m => m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${m} m`;
  const level = v => v === 0 ? "Closed" : v < 35 ? "Quiet" : v < 70 ? "Medium" : "Busy";
  const hourLabel = h => h === 0 ? "12am" : h < 12 ? `${h}am` : h === 12 ? "12pm" : `${h - 12}pm`;

  let view = null, dayIdx = 0, map = null, layer = null, markers = {}, health = {};

  /* ---------------- rendering ---------------- */
  function render(v) {
    view = v;
    dayIdx = Math.min(dayIdx, v.days.length - 1);
    document.title = `${v.trip.title} · Food Hunt`;
    const slugNow = new URLSearchParams(location.search).get("trip") || $("#tripPicker").value || "hatyai";
    $("#albumLink").href = `album.html?trip=${encodeURIComponent(slugNow)}`;
    $("#albumLink").hidden = !!window.__TRIP__;
    const stops = v.days.flatMap(d => d.stops);
    const walk = v.days.reduce((a, d) => a + (d.walk_m || 0), 0);
    const nights = v.days.length;
    $("#content").innerHTML = `
      <p class="kicker">${nights}-day food route · ${esc(v.trip.city)}</p>
      <h1>${esc(v.trip.title)}</h1>
      <p class="hero-sub">Starts at <b>${esc(v.trip.start.name)}</b>. Each stop is timed to be open, before the rush, and a short walk from the last.</p>
      <div class="stats">
        <div class="stat"><b>${stops.length}</b><span>stops</span></div>
        <div class="stat"><b>${nights}</b><span>days</span></div>
        <div class="stat"><b>${km(walk)}</b><span>walking</span></div>
        <div class="stat"><b>${v.no_location.length + v.leftover.length}</b><span>to check</span></div>
      </div>
      <div class="tabs" role="tablist" aria-label="Days">
        ${v.days.map((d, i) => `<button class="tab" role="tab" data-day="${i}" aria-selected="${i === dayIdx}">
          <span class="dot" style="background:${dayColor(i)}"></span>Day ${i + 1} · ${esc(fmtDate(d.date, d.weekday))}</button>`).join("")}
        <button class="tab" role="tab" data-day="-1" aria-selected="${dayIdx === -1}">All days</button>
      </div>
      <div id="days"></div>
      ${extras(v)}
      <p class="footer">Places: ${esc(v.trip.sources.places)} · Crowd: ${v.trip.sources.crowd === "estimate" ? "estimated from meal-time patterns (not live)" : "BestTime live data"}
        · Routes: OpenStreetMap/OSRM · Updated ${esc(v.trip.generated_at?.slice(0, 10) || "")}</p>`;
    $("#content").querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => selectDay(+t.dataset.day)));
    renderDays();
  }

  function selectDay(i) {
    dayIdx = i;
    document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-selected", String(+t.dataset.day === i)));
    renderDays();
    const tabs = $(".tabs"); window.scrollTo({ top: tabs.offsetTop - 60, behavior: "smooth" });
  }

  function renderDays() {
    const list = dayIdx === -1 ? view.days.map((d, i) => [d, i]) : [[view.days[dayIdx], dayIdx]];
    $("#days").innerHTML = list.map(([d, i]) => dayHTML(d, i)).join("");
    wire();
    drawMap();
  }

  function dayHTML(d, i) {
    const color = dayColor(i);
    return `<section class="day" style="--day:${color}">
      <div class="day-head">
        <div><h2>Day ${i + 1} · ${esc(fmtDate(d.date, d.weekday))}</h2>
        <p>${d.stops.length} stops · ${km(d.walk_m || 0)} on foot</p></div>
        <a class="btn" href="${esc(d.map_link)}" target="_blank" rel="noopener">🧭 Navigate day</a>
      </div>
      <ol class="timeline">${d.stops.map((s, j) => legHTML(s, i, j) + stopHTML(s, i, j)).join("")}</ol>
    </section>`;
  }

  function legHTML(s, i, j) {
    const L = s.leg, icon = L.mode === "walking" ? "🚶" : "🚕", verb = L.mode === "walking" ? "Walk" : "Grab";
    const from = j === 0 ? "from start" : "";
    return `<li class="leg"><div class="rail"></div><div class="leg-body">
      <button class="leg-chip" type="button" aria-expanded="false" aria-controls="steps-${i}-${j}">${icon} ${verb} ${L.minutes} min${L.meters ? ` · ${km(L.meters)}` : ""} ${from} <span aria-hidden="true">▾</span></button>
      <ol class="steps" id="steps-${i}-${j}" hidden>${(L.steps.length ? L.steps : ["Open the Google Maps link for directions."]).map(x => `<li>${esc(x)}</li>`).join("")}</ol>
    </div></li>`;
  }

  function stopHTML(s, i, j) {
    const p = s.place, key = `${i}-${j}`;
    const imgs = (p.images || []).map(src => `<img src="${esc(src.startsWith("http") ? src : IMG + src)}" alt="${esc(p.display)}" loading="lazy">`).join("");
    const badges = [
      p.must && `<span class="badge must">★ Must-eat</span>`,
      p.sells_out && `<span class="badge warn">⏳ Sells out — go early</span>`,
      (!s.hours_known || p.confidence === "low") && `<span class="badge crit">⚠ Hours not verified</span>`,
      p.approx && `<span class="badge">📍 Pin is street-level</span>`,
      s.wait_reason === "opening" && s.wait_min > 10 && `<span class="badge">🔓 Opens ${esc(s.arrive)} — be on time</span>`,
    ].filter(Boolean).join("");
    const prev = j === 0 ? view.trip.start : view.days[i].stops[j - 1].place;
    const dir = `https://www.google.com/maps/dir/?api=1&origin=${prev.lat},${prev.lng}&destination=${p.lat},${p.lng}&travelmode=${s.leg.mode}`;
    return `<li class="stop" style="--day:${dayColor(i)}">
      <div class="time"><b>${esc(s.arrive)}</b><span>to ${esc(s.leave)}</span></div>
      <article class="card" id="stop-${key}" data-key="${key}" tabindex="-1">
        ${imgs ? `<div class="photos ${p.images.length === 1 ? "single" : ""}">${imgs}</div>` : ""}
        <div class="card-body">
          <div class="card-top"><span class="num">${j + 1}</span><span class="slot">${KIND[p.kind] || "🍽️"} ${esc(s.slot || "")}</span></div>
          <h3>${esc(p.display)}</h3>
          <div class="meta">
            ${p.rating ? `<span class="star">★ ${p.rating}${p.reviews ? ` <span class="muted">(${Number(p.reviews).toLocaleString()})</span>` : ""}</span>` : ""}
            <span>🕒 ${esc(s.hours_today)}</span>
          </div>
          ${badges ? `<div class="badges">${badges}</div>` : ""}
          ${p.order ? `<p class="order">🍴 <b>Order:</b> ${esc(p.order)}</p>` : ""}
          ${p.tip ? `<p class="tip">💡 ${esc(p.tip)}</p>` : ""}
          ${crowdHTML(s, key)}
          <div class="actions">
            <a class="btn" href="${esc(dir)}" target="_blank" rel="noopener">🧭 Directions</a>
            <a class="btn" href="${esc(p.maps_url || "#")}" target="_blank" rel="noopener">Google Maps</a>
          </div>
        </div>
      </article>
    </li>`;
  }

  /* Crowd chart: one series (busy level 0–100 by hour), so no legend — the heading names it.
     Bars anchored to the baseline, 4px-rounded tops, 2px gaps; your arrival hour is the dark bar. */
  function crowdHTML(s, key) {
    const c = s.crowd, by = c.by_hour || [], H0 = 6, H1 = 23, n = H1 - H0 + 1;
    const W = 360, top = 12, base = 48, slot = W / n, bw = slot - 2;
    const you = parseInt(s.arrive, 10);
    let bars = "", hits = "";
    for (let h = H0; h <= H1; h++) {
      const v = by[h] || 0, x = (h - H0) * slot + 1;
      const hgt = v === 0 ? 3 : Math.max(4, (v / 100) * (base - top));
      const y = base - hgt, r = Math.min(4, hgt / 2);
      const cls = v === 0 ? "closed" : h === you ? "you" : "";
      bars += `<path class="bar ${cls}" data-h="${h}" d="M${x},${base}V${y + r}Q${x},${y} ${x + r},${y}H${x + bw - r}Q${x + bw},${y} ${x + bw},${y + r}V${base}Z"/>`;
      hits += `<rect class="hit" x="${x - 1}" y="0" width="${slot}" height="${base}" data-h="${h}" data-v="${v}"/>`;
      if (h === you) bars += `<text class="you-label" x="${x + bw / 2}" y="${y - 3}" text-anchor="middle">you</text>`;
    }
    const ticks = [6, 12, 18, 23].map(h => `<text class="axis" x="${(h - H0) * slot + slot / 2}" y="62" text-anchor="middle">${hourLabel(h)}</text>`).join("");
    const rows = by.map((v, h) => [h, v]).filter(([h]) => h >= H0 && h <= H1)
      .map(([h, v]) => `<tr><td>${hourLabel(h)}</td><td>${level(v)}</td><td>${v}</td></tr>`).join("");
    const label = `How busy by hour. You arrive at ${s.arrive}: ${level(s.crowd_now).toLowerCase()}. Quietest ${c.best}, busiest ${c.peak}.`;
    return `<div class="crowd">
      <div class="crowd-head"><b>How busy · ${c.source === "estimate" ? "estimated" : "live"}</b>
        <span>At ${esc(s.arrive)}: <b>${level(s.crowd_now)}</b></span></div>
      <svg viewBox="0 0 ${W} 64" role="img" aria-label="${esc(label)}" data-key="${key}">${hits}${bars}${ticks}</svg>
      <div class="crowd-foot"><span>Quietest ${esc(c.best || "–")}</span><span>Busiest ${esc(c.peak || "–")}</span></div>
      <details class="small muted"><summary>Hourly table</summary><table><thead><tr><th>Hour</th><th>Level</th><th>0–100</th></tr></thead><tbody>${rows}</tbody></table></details>
    </div>`;
  }

  function extras(v) {
    const block = (title, note, items) => !items.length ? "" : `<div class="section"><h2>${title}</h2><p class="muted small">${note}</p>
      ${items.map(p => `<div class="mini"><span><b>${esc(p.display)}</b>${p.hours ? `<br><span class="muted small">${esc(p.hours)}</span>` : ""}</span>
        <a class="btn" href="${esc(p.maps_url || "#")}" target="_blank" rel="noopener">Open</a></div>`).join("")}</div>`;
    return block("📍 Need exact location", "On your list, but no map source has a reliable pin yet. Tap to check — add a Google Maps key and they get routed automatically.", v.no_location)
      + block("Didn't fit", "Closed on these days or no free meal slot.", v.leftover);
  }

  /* ---------------- interactions ---------------- */
  function wire() {
    document.querySelectorAll(".leg-chip").forEach(b => b.addEventListener("click", () => {
      const open = b.getAttribute("aria-expanded") === "true";
      b.setAttribute("aria-expanded", String(!open));
      document.getElementById(b.getAttribute("aria-controls")).hidden = open;
    }));
    document.querySelectorAll(".card").forEach(c => {
      c.addEventListener("mouseenter", () => setActive(c.dataset.key, false));
      c.addEventListener("focusin", () => setActive(c.dataset.key, false));
    });
    const tip = $("#tooltip");
    document.querySelectorAll(".crowd .hit").forEach(r => {
      r.addEventListener("mousemove", e => {
        const h = +r.dataset.h, v = +r.dataset.v;
        tip.textContent = `${hourLabel(h)} · ${level(v)}${v ? ` (${v}/100)` : ""}`;
        tip.hidden = false; tip.style.left = `${e.clientX + 12}px`; tip.style.top = `${e.clientY - 30}px`;
        r.parentNode.querySelector(`.bar[data-h="${h}"]`)?.classList.add("hover");
      });
      r.addEventListener("mouseleave", () => { tip.hidden = true; r.parentNode.querySelectorAll(".bar.hover").forEach(b => b.classList.remove("hover")); });
    });
  }

  function setActive(key, scroll) {
    document.querySelectorAll(".card.active").forEach(c => c.classList.remove("active"));
    Object.values(markers).forEach(m => m.getElement()?.querySelector(".pin")?.classList.remove("active"));
    const card = document.getElementById(`stop-${key}`);
    card?.classList.add("active");
    markers[key]?.getElement()?.querySelector(".pin")?.classList.add("active");
    if (scroll && card) card.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  /* ---------------- map ---------------- */
  function drawMap() {
    if (!window.L) return;
    if (!map) {
      map = L.map("map", { zoomControl: true, scrollWheelZoom: true });
      // Standard OSM tiles: free, no key, attribution required (fine for a personal/small site;
      // for heavy traffic switch to a paid tile provider per OSM's tile usage policy).
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);
    }
    layer?.remove(); layer = L.layerGroup().addTo(map); markers = {};
    const s0 = view.trip.start, pts = [[s0.lat, s0.lng]];
    L.marker([s0.lat, s0.lng], { icon: L.divIcon({ className: "", html: '<div class="pin-start" title="Start">🏨</div>', iconSize: [34, 34] }), zIndexOffset: 1000 })
      .bindTooltip(esc(s0.name)).addTo(layer);
    view.days.forEach((d, i) => {
      const on = dayIdx === -1 || dayIdx === i, col = dayColor(i);
      const line = d.stops.flatMap(s => s.leg.geometry || []);
      if (line.length) L.polyline(line, { color: col, weight: on ? 4 : 2, opacity: on ? .85 : .2, dashArray: on ? null : "4 6" }).addTo(layer);
      d.stops.forEach((s, j) => {
        const key = `${i}-${j}`, p = s.place;
        const m = L.marker([p.lat, p.lng], {
          icon: L.divIcon({ className: "", html: `<div class="pin ${on ? "" : "dim"}" style="--c:${col}">${j + 1}</div>`, iconSize: [30, 30] }),
          zIndexOffset: on ? 500 : 0, keyboard: true, title: p.display,
        }).bindTooltip(`<b>${esc(p.display)}</b><br>Day ${i + 1} · ${esc(s.arrive)}`).addTo(layer);
        m.on("click", () => { if (!on) selectDay(i); setTimeout(() => setActive(key, true), on ? 0 : 60); });
        markers[key] = m;
        if (on) pts.push([p.lat, p.lng]);
      });
    });
    map.fitBounds(pts, { padding: [40, 40], maxZoom: 16 });
    setTimeout(() => map.invalidateSize(), 50);
  }

  $("#mapToggle").addEventListener("click", e => {
    const w = $(".mapwrap"); w.classList.toggle("expanded");
    e.currentTarget.setAttribute("aria-pressed", String(w.classList.contains("expanded")));
    e.currentTarget.textContent = w.classList.contains("expanded") ? "List" : "Map";
    setTimeout(() => map?.invalidateSize(), 300);
  });

  /* ---------------- agent drawer ---------------- */
  const drawer = $("#drawer"), backdrop = $("#drawerBackdrop");
  const openDrawer = o => { drawer.classList.toggle("open", o); drawer.setAttribute("aria-hidden", String(!o)); backdrop.hidden = !o; if (o) $("#prompt").focus(); };
  $("#openAgent").addEventListener("click", () => openDrawer(true));
  $("#closeAgent").addEventListener("click", () => openDrawer(false));
  backdrop.addEventListener("click", () => openDrawer(false));
  document.addEventListener("keydown", e => { if (e.key === "Escape") openDrawer(false); });
  document.querySelectorAll("#examples .chip").forEach(c => c.addEventListener("click", () => { $("#prompt").value = c.textContent; }));
  $("#accessCode").value = localStorage.getItem("fh_code") || "";

  function log(cls, html) { const li = document.createElement("li"); li.className = cls; li.innerHTML = html; $("#agentLog").appendChild(li); li.scrollIntoView({ block: "nearest" }); return li; }

  $("#agentForm").addEventListener("submit", async e => {
    e.preventDefault();
    const btn = $("#runAgent"), code = $("#accessCode").value.trim();
    if (code) localStorage.setItem("fh_code", code);
    btn.disabled = true; btn.textContent = "Researching…"; $("#agentLog").innerHTML = "";
    try {
      const res = await fetch("api/agent", { method: "POST",
        headers: { "Content-Type": "application/json", ...(code ? { Authorization: `Bearer ${code}` } : {}) },
        body: JSON.stringify({ prompt: $("#prompt").value }) });
      if (res.status === 401) { $("#codeRow").hidden = false; log("err", "This site needs an access code."); return; }
      if (!res.ok || !res.body) { log("err", `Server error ${res.status}`); return; }
      const reader = res.body.getReader(), dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        let i; while ((i = buf.indexOf("\n\n")) >= 0) {
          const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
          if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
        }
      }
    } catch (err) { log("err", esc(err.message)); }
    finally { btn.disabled = false; btn.textContent = "Plan it"; }
  });

  function onEvent(ev) {
    if (ev.type === "status") log("", `⏳ ${esc(ev.text)}`);
    else if (ev.type === "search") log("", `${TOOL_ICON[ev.tool] || "🔎"} <span>${ev.tool === "web_fetch" ? "Reading" : "Searching"} <code>${esc(ev.query)}</code></span>`);
    else if (ev.type === "tool_start") log("", `${TOOL_ICON[ev.tool] || "🛠"} <span>${esc(ev.tool)} <code>${esc(ev.input)}</code></span>`);
    else if (ev.type === "tool_error") log("err", `⚠ ${esc(ev.tool)}: ${esc(ev.error)}`);
    else if (ev.type === "text") log("text", esc(ev.text));
    else if (ev.type === "trip" && ev.view) {
      log("ok", `🗺️ Route ready — <b>${esc(ev.view.trip.title)}</b>`);
      dayIdx = 0; render(ev.view);
      history.replaceState(null, "", `?trip=${encodeURIComponent(ev.slug)}`);
      addPick(ev.slug, ev.view.trip.title, true);
    } else if (ev.type === "error") log("err", `⚠ ${esc(ev.error)}`);
    else if (ev.type === "done") log("ok", `✓ Done${ev.usage?.output ? ` · ${ev.usage.output.toLocaleString()} output tokens` : ""}`);
  }

  /* ---------------- boot ---------------- */
  function addPick(slug, title, select) {
    const p = $("#tripPicker");
    if (![...p.options].some(o => o.value === slug)) p.add(new Option(title, slug));
    if (select) p.value = slug;
    p.hidden = p.options.length < 2;
  }
  $("#tripPicker").addEventListener("change", async e => {
    dayIdx = 0; render(await (await fetch(`api/trips/${encodeURIComponent(e.target.value)}`)).json());
    history.replaceState(null, "", `?trip=${encodeURIComponent(e.target.value)}`);
  });

  async function boot() {
    if (window.__TRIP__) { $("#openAgent").hidden = true; render(window.__TRIP__); return; }
    try {
      health = await (await fetch("api/health")).json();
      if (!health.agent) { $("#agentStatus").textContent = "The planning agent is offline on this server (no ANTHROPIC_API_KEY). You can still browse trips."; $("#runAgent").disabled = true; }
      if (health.access_code_required) $("#codeRow").hidden = false;
      const trips = await (await fetch("api/trips")).json();
      trips.forEach(t => addPick(t.slug, t.title, false));
      const want = new URLSearchParams(location.search).get("trip") || trips[0]?.slug;
      if (!want) { $("#content").innerHTML = `<h1>No trips yet</h1><p class="hero-sub">Tap <b>✨ Plan a trip</b> to create one.</p>`; return; }
      addPick(want, want, true);
      render(await (await fetch(`api/trips/${encodeURIComponent(want)}`)).json());
    } catch (err) {
      $("#content").innerHTML = `<h1>Couldn't load</h1><p class="hero-sub">${esc(err.message)}</p>`;
    }
  }
  if (OFFLINE && !window.__TRIP__) $("#content").innerHTML = `<h1>Open via the server</h1><p class="hero-sub">Run <code>uv run uvicorn app:app</code>.</p>`;
  else boot();
})();
