# AltairGO Strategic Roadmap — Quality-First Implementation Plan

> **Date:** 2026-04-21
> **Status:** Draft — awaiting founder approval
> **Thesis:** The itinerary is the product. Features built on a bad itinerary are wasted.

---

## 1. Requirements Restatement

**The Thesis (in plain terms):**
The itinerary is the product. Bookings, analytics, SEO, and virality are amplifiers — they multiply whatever quality signal the core product emits. If that signal is weak, amplifiers broadcast weakness. Therefore, no feature downstream of the itinerary ships until itinerary quality is measurable, stable, and defensibly good.

**Hard constraints (non-negotiable):**

1. Every roadmap phase must have a quality gate — a phase cannot ship if it degrades a tracked quality metric.
2. No prompt, model, or engine change enters production without passing an automated eval.
3. The user must never see a "Trip to X" unpolished fallback in a state that is silently accepted as success — either it's visibly flagged as degraded, or it doesn't ship.
4. All quality dimensions must have at least one objective (non-LLM-judged) measurement. LLM-as-judge is a supplement, not the sole signal.
5. Phase 0 precedes everything. Even urgent revenue work waits for eval infrastructure.
6. Migrations via Supabase MCP only. Never `flask db upgrade` in prod.
7. Budget reality: Gemini free tier is a known cliff. Either pay for it, or make Ollama polish good enough that it is indistinguishable in blind tests.

**Ambiguity resolved:** "Focus on quality" could mean (a) fix the 8 known quality cliffs or (b) raise the ceiling on what AltairGO can generate. **Default: 70% floor, 30% ceiling** — floor bugs are what users actually hit.

---

## 2. Definition of a "Quality Itinerary"

Quality is a vector, not a scalar. 10 measurable dimensions:

### 2.1 Factual Accuracy
- **Definition:** Every claim (attraction, price, hours) corresponds to reality.
- **Gap:** Gemini hallucinates names, closing times, "famous" dishes. No fact-check layer.
- **Measurement:** Extract entity mentions; cross-reference against `Attraction` table. Grounding rate ≥95%.

### 2.2 Operational Correctness (the "closed-days" dimension)
- **Definition:** No activity scheduled when it's physically inaccessible.
- **Gap:** `Attraction.closed_days`, `opening_hours` have uneven coverage. Filter passes if data is NULL.
- **Measurement:** Post-generation replay: for each activity, check (closed_days, opening_hours, seasonal, WeatherAlert). Target: 0 violations on >80% data-coverage trips.

### 2.3 Route Sensibility
- **Definition:** Daily order is geographically rational. No zig-zag.
- **Gap:** RouteOptimizer uses flat 15 km/h, no traffic model, no meal-adjacent clustering.
- **Measurement:** Total daily km, max leg km, backtrack ratio (leg distances / hull perimeter). Track p50, p90.

### 2.4 Budget Accuracy
- **Definition:** `total_cost` matches actual spend within ±15%.
- **Gap:** HotelPrice tiers are static; flight costs aren't dynamic; activity costs often NULL.
- **Measurement:** Reconcile `cost_breakdown` against `ExpenseEntry.actual_amount`. Report MAPE.

### 2.5 Pacing
- **Definition:** Activities per day humane; morning/afternoon/evening split fits traveler_type.
- **Gap:** Assembler has `pacing_level` but no heuristic for over/under-scheduling per traveler profile.
- **Measurement:** Activities/day distribution by traveler_type. Target: 3–5 for family/senior, 4–6 for solo/adventure.

### 2.6 Personalization Fidelity
- **Definition:** Itinerary demonstrably reflects user input.
- **Gap:** Interests accepted but unclear if they bias theme selection.
- **Measurement:** Cosine similarity between (user interest vector) and (itinerary theme vector). Target ≥0.6.

