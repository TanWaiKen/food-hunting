# Decision Log — Food Hunt

Format: **Step / Decision** → Why → How → Result. Newest at the bottom. Don't edit old entries; add new ones.

---

## Stage 0 — Process

### D1. Use "AI-DLC Lite": 4 stages and 2 human gates, not the full ~20-stage AI-DLC
- **Why:** You're one person running a small food-guide business. The full AI-DLC stages (user stories, NFR design, infra design, units…) produce documents nobody will read for a trip guide. The parts that actually stop wrong output are: lock the intent, verify the data, and get a human OK before publishing.
- **How:** Kept *Intent → Gather+Verify → Plan → Publish*. Gate 1 is after Intent (you confirm the trip file). Gate 2 is after Plan (you check the local HTML). See [WORKFLOW.md](WORKFLOW.md).
- **Result:** A new city is one yaml file plus one command. Nothing reaches Notion or WhatsApp until you've seen it locally.

### D2. Build a Claude-driven workflow plus a local MCP server, not an app and not n8n (yet)
- **Why:** You said "workflow, not an app lah". Claude can already read Rednote/web results and write to Notion, so it only needs reliable **tools**. n8n would add a server to run and maintain before we even know the output is right.
- **How:** One Python package `foodhunt` that you can run two ways: as a CLI (`uv run foodhunt plan …`) and as an MCP server (`foodhunt-mcp`, 11 tools) registered in [.mcp.json](../.mcp.json).
- **Result:** The same code runs locally, inside Claude, and later inside n8n or a WhatsApp bot (they can call the CLI). No rewrite is needed to "publish".

---

## Stage 1 — Intent (Hat Yai)

