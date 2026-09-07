# Confluence — Phase 4: 10-Day Correlation & ML Insight Layer

## What this is

A time-boxed, 10-day data collection window with genuinely reliable hourly ingestion, followed by a two-stage analysis: statistical correlation first (appropriate for the sample size you'll actually have), then lightweight ML feature-importance modeling once there's enough data to support it. The output feeds into the LLM as a new, clearly-labeled "observed pattern" layer — not a black-box prediction.

**This deliberately reopens the "no ML" guardrail from the Phase 2 doc.** That was the right call before real history existed. It's a good call to revisit now, as a deliberate decision.

---

## Part 1: Fix the ingestion reliability problem first

GitHub Actions' free-tier scheduler is not reliable enough for this — you've already proven it lands every 3-5h instead of hourly, which would make "10 days" actually ~50-70 samples per location, not ~240.

**Fix: use a dedicated external cron service, not GitHub Actions, not your own laptop.**

- Your laptop staying on and connected for 10 straight days isn't realistic — don't depend on it.
- Use a free external scheduling service (e.g. **cron-job.org**, or similar) configured to hit your live Render endpoint every hour for exactly 10 days.
- Point it at something like `GET https://confluence-si41.onrender.com/environment?lat=X&lon=Y&bypass_cache=true` for each of your 5 registered locations (5 separate scheduled jobs, or one job that loops through `/locations` and hits all 5 — whichever your agent finds simpler to wire up reliably).
- This is fully decoupled from your machine and from GitHub's scheduler quirks — it hits your public API exactly like any other client would.

**Target after 10 days:** ~240 real hourly snapshots per location (~1,200 total across all 5) — enough to make correlation analysis meaningful, and borderline-enough for a very lightweight ML step.

**Don't touch the existing `ingest_history.yml` GitHub Actions cron** — leave it running as-is for ongoing Phase 2 history. This new external cron is a *parallel, temporary, denser* collection specifically for this 10-day analysis window; both can write to the same store without conflict since `save_snapshot` is idempotent-safe on distinct timestamps.

---

## Part 2: Analysis, in two stages

### Stage 1 — Correlation matrix (do this first, appropriate for this sample size)

- Pull the 10-day window from `/environment/history` (or directly from Mongo) per location
- Compute **Pearson and Spearman correlation** across the key variables you already have: temperature, humidity, PM2.5, wave height, wind speed, pressure, heat index, and any other derived insight fields
- Report **both the correlation coefficient and sample size (n)** for every pair — never show a correlation number without its n
- **Flag but do not hide weak/noisy results** — with ~240 samples this is workable, but still small enough that spurious correlations from testing many pairs at once (multiple comparisons) are a real risk. Apply a basic correction (even just noting p-values and being conservative about what counts as "real") rather than reporting every raw correlation as a finding.

### Stage 2 — Lightweight ML (only after Stage 1, only if there's a real signal worth modeling)

- Pick 2-3 meaningful **target variables** to explain — e.g. what predicts heat index spikes, what predicts PM2.5 spikes, what predicts the small-craft-risk score
- Use **Random Forest feature importance** (or similar simple, interpretable method) — not deep learning, not anything requiring more data than you'll actually have
- Output: a ranked list of "what features matter most for predicting X," with the model's own confidence/error bounds shown honestly, not hidden

---

## Part 3: Tying it into the LLM (the "cook" part)

- Add a new field to the unified schema — e.g. `meta.statistical_patterns` — populated only once enough data exists (don't show anything until a minimum sample threshold, e.g. n≥30, is met)
- Each entry must include: the pattern description, **n**, the correlation/importance value, and **explicit uncertainty language** — e.g. *"Observed statistical association (n=240, r=0.62) — not a confirmed causal relationship."*
- Feed this into the chatbot's grounding context alongside the existing physics-derived insights, so the LLM can reference real observed patterns from your own accumulated data — genuinely something ChatGPT/generic tools can't do, since they have no access to your live history at all

**Guardrail, given this project's track record with confidently-stated-but-wrong claims:** the LLM must never be allowed to state a correlation as causation, and must always surface the n and confidence when citing a statistical pattern. This is the same discipline as the WMO citation lesson — a small, honest number beats a confident, unqualified one.

---

## Explicitly out of scope for this pass

- No deep learning, no time-series forecasting models (that's a meaningfully bigger, different problem than correlation — a future phase if ever)
- No claims of causation, ever — correlation only, clearly labeled
- No permanent architecture changes — this is a bounded 10-day experiment; decide afterward whether it's worth making a permanent pipeline

## What "done" looks like

- [ ] External cron confirmed firing reliably, hourly, for the full 10 days (spot-check a few times during the window, don't just trust it silently)
- [ ] ~240 real samples per location collected
- [ ] Correlation matrix computed and reviewed for genuine vs. likely-spurious patterns
- [ ] At least one Random Forest feature-importance result, with honest uncertainty reporting
- [ ] `statistical_patterns` field live in the schema, gated on minimum sample size
- [ ] Chatbot demonstrably references a real observed pattern from your own data in at least one test conversation