### 2.7 Narrative Polish
- **Definition:** `trip_title`, `theme`, `smart_insights` read like a human wrote them.
- **Gap:** "Trip to X" ships when polish chain exhausts. No detector gates this.
- **Measurement:** Regex + LLM-judge. Fail if `trip_title` matches `^Trip to .+$` or `smart_insights` empty. Flesch readability + weekly 10-sample human rating.

### 2.8 Safety & Practical Info
- **Definition:** Pre-trip covers docs, health, seasonal hazards; per-day weather alerts where relevant.
- **Gap:** `DestinationInfo` has 29 rows for ~190 destinations — 15% coverage.
- **Measurement:** `DestinationInfo` coverage %. Per-itinerary: `pre_trip_info` non-empty, `weather_alerts` checked.

### 2.9 Diversity / Anti-repetition
- **Definition:** Multi-day trips don't repeat themes or attractions.
- **Gap:** Assembler has 20% overlap threshold but no cross-day uniqueness check.
- **Measurement:** Duplicate activity rate across days; theme entropy. Target: 0 duplicates, entropy >1.0 (3+ day trips).

### 2.10 Latency & Reliability
- **Definition:** Generation completes <30s p95 without falling to unpolished.
- **Gap:** DEV_EAGER ~17s but Gemini 429s push toward fallback chain.
- **Measurement:** p50/p95/p99 latency; polish tier distribution (gemini / flash-lite / ollama / unpolished).

---

## 3. Risk Register (Top 10, ranked by impact × likelihood)

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|-----------|------------|
| 1 | Gemini 429 cascade → Ollama fails → "Trip to X" ships | Catastrophic | High (free tier) | Phase 0: polish-failure detector blocks ship; Phase 1: paid Gemini OR fine-tuned local model |
| 2 | No eval harness → silent quality regressions | Catastrophic | High (every prompt edit) | Phase 0: golden dataset + CI gate |
| 3 | Attraction data gaps (closed_days, hours, accessibility) → wrong activities | High | Medium-High | Phase 1: enrichment sprint + reject-NULL filter hardening |
| 4 | Embeddings NULL → semantic rec dead → bad personalization | High | Certain (already broken) | Phase 1: run `embedding_sync` on all destinations + attractions |
| 5 | Schema drift (models.py vs DB) | Medium | High (recurring) | Phase 0: schema-drift CI check; Phase 1: reconcile all models |
| 6 | No A/B or canary → prompt changes all-or-nothing | High | Medium | Phase 0: feature-flag-gated prompt variants |
| 7 | Affiliate ID unset → zero real booking revenue | Catastrophic for revenue | Certain | Phase 3 (after quality). Start BD in parallel Phase 1 |
| 8 | Mobile conversion unmeasured on 80% of traffic | High | Certain | Phase 0-lite: funnel events via logging middleware |
| 9 | `run_quality_scoring` task results not surfaced | Medium-High | High | Phase 0: wire `itinerary_qa` as active gate, not passive task |
| 10 | Cost of Gemini upgrade unforecasted at scale | Medium (runway risk) | Medium | Phase 0: cost-per-itinerary telemetry, then decide buy vs self-host |

**Additional risks to surface:**

- **Prompt injection** via `selected_destinations[].name`, `interests`, `dietary` flowing into Gemini prompts. One jailbreak screenshot on Twitter = trust disaster. Mitigation: input allowlisting + prompt template hardening in Phase 0.
- **Seasonality skew** in baseline measurement. Build harness with seasonal-aware partitions.
- **Supabase pooler gotcha recurrence.** CI-check `DATABASE_URL` format.

---

## 4. Phased Plan

### Phase 0 — Quality Foundation (4–6 weeks, MUST ship first)

**Thesis:** You cannot improve what you cannot measure.

**Objectives:**

