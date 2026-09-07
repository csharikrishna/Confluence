# Confluence Model Context Protocol (MCP) Server

[![MCP Standard](https://img.shields.io/badge/MCP-Standard-blue.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-%3E%3D18.0.0-green.svg)](https://nodejs.org/)

An official **Model Context Protocol (MCP)** server providing compatible AI environments (**Anthropic Claude Desktop, Claude Code, Cursor, Zed, Cline**) with direct, authoritative access to the **Confluence Coastal Environmental Intelligence Platform**.

Confluence connects AI agents to **10 concurrent scientific feeds** (weather, ocean/marine, air quality, river basin hydrology & flood, GDACS tropical cyclone tracking, NASA FIRMS active fire/hotspots, astronomical, terrain, climate baseline, seismic) normalized into a single, sub-second snapshot with **deterministic physics derivations** (NOAA Heat Index, Magnus-Tetens dew point, WMO Beaufort force, IMD cyclone scales, inverse barometer storm surge, compound estuarine flooding, GDACS cyclone advisories, NASA FIRMS smoke causality, and Bergeron pressure fall criteria).

*(Note on client ecosystem: MCP is an open protocol specification originated by Anthropic and supported by native MCP clients like Claude Desktop, Cursor, and Zed. It is distinct from OpenAI's proprietary Assistants / Custom GPTs API).*

---

## Quickstart: Claude Desktop

Add this configuration to your Claude Desktop config file:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "confluence": {
      "command": "npx",
      "args": ["-y", "confluence-mcp"],
      "env": {
        "CONFLUENCE_API_KEY": "conf_live_YOUR_API_KEY",
        "CONFLUENCE_API_URL": "https://confluence-si41.onrender.com"
      }
    }
  }
}
```

*Note: If you are testing locally against a local Confluence instance, set `"CONFLUENCE_API_URL": "http://localhost:8000"`.*

---

## Quickstart: Cursor

In your workspace root, create or edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "npx",
      "args": ["-y", "confluence-mcp"],
      "env": {
        "CONFLUENCE_API_KEY": "conf_live_YOUR_API_KEY"
      }
    }
  }
}
```

---

## Getting an API Key

1. Visit the Confluence Developer Portal at [https://confluence-si41.onrender.com](https://confluence-si41.onrender.com) (or your local deployment).
2. Register a developer account.
3. Generate an API Key (starts with `conf_live_`).
4. Paste it into your `CONFLUENCE_API_KEY` configuration.

*(The server also functions without an API key, but will be subject to the anonymous rate limit of 30 requests/minute. Authenticated keys receive 100 requests/minute).*

---

## Available MCP Tools

Frontier models can autonomously invoke the following 5 tools:

### 1. `get_coastal_snapshot`
Fetches the complete 10-in-1 real-time environmental snapshot with calculated physics metrics:
- **Parameters:**
  - `latitude` (number, required): -90 to 90
  - `longitude` (number, required): -180 to 180
  - `location_name` (string, optional): e.g. "Chennai Coast"
- **Returns:**
  - Full atmospheric, oceanographic, air quality, river flood, cyclone tracking, active fire hotspots, solar, and seismic parameters.
  - Calculated physical metrics: NOAA Heat Index Category, Magnus-Tetens Dew Point, WMO Beaufort Scale force, Small Craft Advisory status, GDACS Tropical Cyclone proximity alert, NASA FIRMS biomass burning attribution, Inverse Barometer Storm Surge (cm), and 24h rapid pressure drop.

### 2. `get_preset_locations`
Lists pre-configured coastal observatories across India's South, West, and East coasts (Chennai, Mumbai, Kochi, Visakhapatnam, Kolkata/Sundarbans).
- **Parameters:** None.
- **Returns:** Markdown table of stations, coordinates, and regional characteristics.

### 3. `check_coastal_alerts`
Audits active environmental threshold alerts and hazard classifications for a set of coordinates.
- **Parameters:**
  - `latitude` (number)
  - `longitude` (number)
- **Returns:** Active safety warnings, small-craft risk levels, cyclone categories, and storm surge levels.

### 4. `get_historical_trends`
Compares current readings against 24-hour historical records to evaluate changing coastal regimes.
- **Parameters:**
  - `latitude` (number)
  - `longitude` (number)
- **Returns:** 24-hour deltas for temperature, surface pressure, humidity, wind speed, wave height, and PM2.5.

### 5. `ask_coastal_assistant`
Queries Confluence's sensor-grounded Coastal Assistant chatbot.
- **Parameters:**
  - `query` (string, required): The operational or scientific question.
  - `location_name` (string, optional): Grounding location (e.g. "Mumbai").
- **Returns:** Expert, sensor-grounded maritime guidance synthesized with verified guidelines.

---

## MCP Resources

AI models can inspect static reference context:
- `confluence://locations`: Dynamic JSON list of all coastal stations.
- `confluence://methodology`: Reference markdown documenting the physical regressions and standards used (NOAA, WMO, IMD, NWS, Bergeron criterion).

---

## MCP Prompt Templates

Pre-built operational prompts ready for AI agent workflows:
- `coastal-safety-audit`: Complete harbor and vessel departure safety audit.
- `cyclone-readiness-check`: Cyclone depression, rapid pressure drop, and storm surge risk assessment.

---

## Local Development & Testing

To run or test locally:

```bash
cd packages/confluence-mcp
npm install
npm test
```

To run manually over stdio:
```bash
node bin/cli.js
```
