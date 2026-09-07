# Confluence — Shaping & Launch Prep

No new features from here. This is entirely about making what already exists feel good and honest, then shipping it. Work through these roughly in order — each one is cheap and catches something the next one would otherwise expose.

---

## 1. Copy & Accuracy Sweep (do this first — cheapest, highest embarrassment-prevention)

Go through every place these numbers/claims appear (README, landing page, footer, MCP resource descriptions, walkthrough docs) and confirm they're current:

- [ ] Source count says **11**, not 7 or 9 (stale from earlier phases)
- [ ] "South Indian locations" language replaced with something accurate (5 coastal locations across South, West, and East India — or just name the cities)
- [ ] Latency stat shows both cold and cached numbers, not just the flattering "<1ms" alone
- [ ] Any "0.0% hallucination" language still reads as the softened, scoped version ("no grounding errors observed across N regimes"), not a blanket guarantee
- [ ] Test count badge matches the actual current `pytest` output (these drift every time you add tests — check it's not stale again)
- [ ] RAG benchmark numbers/table match what's actually in `rag_vs_confluence_results.json` right now
- [ ] Nothing anywhere claims "works with ChatGPT" — MCP is Anthropic/partner-ecosystem, not universal (flagged earlier, confirm it's fixed if it was ever written down anywhere)

## 2. UI/UX Polish

Go through the actual experience as a stranger would, not as the person who built it:

- [ ] **Landing page**: does the hero section explain what this *does* in one sentence a non-technical person understands, before it explains the architecture?
- [ ] **Chatbot**: is response formatting clean (markdown rendering correctly, no raw JSON dumped unless the user wants to inspect it)? Is there a visible "what data was this grounded in" affordance, since that's your actual differentiator?
- [ ] **Mobile**: does the whole site actually work on a phone — nav, chatbot drawer, developer portal forms? This matters a lot for Show HN/Reddit traffic, which is majority mobile-first browsing even when the tool itself is dev-facing
- [ ] **Loading/empty/error states**: what does a user see while a cold request is fetching (2.6s isn't instant — is there a visible loading state, or does it look frozen)? What happens if they ask the chatbot something with zero registered-location match?
- [ ] **Developer Portal**: is the code-snippet generator (cURL/Python/JS) actually copy-pasteable and correct right now, given everything that's changed since it was built?

## 3. First 30 Seconds

This is the single highest-leverage thing for a cold visitor from Show HN/Reddit:

- [ ] Can someone understand *and try* the core value (ask a real coastal question, get a grounded answer) within 30 seconds of landing, without reading documentation first?
- [ ] Consider: does the landing page need a live, no-signup-required mini version of the chatbot right on the homepage, rather than requiring a click into a separate tab? First-impression friction kills curious-but-not-committed visitors.
- [ ] Is there one clear, honest sentence somewhere near the top that states the actual differentiator — "grounded in live sensor data across 11 sources, not static training data" — without needing to read the RAG benchmark table to understand why that matters?

## 4. The Launch Post (do this last, after the above)

Write it around the real story, not a generic feature list. The strongest material you have:

- **The honest hook**: while building this, your own AI coding assistant fabricated a specific, confident, wrong citation to a real standards document — you caught it, verified against the primary source, and disclosed it. That's a better opener than any stat.
- **The core finding**: RAG doesn't hallucinate on stale data, it confidently states *wrong current facts from real old documents* — and in your own benchmark, that once caused a system to actively tell someone a toxic air event was safe. That's the most concrete, alarming, memorable finding you have.
- **The proof, not the pitch**: link the live URL, the repo, and the benchmark doc — let people poke at it themselves rather than asking them to trust a summary.
- **Keep it honest about scope**: this is a working prototype with real engineering behind it, not a funded company — undersell rather than oversell, technical audiences respond better to "here's what I built and what I found" than to marketing language.

**Where to post**: Show HN first (technical audience most likely to actually read the benchmark methodology and appreciate the honesty), then r/webdev or r/opensource, then LinkedIn with a shorter version pointing back to the full post.

---

## What "done" looks like

- [ ] Every stale number/claim fixed
- [ ] Someone unfamiliar with the project can use it successfully on mobile within 30 seconds
- [ ] Launch post drafted, reviewed, and posted