1. Golden dataset: 50 canonical test prompts (traveler_type × budget × duration × destination_category).
2. Eval harness running all 10 quality dimensions against golden set.
3. CI pre-merge gate that fails on dimension regression.
4. Promote `backend/agents/itinerary_qa.py` from passive to active gate.
5. Polish-failure detector: retries with different model OR marks itinerary "draft" instead of shipping "Trip to X."
6. A/B harness: two prompt variants via existing `FeatureFlag` model + logged outcomes.
7. Quality dashboard (Grafana/Metabase): 10 dimensions over time, per model, per traveler_type.
8. Schema-drift CI check: compare `models.py` vs `information_schema`.
9. Funnel instrumentation: generate → save → share → book.
10. Prompt-injection hardening.

**Sequencing:**

- **Week 1:** Golden dataset design + curation. Schema-drift check (easy win).
- **Week 2:** Eval harness for objective dimensions (2.1, 2.2, 2.3, 2.4, 2.5, 2.9). Funnel events.
- **Week 3:** LLM-judge dimensions (2.6, 2.7). Polish-failure detector.
- **Week 4:** `itinerary_qa` as active gate. A/B harness. Prompt-injection hardening.
- **Week 5:** Dashboards. Baseline measurement on golden set + last 30 days.
- **Week 6:** Buffer + signoff. Baseline numbers documented.

**Success metrics (Phase 0 exit):**

- Golden dataset: ≥50 prompts, founder-reviewed.
- Eval runs <5 min locally, <15 min in CI.
- Baseline published for all 10 dimensions.
- Polish-failure detector catches 100% of `"Trip to .+"` + empty-smart_insights on 100-trip synthetic test.
- Schema-drift CI green.
- A/B harness demonstrated end-to-end.

**Stop rule:** Do not begin Phase 1 until baseline is published and reviewed. If you cannot measure a dimension, declare it out of scope.

**Complexity:** Medium-High.

---

### Phase 1 — Quality Lifts (6–10 weeks)

**Objectives (ranked by lift/effort):**