### D3. One trip file (`trips/hatyai.yaml`) is the single source of truth
- **Why:** Your Notion page, the Rednote list and the Lee Garden notes overlapped (Lee Garden appeared 3 times, and the 7-Eleven entry isn't a real stop). When intent lives in three places, things drift.
- **How:** Merged everything into 19 entries. Lee Garden oysters, BBQ and the Nutella roti became **one** night-market stop. 7-Eleven was dropped as a stop. Values you set by hand (hours, coordinates) always override anything looked up.
- **Result:** 19 places, each with kind, hours, source and a `confidence` level. Your existing Notion photos are reused through their stable `notion-file-block://` links.

### D4. Assume a Fri–Sun trip (4–6 Dec 2026) starting at Lee Gardens Plaza Hotel
- **Why:** You didn't give dates. Lee Garden Night Market is reported open **Fri–Sun only** (trip101), and your notes reference distances from Lee Gardens Plaza.
- **How:** `days:` in the yaml. Change the dates and re-run; the plan adapts to each weekday's hours.
- **Result:** The night market is on Friday night. ⚠️ **If your dates differ, edit the yaml and re-run.**

---

## Stage 2 — Gather + Verify

### D5. Google Places when a key is set, free OpenStreetMap otherwise
- **Why:** Google has the best ratings, hours and photos, but it needs a billing-enabled key. I didn't want the tool to be useless without one.
- **How:** `places.lookup()` uses Google Places (New) Text Search if `GOOGLE_MAPS_API_KEY` is set. Otherwise it uses Nominatim → Photon (OSM) → street-address geocoding, labelled **approx**.
- **Result:** Without a key, 15 of 19 places are routed (7 exact, 8 street-level approximate). **4 need a key:** Khrua Siblor, Leng Zapp (โนราเล้งแซ่บหม้อไฟ), Joke KakMu, Ken Phu Pang. They're listed with their links in a "Need exact location" section, not silently dropped.

### D6. Street-level pins are flagged, never treated as exact
- **Why:** In testing, Alive's street-level guess was **about 1.7 km** from the real place. A wrong pin means walking to the wrong spot.
- **How:** Name matches (OSM/Photon) and plus codes are pinned as exact. Street-only matches get `location: approx` and an orange "use the Google Maps link for the exact door" line.
- **Result:** Alive, Central, Chen Long, Bankampu, Makro, Jok Songkhla, Kai Tod Decha and Lee Garden are exact. Ko Chew became exact via a plus code found in a Rednote note.

### D7. Rednote = search-engine-indexed notes now; full logged-in search via `xiaohongshu-mcp` later
- **Why:** Rednote has no public API. Scraping it while logged out means fighting bot detection, which I won't build. The open-source [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) uses **your own login** (QR scan) and runs locally.
- **How:** `rednote_search` (no login; DuckDuckGo `site:xiaohongshu.com`) and `parse_rednote_share` (paste Rednote's Share text). `.mcp.json` already points to `http://localhost:18060/mcp` for when you run xiaohongshu-mcp.
- **Result:** It already found useful facts: Baan Khun Bhu is closed Wednesdays, Alive is closed Tuesdays, Ko Chew's exact plus code, and a "Krua Pa-Yad: avoid meal times" warning. All four were fed into the plan.

### D8. Hours: conflicting sources → use the narrower overlap and record the source
- **Why:** Most Hat Yai shops list different hours on different sites. For example, Baan Khun Bhu is 11:00–24:00 on kupi but 10:30–20:00 on Rednote. Arriving when a place is shut is the worst failure.
- **How:** Take the intersection (Baan Khun Bhu → 11:00–20:00, closed Wed), put a comment with the sources on each yaml line, and set `confidence: low` for single or unclear sources.
- **Result:** Every stop shows its hours for that day. Low-confidence ones get a red "check before going" line. **Unverified: Tumrub, Ken Phu Pang, Peter Kanomkrok, Sept, Jok Songkhla.**

### D9. Photos: your Notion photos + Google Places photos only; no random web images
- **Why:** This page is for a business you'll share. Copying photos from other people's blogs or Rednote posts is a copyright risk. Google Places photos are licensed for display through the API.
- **How:** `notion_images` are reused from your page. With a Google key, `images` are filled from Places photos (the URLs are short-lived, so download them with `save_photo` before uploading to Notion).
- **Result:** 10 of 19 places have your photos now. The rest get Google photos once the key is set.

---

## Stage 3 — Plan

### D10. Crowd levels: real data from BestTime if a key is set, otherwise a clearly labelled estimate
- **Why:** You asked for "crowdest time". Google's *Popular Times* is **not** in the official Places API. Scraping it is fragile and against Google's terms, and I won't present a guess as fact.
- **How:** `crowd.py` uses the BestTime.app forecast with `BESTTIME_API_KEY_PRIVATE`. Otherwise it uses meal-time curves per kind (breakfast peaks ~08:00, lunch 12:30, dinner 18:45, night market 19:30, dessert 15:00/20:30). Those are boosted on Fri–Sun, scaled by review count, and zero when closed.
- **Result:** Each stop shows its best and peak hour and a crowd strip (06:00→23:00), tagged "(estimated)" or "(live data)".

### D11. Slot-based planner (breakfast → supper) with a "scarcity first" rule
- **Why:** My first greedy version filled mornings with 7 meals and left evenings empty, so Friday's night market got pushed out. That's wrong for a food trip.
- **How:** Each day has 6 slots, and each slot only accepts the right kinds of place. For each slot, it picks the place with the best score: travel time + 0.3×waiting + 0.4×crowd − **scarcity** (places with few remaining chances, like the Fri–Sun market or Wed-closed Baan Khun Bhu) − must-eat − sells-out. Stops are spread evenly over the days. Places that sell out need a 1 h margin before closing.
- **Result:** Day 1 is all walking from the hotel (Ko Chew 06:36 → Chen Long → Baan Khun Bhu → Peter Kanomkrok at 15:00 → Lee Garden 18:00 → Sept). Day 2 uses Grab (Jok Songkhla, Makro, Krua Pa Yad, Central, Bankampu, Alive at 19:45 after dark). Day 3 is light (3 stops) for your travel home.

### D12. Walk ≤ 1.2 km, otherwise Grab; turn-by-turn steps come from OSRM
- **Why:** You want a "correct step-by-step map to follow and walk along". Straight-line distances lie in Hat Yai's one-way grid.
- **How:** OSRM foot/car routing (routing.openstreetmap.de) gives real distance, minutes and turn-by-turn steps. Each day also gets one Google Maps directions link with every stop as a waypoint.
- **Result:** Every leg shows "🚶 Walk 475 m · 6 min" with numbered turns, and one tap opens the whole day in Google Maps.

### D13. Breakfast starts at 06:30
- **Why:** The first run arrived at Ko Chew at 07:06, which is its estimated peak, and it sells out.
- **How:** Breakfast slot and day start moved to 06:30.
- **Result:** Arrival at 06:36, before the 07:00 peak.

---

## Stage 4 — Publish (waiting for Gate 2)

### D14. Local first: `output/hatyai.html` (map) and `output/hatyai.notion.md`; Notion only after your OK
- **Why:** You said "put it local first; if local works, then publish". Overwriting your existing Notion page is hard to undo.
- **How:** On "publish", Claude creates a **sub-page** "3-Day Food Route" under your Hatyai Food Trip page from the `.notion.md`. Your original page stays as it is. Sharing (Publish to web, then the WhatsApp link) is a button you press in Notion.
- **Result:** Pending your review.

---

## Iteration 2 — hosting, UI, album (2026-11-24)

### D15. One tool registry exposed three ways (local MCP, remote MCP, hosted agent)
- **Why:** You asked how the MCP servers are built and want to host them. Three copies of the same tools would drift apart.
- **How:** [foodhunt/tools.py](../foodhunt/tools.py) holds plain typed functions. `MCPServer.add_tool()` exposes them over stdio (local) and streamable HTTP at `/mcp` (stateless, JSON). The Anthropic SDK's `beta_tool()` turns the same functions into Claude API tools.
- **Result:** One change updates all three, and the tests cover the MCP-over-HTTP and agent paths.

### D16. Hosted agent = Claude API Tool Runner on Vercel (not Managed Agents)
- **Why:** You want to host it on Vercel yourself, so the loop has to run in your function. Locally, Claude Code is the agent and nothing extra is hosted.
- **How:** [foodhunt/agent.py](../foodhunt/agent.py): `client.beta.messages.tool_runner` with model `claude-opus-5-5`, effort `high`, server-side `web_search`/`web_fetch` (more reliable from Vercel than free search), and refusal fallback (`fallbacks: "default"`). It streams events to the browser over SSE.
- **Result:** "✨ Plan a trip" works on any host with `ANTHROPIC_API_KEY`. It was tested here with a mocked client because this machine has no API key; a real run costs money.

### D17. FastAPI on Vercel (Python kept), not a Next.js rewrite
- **Why:** The planner is tested Python. Vercel runs FastAPI with zero config (uv, lifespan, streaming, 300 s functions).
- **How:** `app.py` entrypoint, `[tool.vercel] entrypoint`, `vercel.json` (`maxDuration: 300`), `.python-version` 3.14, `public/` served by the CDN (not mounted on Vercel, per Vercel's docs). Writable data goes to `/tmp`.
- **Result:** A Vercel-mode simulation passed (health, trips, MCP tools/list). Not yet deployed (that needs your Vercel login).

### D18. Paid endpoints are gated by an access code
- **Why:** A public `/api/agent` or `/mcp` would let anyone spend your Claude/Google credits.
- **How:** `FOODHUNT_ACCESS_TOKEN` is checked with a constant-time compare on `/api/agent`, `/api/plan`, uploads and `/mcp` (Bearer). Unset means open, for local dev.
- **Result:** Tested: 401 without the code, 200 with it.

### D19. Bugs found by testing, then fixed
- **Planner:** a place with only one chance (e.g. a Fri-only night market) could be dropped when the per-day cap filled up early. Now its slot is reserved ("today or never").
- **Windows MCP:** `rednote_search` failed over stdio because the search library logged Thai/Chinese text to a cp1252 stderr. Now stderr is UTF-8, noisy loggers are quieted, and `.mcp.json` sets `PYTHONIOENCODING`.
- **UI:** the sticky header vanished after one screen (`body{height:100%}`). CARTO tiles now need a key, so the map uses OSM tiles.

### D20. Design: "Field Journal" = Oura × Runway × scrapbook ([DESIGN.md](../DESIGN.md))
- **Why:** Your references (map-collage scrapbook, vertical-word magazine cover, postage stamps on espresso) are editorial and paper-based. In awesome-design-md, Oura (warm paper, thin serif, earth tones) and Runway (photography-first, dark cinema stage) are the closest.
- **How:** Canvas `#f6f0e6`, Fraunces 300 display, Inter body, Anton only for cover words, one chili action colour, ochre/clay/olive for data. Map day colours stay on the colourblind-validated set.
- **Result:** Both the route page and the album use the same tokens.

### D21. Album matches photos to places automatically
- **Why:** After a trip, nobody wants to sort 200 photos by hand.
- **How:** EXIF GPS → nearest stop within 250 m, else EXIF time → that day's stop window (−30/+60 min), else "Unsorted" with a "Move to…" picker. Photos are EXIF-rotated and resized to ≤1600 px.
- **Result:** Tested with synthetic GPS/time photos. A live upload "at" Lee Garden matched the night market at 3 m.

### D22. Travel Photo Abstraction: Claude picks the facts, code picks the colours
- **Why:** Your "图像的普鲁斯特效应" idea only works if the symbol is faithful. Colours an LLM invents would break the memory link.
- **How:** `SymbolSpec` holds 1–3 visual facts and ≤8 shapes on a 100×100 grid. Claude fills it (vision + structured output, or Claude Code via the skill). The palette is quantised from the photo's pixels, and the SVG is rendered by code.
- **Result:** I generated all 17 Hat Yai symbols in Claude Code (no API key). The album shows them beside each stamp and on the "Proust page" index.

### D23. Album photos on Vercel need real storage (open)
- **Why:** On Vercel, `/tmp` is wiped between cold starts.
- **How:** Not done yet; Vercel Blob is the natural fit.
- **Result:** Locally, albums persist. Hosted albums are **not** persistent until Blob is added.

---

## Iteration 3 — KL time, home page, de-AI design (2026-11-24)

### D24. All times shown in Kuala Lumpur time (MYT); the planner stays on local time
- **Why:** You plan from KL and want one clock. But shops open by *their* clock, and phones abroad switch to local time.
- **How:** [foodhunt/tz.py](../foodhunt/tz.py) works out the offset per trip (`timezone: Asia/Bangkok` → +60 min). The view, the Notion export and the CLI show MYT. `*_local` fields keep the local time, which photo matching uses.
- **Result:** Ko Chew shows 07:36 MYT with "06:36 local" under it, and opening hours read 07:30–15:30 MYT. Tests cover the conversion and the photo-matching rule.

### D25. A home page that lists every trip
- **Why:** The site shouldn't be "only the Hatyai food trip".
- **How:** `/` is now a home page (hero, trip cards with an evening cover photo, cover word, dates and that trip's Proust symbols, and a "Somewhere new?" card). The route page moved to `trip.html?trip=<slug>`, and `/api/trips` now returns cover, dates, stops, distance and symbols.
- **Result:** Each new trip appears on the home page automatically.

### D26. Buttons and copy redesigned
- **Why:** You said the buttons "look very AI". The giveaways were emoji in pills (✨📷🧭), many filled buttons, and plain unstyled sentences.
- **How:** I researched getdesign.md (Nike, Apple, Framer, Clay, Airbnb, Stripe): one filled ink pill per view, text links with chevrons, and press-to-shrink. Their DESIGN.md files leave motion out, so I designed it (DESIGN.md §11). Sentences got typographic roles (serif lede with one italic accent, spelled-out numbers).
- **Result:** No emoji remain in any control. Three directions can be compared live on `/lab.html`; **A is applied now**, and B or C can replace it after you choose.

### D27. GitHub: code public, photos private
- **Why:** The repo `TanWaiKen/food-hunting` is public, and some photos are other people's (watermarked).
- **How:** `public/img/` and `data/*/photos/` are gitignored. You chose this option.
- **Result:** The code and the trip are on GitHub. Photos stay on your PC (and go to Vercel only when you deploy from this PC).

### D28. Direction C · Poster chosen for the whole site
- **Why:** You compared the three directions on `/lab.html` and picked the last one.
- **How:** A Poster layer on top of the shared tokens: Anton caps headlines that wipe in line by line, square bordered buttons with an ink fill that swipes in, caps underlined links, rule-topped cards and stats, no rounded corners. It's applied to the home, route and album pages. Rules are in DESIGN.md §12.
- **Result:** Checked on desktop (1360px) and phone (375px) with no sideways scroll. The mobile top bar was trimmed so the button labels no longer wrap.

### D29. Upload photos from each restaurant; search trips on the home page
- **Why:** You want every suggested restaurant to have its own place for photos that then become the album. You also want the site to work for any trip, not just Hat Yai, so you can search.
- **How:** Each route card has a "Your photos" strip with an **Add photos** button. The upload sends that stop's key, so the photo is filed under that restaurant without needing GPS/EXIF. On the home page, a search box matches trip title, city, place names and dishes (case and accents ignored). If nothing matches, it offers "Plan <city>?", which opens the planner already filled in.
- **Result:** Tested: "pork" finds Hatyai, "Penang" offers a new plan. Cards show the photos already filed there. 29 tests pass, including uploading to a set stop and rejecting an unknown stop.
