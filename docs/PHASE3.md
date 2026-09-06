# Confluence — Phase 3: Minimal Chatbot Interface

## What this is

A thin wrapper — not a product. Takes a plain-language question, resolves it to one of your 5 registered locations, calls your existing `/environment` + `/alerts` endpoints, hands the result to an LLM as grounding context, and returns a plain-language answer.

This is the literal proof of the original thesis from Day 1: *"the chatbot is only the interface, not the system."* You already built the system. This is just finally wiring up the interface.

**Explicit non-goals** (resist adding these — this is intentionally small):
- No multi-turn conversation memory
- No free-text location parsing/geocoding — just match against your 5 registered names
- No new UI framework — a single HTML page with vanilla JS, or even a CLI script, is enough
- No new data sources, no new derived insights — pure consumption of what already exists

## Architecture

```
User question (text)
      ↓
Location match (string match against locations.json — "chennai", "kochi", etc.)
      ↓
Call your own live API: GET /environment?lat=X&lon=Y  +  GET /alerts?lat=X&lon=Y
      ↓
Build one prompt: [system instructions] + [unified JSON] + [user's question]
      ↓
Call LLM (reuse nvidia_grounding_client.py pattern — you already have this working)
      ↓
Return answer to user
```

## Build steps

1. **Location matching** — a simple function: lowercase the user's message, check if any registered location name (or an obvious alias — "chennai," "madras") appears in it. If none match, default to asking which location, or pick the first as a fallback for v1.

2. **Prompt template** — reuse almost exactly what you used in the Phase 1 grounding tests:
   ```
   You are a coastal conditions assistant. Use ONLY the data below to answer.
   If the data doesn't cover something, say so — don't guess.

   [insert full /environment + /alerts JSON here]

   User question: {question}
   ```

3. **LLM call** — reuse `nvidia_grounding_client.py` as-is, or make it swappable (env var for provider) since you mentioned Gemini as a possible second option later — but don't build that abstraction until you actually need a second provider.

4. **Interface** — pick ONE:
   - Simplest: a CLI script (`python chat.py "is it safe to fish near Kochi"`) — fastest to build, fine for a demo video/GIF
   - Slightly more: a single-file HTML page with a text box, calling a small new FastAPI route (`POST /ask`) that does steps 1-3 server-side
   
   Recommend the HTML version — it's still small, but it's the difference between "a script I ran" and "a thing someone else can actually try."

5. **New endpoint on your existing API**: `POST /ask` — body: `{"question": "..."}`. Internally does the location match → fetch → prompt → LLM call → returns `{"answer": "...", "location_used": "...", "grounding_data": {...}}`. Returning the raw grounding data alongside the answer is a nice trust-building touch — let the user see what it was actually grounded in.

## What "done" looks like

- [ ] Can ask "is it safe to fish near Chennai right now" and get a real, grounded, correct answer
- [ ] Can ask about a location with an active alert and have the chatbot surface it unprompted (test against Mumbai if its PM2.5/wave alert is still live)
- [ ] Works via the HTML page, not just a terminal
- [ ] One clear failure mode tested: ask about a location NOT in your registry — confirm it fails gracefully (asks for clarification or lists available locations), doesn't crash or hallucinate

## Explicitly out of scope for this pass

- Conversation history / follow-up questions
- Voice input, mobile app, anything beyond a single web page
- Location resolution smarter than string matching
- Streaming responses (a full response is fine for v1)

If any of these feel necessary mid-build — stop, that's Phase 4, not this.