**1.1 Polish reliability (kills Risk #1):**

- Decide: paid Gemini vs self-hosted polish (use Phase 0 cost telemetry).
- Add `gemini-2.0-flash` retry with exponential backoff before flash-lite.
- Harden Ollama fallback: structured output + json-repair on parse failures.
- Add third fallback: deterministic Jinja template polish — ugly but never "Trip to X."

**1.2 Embedding generation (kills Risk #4):**

- Run `backend.scripts.generate_embeddings` on 190 destinations + 11,539 attractions.
- Validate: semantic similarity tests on curated pairs.
- Wire embedding-based recommendation into FilterEngine as tiebreaker.

**1.3 Attraction data enrichment (kills Risk #3):**

- Audit % NULL for `closed_days`, `opening_hours`, `accessibility_level`, `dietary_options`, `min_age`.
- Source: OSM Overpass + Google Places + manual curation for top 500 attractions.
- Harden FilterEngine: reject NULL when user specified constraint (currently lets NULL pass).
- Target: 90% coverage on top-500, 60% on all 11,539.

**1.4 Pacing heuristic:**

- Add pacing rules per traveler_type to Assembler.
- Block "7-activity" day for seniors; block "1-activity" day unless explicitly requested.

**1.5 Route optimizer upgrades:**

- Replace flat 15 km/h with city (12 km/h) vs intercity (35 km/h) split.
- Meal-time clustering: lunch activity within 2 km of 12:00–14:00 block.
- Measure backtrack ratio delta.

**1.6 Prompt engineering cycles:**

- 3–5 A/B prompt variants per week. Keep winners on golden set.
- Focus: `trip_title` creativity, `smart_insights` specificity, `theme` variety.

**1.7 Schema reconciliation:**

- Fix `LocalEvent.start_date/end_date` type mismatch (model `String(10)` vs DB `DATE`).
- Proper ORM relationship for `Destination ↔ state_id`.

**Sequencing:**

- **Weeks 1–2:** 1.1 polish + 1.2 embeddings (highest impact).
- **Weeks 3–5:** 1.3 attraction data (slow curation, run parallel).
- **Weeks 4–6:** 1.4 pacing + 1.5 routing.
- **Weeks 6–8:** 1.6 prompt cycles (continuous).
- **Weeks 8–10:** 1.7 schema + buffer.

**Success metrics (Phase 1 exit):**

- Polished-unpolished rate: <0.5%.
- Embedding coverage: 100% destinations, 100% attractions.
- Closed-days violations on golden set: 0.
- Pacing outlier rate: <5%.
- Backtrack ratio p90: -20% vs Phase 0 baseline.
- Golden-set aggregate: +15% vs baseline.
- Schema drift: 0 CI failures for 4 consecutive weeks.

**Stop rule:** Do not begin Phase 2 until Phase 1 exit metrics are green for 2 consecutive weeks.

**Complexity:** High. Multiple parallel tracks.

---

### ⚠️ Order Recommendation: Phase 3 before Phase 2

**The founder brief placed Phase 2 (personalization) before Phase 3 (monetization). I recommend reversing.**

Why:

1. **Monetization has no quality dependency** once Phase 1 is done.
2. **Partnership BD is slow** — 4–8 weeks each. Must run parallel with Phase 1.
3. **Personalization is an ROI trap early.** Data sparsity makes it unlearnable until 10K+ trips.
4. **Revenue funds quality.** Runway pressure compresses quality investment.

**Recommended order:** Phase 1 → Phase 3 → Phase 2 → Phase 4 → Phase 5.

---

### Phase 3 (recommended 2nd) — Monetization Unlocks (6–8 weeks, BD from Phase 1 week 1)

**Objectives:**

1. **Booking.com affiliate live:** obtain `BOOKINGCOM_AFFILIATE_ID`, flip registry default, verify end-to-end. Instrument commission tracking.
2. **Second hotel provider:** Agoda / MakeMyTrip / Cleartrip (redundancy + price comparison).
3. **Flight affiliate:** Skyscanner or Kiwi.com.
4. **Activity/experience affiliate:** GetYourGuide or Viator (top-50 Indian destinations).
5. **Pricing tiers:** Free (1 itinerary/month), Pro (unlimited + priority), Concierge (human touch-up, SLA). Razorpay (India).
6. **Funnel optimization:** use Phase 0 events, fix biggest leak in generate → save → book.
7. **Commission reconciliation:** partner-reported vs our recorded bookings.

**Sequencing:**

- BD starts Phase 1 week 1. Affiliate agreements signed by Phase 3 start.
- **Weeks 1–2:** Booking.com (prep done, just flip flag).
- **Weeks 3–4:** Second hotel + flight affiliate.
- **Weeks 5–6:** Activity affiliate + pricing tiers + Razorpay.
- **Weeks 7–8:** Reconciliation + funnel fixes.

**Success metrics:**

- ≥60% of bookings via real providers.
- First ₹ of real commission revenue.
- Unit economics: CAC vs (commission + subscription LTV).

**Stop rule:** Booking completion rate <60% or partner API breaks quality → halt. Revenue that breaks quality is net negative.

**Complexity:** Medium engineering, high BD/legal.

---

### Phase 2 (recommended 3rd) — Personalization & Memory (4–6 weeks)

**Objectives:**

1. **Trip-to-trip memory:** after trip 1, `UserProfile.embedding` updates from feedback + expense data. Trip 2 biases with this embedding.
2. **Preference learning:** implicit signals from `Feedback.corrections`, `ExpenseEntry` deltas, trip-editor edits.
3. **Second-trip delight:** onboarding surfaces "Based on your trip to Jaipur, here are three next destinations."
4. **Taste-maker cohorts:** cluster users; cold-start with cohort centroid.
5. **Guardrails:** personalization cannot violate Phase 1 filters.

**Sequencing:**

- **Weeks 1–2:** Signal collection — wire implicit feedback events.
- **Weeks 3–4:** Embedding update loop (Celery). Cohort clustering.
- **Weeks 5–6:** UI surfaces.

**Success metrics:**

- Second-trip conversion (user generates trip 2 within 90 days) > baseline.
- Personalization fidelity: +20% for users with >1 trip.
- No regression on other dimensions.

**Stop rule:** Second-trip conversion must be measurable. If no repeat users yet, wait.

**Complexity:** Medium. ML is commodity post-embeddings; UX is the hard part.

---

### Phase 4 — Growth & GTM (8–12 weeks, partially parallel with Phase 3)

**Objectives:**

1. **SEO programmatic:** template pages per (destination × traveler_type × duration × season). 190 × 5 × 4 × 4 = 15,200 pages. Long-tail targets: "4-day Kerala family trip monsoon."
2. **Blog expansion:** 23 → 200 posts, AI-assisted human-edited, internal linking hub-and-spoke.
3. **Sharing virality:** OpenGraph previews, WhatsApp/Twitter CTAs, "Fork this trip" pre-fills generator.
4. **Referral loop:** referrer gets 1 free Pro month per 3 successful signups.
5. **Mobile conversion:** split Phase 0 funnel by device; fix biggest mobile drop.
6. **Email lifecycle:** pre-trip countdown, post-trip review ask, abandoned-generation recovery.

**Sequencing:**

- **Weeks 1–4:** Programmatic SEO infra. Sitemap, schema.org, indexing.
- **Weeks 3–6:** Blog content sprint (parallel).
- **Weeks 5–8:** Sharing + referral.
- **Weeks 7–10:** Email lifecycle + mobile conversion.
- **Weeks 10–12:** Buffer + SEO indexation wait.

**Success metrics:**

- Organic traffic: 0 → baseline in 90 days, 10x in 6 months.
- Share → signup conversion measured.
- Referral k-factor >0.3.
- Mobile conversion parity with desktop (±10%).

**Stop rule:** SEO indexed but bounce >80% → content is thin. Stop scaling, improve quality.

**Complexity:** Medium.

---

### Phase 5 — Moat & Expansion (ongoing)

**Objectives:**

1. **Day-of intelligence:** real-time weather/crowd/event alerts via push + WhatsApp.
2. **Concierge layer:** human fallback for Pro users via Track B admin tools.
3. **Geographic expansion:** Sri Lanka, Bhutan, Nepal first. Then Thailand, Vietnam.
4. **B2B:** white-label dashboard for small travel agencies.
5. **Mobile app:** only after web conversion proven. React Native reusing components.
6. **Offline mode:** downloadable itinerary PDF/PWA offline pack.

**Stop rule:** Max 2 expansion vectors simultaneously.

---

## 5. Success Metrics (Founder-facing)

**Top-line (weekly):**

1. **Polished-itinerary rate** — % generations shipping non-template `trip_title` + complete `smart_insights`. North star for quality. Target ≥99.5%.
2. **Golden-set eval score** — aggregate 0–100 across 10 dimensions. Moves up over time. Tracks every deploy.
3. **Generate → Book conversion** — % of generations resulting in real (non-simulated) booking within 14 days. North star for revenue.
4. **Active unique users / week** — weekly unique generations, de-duped.
5. **Second-trip rate** — % users generating trip 2 within 90 days. North star for retention.
6. **NPS** — post-trip survey, target ≥50.

**Operational (daily):**

- p95 generation latency (<30s).
- Polish tier distribution (gemini / flash-lite / ollama / unpolished).
- Error envelope rate (ERR_*) by code.
- Gemini cost per itinerary (₹).

**Leading indicators of quality problems:**

- Unpolished rate trending up.
- Polish tier skewing Ollama (Gemini 429s rising).
- Closed-days violation rate >0.
- `Feedback.corrections` rate per trip trending up.

---

## 6. What NOT to Build (Explicit Anti-Goals)

Until Phase 1 exit metrics are green:

1. **No mobile native app.** PWA is fine.
2. **No crypto / Web3 / NFT travel passes.**
3. **No AI chatbot concierge.** Amplifies flaws.
4. **No "social network for travelers."**
5. **No geographic expansion beyond India.** 190 destinations is plenty.
6. **No user-generated itinerary marketplace.**
7. **No multi-language support.** English + Hinglish = 90% TAM.
8. **No corporate/B2B sales motion.**
9. **No VR/AR previews.**
10. **No voice mode.**
11. **No React/Flask/Tailwind major version bumps** during Phase 0–1.
12. **No engine architecture refactor.** Tweaks via eval loop, not rewrites.

---

## 7. 30 / 60 / 90 Day Milestones

### Day 30 (end of Phase 0 week 4)
- ≥50 golden prompts curated and reviewed.
- Eval harness runs all 10 dimensions.
- Polish-failure detector 100% on synthetic tests.
- `itinerary_qa` active gate in pipeline.
- Schema-drift CI green for 2 weeks.
- Baseline published for all 10 dimensions.
- Funnel events in `/api/metrics`.
- Booking.com BD outreach started.

### Day 60 (mid-Phase 1)
- Phase 0 signed off.
- Unpolished rate <1%.
- 100% destinations have embeddings.
- Top-500 attractions ≥90% coverage on key fields.
- A/B harness completed ≥3 experiments.
- Golden-set score: +8–10%.
- Booking.com terms signed or in final review.
- Founder dashboard reviewed weekly.

### Day 90 (end of Phase 1)
- All Phase 1 exit metrics green.
- Polished rate ≥99.5%.
- Closed-days violations: 0.
- Pacing outliers: <5%.
- Backtrack ratio p90: -20%.
- Golden-set aggregate: +15%.
- Schema drift: 0 for 4 weeks.
- Phase 3 (monetization) kicked off with Booking.com integration in progress.
- Phase 2 (personalization) on hold pending revenue + user volume.
- Demo-ready for investors: quality metric + improvement + methodology + revenue + roadmap.

---

## Relevant Files

**Engine (Phase 0–1 focus):**
- `backend/engine/filter_engine.py`
- `backend/engine/cluster_engine.py`
- `backend/engine/budget_allocator.py`
- `backend/engine/route_optimizer.py`
- `backend/engine/assembler.py`
- `backend/engine/orchestrator.py`

**Quality gates:**
- `backend/agents/itinerary_qa.py` (promote passive → active)
- `backend/tasks/quality_scorer.py` (surface results)
- `backend/services/gemini_service.py` (polish chain hardening)

**Data:**
- `backend/models.py` (schema reconciliation)
- `backend/scripts/generate_embeddings.py` (run on all)
- `backend/tasks/embedding_sync.py`

**Monetization (Phase 3):**
- `backend/services/booking_providers/registry.py` (flip default)

**Observability (Phase 0 funnel):**
- `backend/metrics.py` (the new `/api/metrics` endpoint)
- `backend/middleware/logging.py`

**Frontend (Phase 2/4):**
- `D:\Projects\AltairGO-Platform\src\pages\GeneratingPage.jsx`

---

## Opinionated Footnotes

- **Phase 2/3 order reversed.** Override only if you have 10K+ repeat users, which you don't.
- **If Gemini paid tier costs <₹15/itinerary, pay it.** Don't build fine-tuning infra to save money.
- **Biggest risk is not any item in the register** — it's founder patience with Phase 0. Six weeks of "building nothing users see" feels expensive. It is not. It is the foundation of every subsequent dollar.

---

**Status:** WAITING FOR CONFIRMATION
**Next action:** Founder approval → begin Phase 0 Week 1 (golden dataset + schema-drift CI)
