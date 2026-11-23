/* Home: list every trip as a cover card. */
(() => {
  "use strict";
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const range = (a, b) => {
    if (!a) return "";
    const A = new Date(a + "T00:00:00"), B = new Date((b || a) + "T00:00:00");
    const m = d => d.toLocaleDateString("en", { month: "short" });
    return A.getMonth() === B.getMonth() ? `${A.getDate()}–${B.getDate()} ${m(A)} ${A.getFullYear()}` : `${A.getDate()} ${m(A)} – ${B.getDate()} ${m(B)}`;
  };

  function card(t) {
    const word = (t.title.split(/\s+/)[0] || t.city).toUpperCase();
    const cover = t.cover ? `<img src="${esc(t.cover)}" alt="" loading="lazy">` : "";
    return `<article class="trip-card reveal">
      <a class="cover" href="trip.html?trip=${encodeURIComponent(t.slug)}" aria-label="${esc(t.title)} route">${cover}
        <span class="word" aria-hidden="true">${esc(word)}</span><span class="dates">${esc(range(t.first_day, t.last_day))}</span></a>
      <div class="body">
        <p class="kicker">${esc(t.city)}</p>
        <h3>${esc(t.title)}</h3>
        <p class="facts">${t.days} days · ${t.stops} plates · ${(t.walk_m / 1000).toFixed(1)} km on foot${t.photos ? ` · ${t.photos} photos` : ""}</p>
        ${t.symbols?.length ? `<div class="symbols" aria-hidden="true">${t.symbols.join("")}</div>` : ""}
        <div class="links">
          <a class="link" href="trip.html?trip=${encodeURIComponent(t.slug)}">Route <span class="chev" aria-hidden="true">›</span></a>
          <a class="link" href="album.html?trip=${encodeURIComponent(t.slug)}">Album <span class="chev" aria-hidden="true">›</span></a>
        </div>
      </div>
    </article>`;
  }

  const fresh = q => q
    ? `<a class="new-card reveal" href="trip.html?plan=1&q=${encodeURIComponent(q)}"><div><h3>Plan ${esc(q)}?</h3>
    <p>No trip for that yet. We'll research it, verify each place and time the route.</p>
    <span class="btn btn-primary">Plan this trip <span class="arrow" aria-hidden="true">→</span></span></div></a>`
    : `<a class="new-card reveal" href="trip.html?plan=1"><div><h3>Somewhere new?</h3>
    <p>Name the city and the dishes. The route comes back verified and timed.</p>
    <span class="btn btn-primary">Plan a trip <span class="arrow" aria-hidden="true">→</span></span></div></a>`;

  /* search: every word must appear in the trip's title, city, places or dishes (accents/case ignored) */
  const norm = s => String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, "");
  let all = [];
  function show(q) {
    q = (q || "").trim();
    const terms = q.split(/\s+/).filter(Boolean).map(norm);
    const hits = !terms.length ? all : all.filter(t => {
      const hay = norm([t.title, t.city, t.slug, ...(t.places || []), ...(t.dishes || [])].join(" "));
      return terms.every(w => hay.includes(w));
    });
    document.getElementById("tripGrid").innerHTML = hits.map(card).join("") + fresh(hits.length ? "" : q);
    document.getElementById("searchNote").textContent = !q ? "" : hits.length ? `${hits.length} trip${hits.length > 1 ? "s" : ""} match “${q}”` : `Nothing for “${q}” yet`;
    reveal();
  }
  const form = document.getElementById("tripSearch"), input = document.getElementById("q");
  input.value = new URLSearchParams(location.search).get("q") || "";
  input.addEventListener("input", () => show(input.value));
  form.addEventListener("submit", e => { e.preventDefault(); show(input.value);
    history.replaceState(null, "", input.value.trim() ? `?q=${encodeURIComponent(input.value.trim())}#trips` : location.pathname); });

  function reveal() {
    const els = document.querySelectorAll(".reveal:not(.in)");
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) { els.forEach(e => e.classList.add("in")); return; }
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -6% 0px" });
    els.forEach((e, i) => { e.style.setProperty("--d", `${(i % 5) * 70}ms`); io.observe(e); });
  }

  fetch("api/trips").then(r => r.json()).then(trips => { all = trips; show(input.value); })
    .catch(() => { document.getElementById("tripGrid").innerHTML = `<p class="muted">Couldn't load trips.</p>` + fresh(""); reveal(); });
  reveal();
})();
