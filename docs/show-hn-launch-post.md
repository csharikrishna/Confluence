# Show HN: Confluence — A 10-in-1 coastal intelligence platform built to stop LLMs from hallucinating marine safety

**Live Platform:** [https://confluence-si41.onrender.com](https://confluence-si41.onrender.com)  
**Interactive Swagger Docs:** [https://confluence-si41.onrender.com/docs](https://confluence-si41.onrender.com/docs)  
**GitHub Repository:** [https://github.com/csharikrishna/Confluence](https://github.com/csharikrishna/Confluence)  
**MCP Server:** [https://github.com/csharikrishna/Confluence/tree/main/packages/confluence-mcp](https://github.com/csharikrishna/Confluence/tree/main/packages/confluence-mcp)  

---

### The Hook

A few weeks ago, while pair-programming with an advanced AI coding assistant to build a marine risk calculation engine, the AI generated a function calculating the Beaufort wind scale. It didn't just write the code — it included a confident, beautifully formatted docstring citing:

> *"World Meteorological Organization (WMO) Technical Commission for Marine Meteorology, Publication No. 522, Appendix III (1984)."*

It looked completely legitimate. But when I actually traced the primary literature, WMO Pub 522 is *not* the Beaufort specification (the internationally adopted Beaufort wind scale is governed by the WMO Manual on Marine Meteorological Services, WMO-No. 558, and Beaufort's original empirical naval observations). The AI had hallucinated an authentic-sounding publication number and appendix out of whole cloth.

That single moment crystallized the core problem of AI in physical domains: **when language models speak about physical safety, they don't hallucinate like a confused human; they fabricate with absolute academic confidence.**

If you ask ChatGPT or a standard RAG assistant whether an artisanal fisherman in Chennai can launch his small boat today, or if severe wave swell is approaching Kochi, the model will answer authoritatively. But its knowledge is either based on training-data priors or, worse, retrieved from stale PDF reports from 3 weeks ago.

---

### The Core Finding: Why RAG Fails in Physical Systems

Retrieval-Augmented Generation (RAG) is celebrated as the universal cure for LLM hallucinations. But when we benchmarked naive vector-RAG against live environmental telemetry, we discovered an alarming failure mode:

**RAG doesn't hallucinate on stale data — it accurately retrieves real historical documents that are completely, dangerously false right now.**

In one of our benchmark runs on a severe particulate spike in Visakhapatnam, the vector database pulled a verified government air monitoring report from 14 days earlier when the air was pristine. The LLM summarized the retrieved document with 100% fidelity: *"The air quality is excellent and conditions are safe for outdoor recreation."* In reality, live ground sensors were measuring toxic PM2.5 levels exceeding $168\ \mu\text{g}/\text{m}^3$. The system was factual about the past, and actively hazardous to someone breathing the air today.

---

### What Confluence Actually Is

Confluence is an open-source, normalized environmental intelligence API and full-stack platform that aggregates **50+ physical hyperparameters across 10 free, independent public data feeds** into a single validated JSON snapshot in ~2.4 seconds, then applies deterministic physics equations and multi-hazard tracking:

1. **Atmospheric Weather** (Open-Meteo Weather): Temp, humidity, surface pressure, wind gusts, dew point.
2. **Marine Hydrodynamics** (Open-Meteo Marine): Significant wave height, swell wave direction, period, surface ocean currents.
3. **Dual-Tier Air Quality**:
   * *Primary*: OpenAQ Ground Sensor Array (physical PM2.5, PM10, $O_3$, $NO_2$, $SO_2$, CO).
   * *Fallback*: Open-Meteo European CAMS atmospheric model with honest provenance tagging (`"data_type": "modeled"` vs `"data_type": "measured"`).
4. **River Flood & Estuarine Discharge** (Copernicus GloFAS): Real-time river discharge ($m^3/s$) for compound estuarine flooding (e.g. Hooghly / Sundarbans delta).
5. **Solar & Marine Ephemeris** (Sunrise-Sunset.org): Civil/nautical twilight, solar noon, daylight length.
6. **Coastal Topography & Elevation** (Open-Elevation): True elevation ($m$ above sea level) for surge inundation vulnerability.
7. **Climate Baseline Normals** (NASA POWER): Historical seasonal normals and baseline temperature deltas.
8. **Seismic & Tsunami Hazard** (USGS Earthquake Hazards): Real-time global seismic feeds tracking shallow-focus (<70km) offshore seismic events.
9. **Tropical Cyclone Tracking** (GDACS — UN/JRC): Real-time active tropical cyclone coordinates, sustained wind speeds, and geodesic proximity tracking ($<500\text{ km}$ critical danger).
10. **Fire & Smoke Causality** (NASA FIRMS): Satellite thermal anomaly detection (VIIRS/MODIS) providing upstream physical causality (agricultural/biomass burning) for sudden PM2.5 spikes within $300\text{ km}$.

---

### Physics-Grounded Reasoning Layer (No Black Boxes)

Rather than feeding raw telemetry to an LLM and hoping it does math correctly, Confluence computes composite signals using cited scientific standards before the model ever sees the data:
* **Heat Index**: NOAA / Rothfusz 9-term polynomial regression with high/low humidity adjustments.
* **Dew Point & Fog Risk**: Magnus-Tetens approximation.
* **Sea State & Small Craft Safety**: NWS Coastal Marine warning thresholds (Small Craft Advisory $\rightarrow$ Gale $\rightarrow$ Storm $\rightarrow$ Hurricane Force).
* **Storm Potential**: Latitude-normalized pressure-fall criteria (Bergeron / Sanders-Gyakum rapid cyclogenesis).
* **Compound Estuarine Flood Risk**: Inverse barometer effect (~1cm sea level rise per 1 hPa pressure drop) combined with GloFAS river basin discharge.

---

### AI Integration: Model Context Protocol (MCP)

To ground frontier AI agents in live coastal truth, we built and verified [`packages/confluence-mcp`](https://github.com/csharikrishna/Confluence/tree/main/packages/confluence-mcp) — a native Model Context Protocol server.

*MCP is an open standard originated by Anthropic*, and works natively with Claude Desktop, Claude Code, Cursor, Zed, and Cline. It exposes 5 deterministic tools:
* `get_coastal_snapshot`: Returns validated 10-feed telemetry for any `lat`/`lon`.
* `get_preset_locations`: Lists registered coastal stations across India's South, West, and East coasts.
* `check_coastal_alerts`: Evaluates active safety alerts against threshold and 24h trend rules.
* `get_historical_trends`: Returns 24h parameter deltas.
* `ask_coastal_assistant`: Queries the grounded decision support engine.

---

### Try It Live

* **Explore the Web Interface**: [https://confluence-si41.onrender.com](https://confluence-si41.onrender.com) (try the live inquiry bar on the hero).
* **Swagger API Docs**: [https://confluence-si41.onrender.com/docs](https://confluence-si41.onrender.com/docs)
* **Upstream Health & Latency**: [https://confluence-si41.onrender.com/#health](https://confluence-si41.onrender.com/#health)
* **Generate a Developer Key**: [https://confluence-si41.onrender.com/#developer](https://confluence-si41.onrender.com/#developer)

I’d love honest feedback on the physical derivation equations, the dual-tier air quality fallback architecture, and how you think about grounding LLMs in dynamic physical sensor streams.
