/* Food Hunt album: cover → one scrapbook spread per day → film strip → Proust index → unsorted tray. */
(() => {
  "use strict";
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const DAY = ["--d1", "--d2", "--d3", "--d4"].map(v => getComputedStyle(document.documentElement).getPropertyValue(v).trim());
  const slug = new URLSearchParams(location.search).get("trip") || "hatyai";
  const auth = () => { const c = localStorage.getItem("fh_code"); return c ? { Authorization: `Bearer ${c}` } : {}; };
  const fmtDay = d => new Date(d + "T00:00:00").toLocaleDateString("en", { weekday: "short", day: "numeric", month: "short" });
  let data = null;

  const toast = msg => { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 3200); };

  async function load() {
    const r = await fetch(`api/trips/${encodeURIComponent(slug)}/album`);
    if (!r.ok) { $("#album").innerHTML = `<p class="loading">Trip “${esc(slug)}” not found.</p>`; return; }
    data = await r.json();
    render();
  }

  /* ---------------- helpers ---------------- */
  const stopsByKey = () => Object.fromEntries(data.stops.map(s => [s.key, s]));
  const photosFor = key => data.album.photos.filter(p => p.stop_key === key);
  const stampImg = (p, alt) => `<div class="stamp-wrap"><div class="stamp"><img src="${esc(p.src)}" alt="${esc(alt)}" loading="lazy"></div></div>`;

  function memoryHTML(p, stop, n, color) {
    const sym = p.symbol_svg ? `<div class="symbol" title="${esc((p.symbol.visual_facts || []).join(" · "))}">${p.symbol_svg}</div>` : "";
    const opts = data.stops.map(s => `<option value="${s.key}">${esc(s.name)}</option>`).join("");
    return `<article class="memory" style="--day:${color}" data-id="${p.id}">
      <div class="memory-head">${n ? `<span class="stopno">${n}</span>` : ""}<span class="place">${esc(stop?.name || "Unsorted")}</span>${stop?.arrive ? `<time>${esc(stop.arrive)}</time>` : ""}</div>
      <div class="pair ${sym ? "" : "no-symbol"}">${stampImg(p, stop?.name || "")}${sym}</div>
      ${p.caption || p.symbol?.caption ? `<p class="caption">${esc(p.caption || p.symbol.caption)}</p>` : ""}
      ${p.symbol ? `<p class="facts">${esc(p.symbol.visual_facts.join(" · "))}</p>` : ""}
      <div class="mini-actions">
        <button type="button" data-act="abstract">${p.symbol ? "↻ Redo symbol" : "✨ Make symbol"}</button>
        <select data-act="move" aria-label="Move photo to place"><option value="">Move to…</option>${opts}</select>
        ${p.by ? `<span class="facts">matched by ${esc(p.by)}${p.distance_m != null ? ` · ${p.distance_m} m` : ""}</span>` : ""}
      </div>
    </article>`;
  }

  /* hand-drawn route map for one day, projected into a 400×300 paper card */
  function routeSVG(day, i) {
    const pts = [data.view.trip.start, ...day.stops.map(s => s.place)];
    const geo = day.stops.flatMap(s => s.leg.geometry || []);
    const all = [...pts.map(p => [p.lat, p.lng]), ...geo];
    const lats = all.map(a => a[0]), lngs = all.map(a => a[1]);
    const [a0, a1, o0, o1] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
    const W = 400, H = 300, pad = 30, sx = (W - 2 * pad) / Math.max(o1 - o0, 1e-4), sy = (H - 2 * pad) / Math.max(a1 - a0, 1e-4), s = Math.min(sx, sy);
    const X = lng => pad + (lng - o0) * s + ((W - 2 * pad) - (o1 - o0) * s) / 2;
    const Y = lat => H - pad - (lat - a0) * s - ((H - 2 * pad) - (a1 - a0) * s) / 2;
    const line = geo.map(([la, lo]) => `${X(lo).toFixed(1)},${Y(la).toFixed(1)}`).join(" ");
    const grid = Array.from({ length: 9 }, (_, k) => `<line x1="${k * 50}" y1="0" x2="${k * 50}" y2="${H}"/><line x1="0" y1="${k * 40}" x2="${W}" y2="${k * 40}"/>`).join("");
    const stamps = day.stops.map((st, j) => `<g transform="translate(${X(st.place.lng).toFixed(1)},${Y(st.place.lat).toFixed(1)})">
        <circle r="11" fill="${DAY[i % 4]}" stroke="#fffaf2" stroke-width="2.5"/><text y="4" text-anchor="middle" font-family="Anton,Impact" font-size="12" fill="#fffaf2">${j + 1}</text></g>`).join("");
    const st = data.view.trip.start;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Route for day ${i + 1}">
      <rect width="${W}" height="${H}" fill="#fbf5ea"/><g stroke="#e9dfcf" stroke-width="1">${grid}</g>
      <polyline points="${line}" fill="none" stroke="${DAY[i % 4]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1 7" opacity=".9"/>
      <polyline points="${line}" fill="none" stroke="${DAY[i % 4]}" stroke-width="1.4" opacity=".55"/>
      <rect x="${X(st.lng) - 9}" y="${Y(st.lat) - 9}" width="18" height="18" rx="3" fill="#2b1d18"/><text x="${X(st.lng)}" y="${Y(st.lat) + 4}" text-anchor="middle" font-size="11" fill="#fffaf2">⌂</text>
      ${stamps}
      <g transform="translate(${W - 26},28)" fill="none" stroke="#857d74" stroke-width="1.2"><path d="M0,10 L0,-10 M-5,-4 L0,-10 L5,-4"/><text y="22" text-anchor="middle" font-size="9" fill="#857d74" stroke="none">N</text></g>
    </svg>`;
  }

  /* ---------------- render ---------------- */
  function render() {
    const v = data.view, sk = stopsByKey(), ps = data.album.photos;
    const word = (v.trip.title.split(/\s+/)[0] || v.trip.city).toUpperCase();
    const first = v.days[0]?.date;
    const chip = first ? new Date(first + "T00:00:00").toLocaleDateString("en", { month: "short", year: "numeric" }).toUpperCase() : "";
    const night = ps.find(p => { const s = sk[p.stop_key]; return s && s.arrive >= "18:00"; }) || ps[0];
    document.title = `${v.trip.title} · Album`;
    $("#barTitle").textContent = `${v.trip.title} · ${ps.length} photos`;
    $("#backLink").href = `./?trip=${encodeURIComponent(slug)}`;

    const cover = `<section class="cover"><div class="book">
        <h1 class="spine-word">${esc(word)}</h1>
        <div class="cover-photo" style="background-image:url('${night ? esc(night.src) : ""}')" role="img" aria-label="Cover photo">
          <span class="cover-sub">${esc(v.days.length)} days, ${esc(v.days.reduce((a, d) => a + d.stops.length, 0))} plates</span>
          <span class="cover-chip">${esc(chip)}</span></div></div></section>`;

    const spreads = v.days.map((d, i) => {
      const color = DAY[i % 4];
      const mems = d.stops.map((s, j) => {
        const mine = photosFor(`${i}-${j}`);
        return mine.length ? mine.map((p, k) => memoryHTML(p, sk[p.stop_key], k ? "" : j + 1, color)).join("")
          : `<article class="memory" style="--day:${color}"><div class="memory-head"><span class="stopno">${j + 1}</span><span class="place">${esc(s.place.display)}</span><time>${esc(s.arrive)}</time></div><div class="empty-stop">No photo yet —<br>add one after you eat here.</div></article>`;
      }).join("");
      return `<section class="spread" style="--day:${color}"><div class="spread-inner">
        <div class="chapter"><span class="num">${String(i + 1).padStart(2, "0")}</span><div><span class="eyebrow">Day ${i + 1} · ${esc(fmtDay(d.date))}</span>
          <h2>${esc(d.stops.length)} stops, ${(d.walk_m / 1000).toFixed(1)} km on foot</h2></div></div>
        <div class="pages"><div class="mapcard"><span class="tape"></span>${routeSVG(d, i)}<span class="eyebrow">From ${esc(v.trip.start.name)}</span></div>
          <div class="memories">${mems}</div></div></div></section>`;
    }).join("");

    const extra = ps.filter(p => p.stop_key && p.stop_key.startsWith("x-"));
    const extraSpread = extra.length ? `<section class="spread" style="--day:var(--clay)"><div class="spread-inner">
        <div class="chapter"><span class="num">+</span><div><span class="eyebrow">Off the route</span><h2>Also on the list</h2></div></div>
        <div class="memories">${extra.map(p => memoryHTML(p, sk[p.stop_key], "", "var(--clay)")).join("")}</div></div></section>` : "";

    const highlights = v.days.flatMap((d, i) => d.stops.map((s, j) => photosFor(`${i}-${j}`)[0]).filter(Boolean)).slice(0, 5);
    const strip = highlights.length ? `<section class="stage"><span class="eyebrow">Food Hunt · ${esc(v.trip.city.split(",")[0])}</span>
        <div class="stage-grid"><p class="side">Food<br>postcards<br><em>from</em></p>
        <div class="strip"><svg class="clip" viewBox="0 0 64 44" aria-hidden="true"><path d="M14 40 L14 10 Q32 -6 50 10 L50 40" fill="none" stroke="#8d8d8d" stroke-width="2.5"/><rect x="2" y="26" width="60" height="18" rx="3" fill="#111"/></svg>
          ${highlights.map(p => stampImg(p, sk[p.stop_key]?.name || "")).join("")}</div>
        <p class="side right">${esc(v.trip.city.split(",")[0])}<br><em>and</em><br>${esc((v.trip.city.split(",")[1] || "").trim() || "beyond")}</p></div></section>` : "";

    const withSym = ps.filter(p => p.symbol_svg);
    const index = withSym.length ? `<section class="index"><div class="index-inner"><span class="eyebrow">Memory index</span>
        <h2>The Proust page</h2>
        <p class="lead">A smell can bring back a whole afternoon. These are the same moments, reduced to the few shapes and colours your eye remembered. Hover to see the photo.</p>
        <div class="symbols">${withSym.map(p => `<figure tabindex="0">${p.symbol_svg}<img src="${esc(p.src)}" alt="" loading="lazy">
          <figcaption>${esc(p.caption || p.symbol.caption || p.symbol.motif)}</figcaption></figure>`).join("")}</div></div></section>` : "";

    const unsorted = ps.filter(p => !p.stop_key);
    const tray = unsorted.length ? `<section class="tray"><span class="eyebrow">Unsorted</span><h2 style="font:300 28px var(--serif);margin:4px 0 18px">No location or time matched — pick a place</h2>
        <div class="memories">${unsorted.map(p => memoryHTML(p, null, "", "var(--ash)")).join("")}</div></section>` : "";

    const drop = `<div class="drop" id="drop">Drop photos here — they're matched to places by GPS, then by time taken.</div>`;
    $("#album").innerHTML = cover + spreads + extraSpread + strip + index + tray + drop;
    wire();
  }

  /* ---------------- actions ---------------- */
  function wire() {
    document.querySelectorAll(".memory[data-id]").forEach(card => {
      const id = card.dataset.id;
      card.querySelector('[data-act="abstract"]')?.addEventListener("click", async e => {
        e.target.disabled = true; e.target.textContent = "Looking…";
        const r = await fetch(`api/trips/${slug}/photos/${id}/abstract`, { method: "POST", headers: auth() });
        if (!r.ok) {
          const msg = (await r.json().catch(() => ({}))).detail || r.status;
          toast(r.status === 502 && /api_key|auth/i.test(msg) ? "Needs ANTHROPIC_API_KEY on the server — or run the skill in Claude Code." : `Couldn't make a symbol: ${msg}`);
          e.target.disabled = false; e.target.textContent = "✨ Make symbol"; return;
        }
        await load(); toast("Symbol made.");
      });
      card.querySelector('[data-act="move"]')?.addEventListener("change", async e => {
        if (!e.target.value) return;
        await fetch(`api/trips/${slug}/photos/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json", ...auth() }, body: JSON.stringify({ stop_key: e.target.value }) });
        await load(); toast("Moved.");
      });
    });
    const drop = $("#drop");
    ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", e => upload(e.dataTransfer.files));
  }

  async function upload(files) {
    if (!files?.length) return;
    const fd = new FormData(); [...files].forEach(f => fd.append("files", f));
    toast(`Uploading ${files.length} photo${files.length > 1 ? "s" : ""}…`);
    const r = await fetch(`api/trips/${slug}/photos`, { method: "POST", body: fd, headers: auth() });
    if (!r.ok) { toast(r.status === 401 ? "Access code needed (set it on the route page)." : `Upload failed (${r.status})`); return; }
    const { added } = await r.json();
    const matched = added.filter(a => a.stop_key).length;
    await load();
    toast(`${added.length} added · ${matched} matched to places automatically`);
  }

  $("#fileInput").addEventListener("change", e => upload(e.target.files));
  $("#showSymbols").addEventListener("change", e => document.body.classList.toggle("hide-symbols", !e.target.checked));
  $("#printBtn").addEventListener("click", () => window.print());
  load();
})();
