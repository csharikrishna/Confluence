import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const DEFAULT_API_URL = "https://confluence-si41.onrender.com";

/**
 * Normalizes base API URL and removes trailing slashes
 */
function getApiUrl() {
  const url = process.env.CONFLUENCE_API_URL || DEFAULT_API_URL;
  return url.replace(/\/+$/, "");
}

/**
 * Returns optional API key from environment
 */
function getApiKey() {
  return process.env.CONFLUENCE_API_KEY || "";
}

/**
 * Unified fetch wrapper with error handling and authentication
 */
async function fetchConfluence(endpoint, options = {}) {
  const baseUrl = getApiUrl();
  const apiKey = getApiKey();
  const url = `${baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers = {
    "Accept": "application/json",
    "User-Agent": "Confluence-MCP-Server/1.0.0",
    ...(options.headers || {})
  };

  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers
    });

    if (!response.ok) {
      let errorBody = "";
      try {
        const errJson = await response.json();
        errorBody = errJson.message || errJson.error || JSON.stringify(errJson);
      } catch {
        errorBody = await response.text();
      }
      throw new Error(`Confluence API returned HTTP ${response.status}: ${errorBody}`);
    }

    return await response.json();
  } catch (err) {
    if (err.name === "TypeError" && err.message.includes("fetch")) {
      throw new Error(`Unable to connect to Confluence API at ${baseUrl}. Ensure the server is reachable.`);
    }
    throw err;
  }
}

/**
 * Initializes and starts the Confluence MCP Server
 */
export async function main() {
  const server = new McpServer({
    name: "confluence",
    version: "1.0.0"
  });

  // --------------------------------------------------------------------------
  // TOOL 1: get_coastal_snapshot
  // --------------------------------------------------------------------------
  server.tool(
    "get_coastal_snapshot",
    "Fetches authoritative 7-in-1 real-time coastal environmental snapshot for given coordinates, normalized from Open-Meteo, Copernicus/Marine, OpenAQ, Sunrise-Sunset, NASA POWER, Elevation, and USGS Seismic feeds, with deterministic physical calculations.",
    {
      latitude: z.number().min(-90).max(90).describe("Geographic latitude (-90 to 90)"),
      longitude: z.number().min(-180).max(180).describe("Geographic longitude (-180 to 180)"),
      location_name: z.string().optional().describe("Optional friendly name for the location (e.g. 'Chennai Coast', 'Mumbai Harbor')")
    },
    async ({ latitude, longitude, location_name }) => {
      const q = new URLSearchParams({
        lat: latitude.toString(),
        lon: longitude.toString()
      });
      if (location_name) {
        q.set("name", location_name);
      }

      const data = await fetchConfluence(`/environment?${q.toString()}`);
      const weather = data.weather || {};
      const marine = data.marine || {};
      const air = data.air_quality || {};
      const astro = data.astronomical || {};
      const meta = data.meta || {};
      const derived = meta.derived_insights || {};
      const alerts = meta.active_alerts || [];
      const trend = meta.trend_24h || {};

      let report = `# Coastal Environmental Snapshot: ${data.location?.name || `${latitude}, ${longitude}`}\n`;
      report += `**Generated At:** ${data.generated_at} | **Cache Status:** ${meta.cache_hit ? "Hit (< 1ms)" : "Live Ingest"}\n\n`;

      report += `### 1. Atmospheric & Weather Conditions\n`;
      report += `- **Temperature:** ${weather.temperature_c ?? "N/A"} °C\n`;
      report += `- **Relative Humidity:** ${weather.relative_humidity_pct ?? "N/A"} %\n`;
      report += `- **Surface Pressure:** ${weather.surface_pressure_hpa ?? "N/A"} hPa\n`;
      report += `- **Sustained Wind Speed:** ${weather.wind_speed_kmh ?? "N/A"} km/h\n`;
      report += `- **Wind Gusts:** ${weather.wind_gusts_kmh ?? "N/A"} km/h\n`;
      report += `- **Precipitation:** ${weather.precipitation_mm ?? 0} mm\n`;
      report += `- **Weather Code / Condition:** ${weather.weather_code ?? "Normal"}\n\n`;

      report += `### 2. Marine & Oceanographic Conditions\n`;
      report += `- **Significant Wave Height:** ${marine.significant_wave_height_m ?? "N/A"} m\n`;
      report += `- **Wave Direction:** ${marine.wave_direction_deg ?? "N/A"}°\n`;
      report += `- **Wave Period:** ${marine.wave_period_s ?? "N/A"} s\n`;
      report += `- **Sea Water Temperature:** ${marine.sea_water_temperature_c ?? "N/A"} °C\n\n`;

      report += `### 3. Air Quality & Particulates\n`;
      report += `- **PM2.5:** ${air.pm25 ?? "N/A"} µg/m³\n`;
      report += `- **PM10:** ${air.pm10 ?? "N/A"} µg/m³\n`;
      report += `- **Air Quality Category:** ${air.air_quality_category ?? "Unknown"}\n\n`;

      report += `### 4. Solar, Astronomical & Terrain\n`;
      report += `- **UV Index:** ${astro.uv_index ?? "N/A"}\n`;
      report += `- **Sunrise / Sunset:** ${astro.sunrise_time ?? "N/A"} / ${astro.sunset_time ?? "N/A"}\n`;
      report += `- **Elevation:** ${data.terrain?.elevation_m ?? "Sea Level"} m\n\n`;

      report += `### 5. Deterministic Physics Insights (Peer-Reviewed Regressions)\n`;
      report += `- **NOAA Heat Index:** ${derived.heat_index_c ?? "N/A"} °C (Category: **${derived.heat_index_category ?? "Normal"}**)\n`;
      report += `- **Magnus-Tetens Dew Point:** ${derived.dew_point_c ?? "N/A"} °C\n`;
      report += `- **WMO Beaufort Scale:** Force ${derived.beaufort_scale?.force ?? "N/A"} (*${derived.beaufort_scale?.name ?? "N/A"}*)\n`;
      report += `- **IMD Cyclone Classification:** ${derived.imd_cyclone_category ?? "None (Sub-cyclonic)"}\n`;
      report += `- **Small Craft Warning Level:** **${derived.small_craft_risk_level?.toUpperCase() ?? "NONE"}**\n`;
      if (derived.small_craft_risk_detail) {
        report += `  - Reason: ${derived.small_craft_risk_detail.reason || "Wind/waves within normal navigational thresholds"}\n`;
      }
      report += `- **Inverse Barometer Storm Surge:** ${derived.coastal_flood_risk?.inverse_barometer_surge_cm ?? 0} cm sea surface elevation\n`;
      report += `- **Bergeron Rapid Pressure Fall (24h):** ${derived.rapid_pressure_fall?.change_24h_hpa ?? 0} hPa drop (Threshold: ${derived.rapid_pressure_fall?.latitude_normalized_threshold_hpa ?? "N/A"} hPa)\n\n`;

      report += `### 6. Active Physical Alerts\n`;
      if (alerts.length === 0) {
        report += `✅ **No active hazard warnings.** All environmental indicators within baseline limits.\n`;
      } else {
        for (const a of alerts) {
          report += `⚠️ **[${a.severity?.toUpperCase() || "WARNING"}] ${a.title || a.rule_id}**: ${a.description || a.message}\n`;
        }
      }

      return {
        content: [
          {
            type: "text",
            text: report
          },
          {
            type: "text",
            text: `\nRAW DATA JSON:\n${JSON.stringify(data, null, 2)}`
          }
        ]
      };
    }
  );

  // --------------------------------------------------------------------------
  // TOOL 2: get_preset_locations
  // --------------------------------------------------------------------------
  server.tool(
    "get_preset_locations",
    "Returns the list of verified, pre-configured coastal observatories in the Confluence platform (e.g., Chennai, Mumbai, Kochi, Visakhapatnam, Kolkata/Sundarbans, Goa, Mangalore) with latitude, longitude, and marine characteristics.",
    {},
    async () => {
      const res = await fetchConfluence("/locations");
      const locations = Array.isArray(res) ? res : (res.locations || []);
      let text = `# Pre-Configured Coastal Observatories\n\n`;
      text += `| Location Name | Latitude | Longitude | Coastal Characteristic |\n`;
      text += `|---|---|---|---|\n`;

      for (const loc of locations) {
        text += `| **${loc.name}** | ${loc.lat} | ${loc.lon} | ${loc.description || loc.region || "Coastal marine station"} |\n`;
      }

      return {
        content: [
          {
            type: "text",
            text
          }
        ]
      };
    }
  );

  // --------------------------------------------------------------------------
  // TOOL 3: check_coastal_alerts
  // --------------------------------------------------------------------------
  server.tool(
    "check_coastal_alerts",
    "Evaluates physics-informed coastal alerts and hazard conditions for specific coordinates. Checks for heat stress, small craft advisories, gale squalls, cyclone depressions, and storm surge risks.",
    {
      latitude: z.number().min(-90).max(90),
      longitude: z.number().min(-180).max(180)
    },
    async ({ latitude, longitude }) => {
      const q = new URLSearchParams({
        lat: latitude.toString(),
        lon: longitude.toString()
      });
      const data = await fetchConfluence(`/environment?${q.toString()}`);
      const derived = data.meta?.derived_insights || {};
      const alerts = data.meta?.active_alerts || [];

      let out = `# Coastal Safety & Alert Audit: ${data.location?.name || `${latitude}, ${longitude}`}\n\n`;

      if (alerts.length > 0) {
        out += `## 🚨 Active Environmental Alerts (${alerts.length})\n`;
        alerts.forEach((alert, idx) => {
          out += `${idx + 1}. **${alert.title || alert.rule_id}** [${alert.severity?.toUpperCase() || "ALERT"}]\n`;
          out += `   - ${alert.description || alert.message}\n`;
        });
        out += "\n";
      } else {
        out += `## ✅ All Safety Clear\nNo active threshold alerts are currently triggered.\n\n`;
      }

      out += `## Physical Risk Indices:\n`;
      out += `- **Small Craft Advisory:** ${derived.small_craft_risk_level?.toUpperCase() || "NONE"}\n`;
      out += `- **Heat Index Danger:** ${derived.heat_index_category || "NORMAL"} (${derived.heat_index_c || "N/A"} °C)\n`;
      out += `- **Cyclone Category:** ${derived.imd_cyclone_category || "None"}\n`;
      out += `- **Storm Surge (Inverse Barometer):** ${derived.coastal_flood_risk?.inverse_barometer_surge_cm || 0} cm\n`;
      out += `- **Rapid Pressure Fall (24h):** ${derived.rapid_pressure_fall?.rapid_fall ? "YES ⚠️ (Depression Warning)" : "Normal"}\n`;

      return {
        content: [{ type: "text", text: out }]
      };
    }
  );

  // --------------------------------------------------------------------------
  // TOOL 4: get_historical_trends
  // --------------------------------------------------------------------------
  server.tool(
    "get_historical_trends",
    "Fetches 24-hour physical deltas and trends (temperature, barometric pressure, wind speed, wave height, PM2.5) for a coastal station to detect storm approach or changing marine regimes.",
    {
      latitude: z.number().min(-90).max(90),
      longitude: z.number().min(-180).max(180)
    },
    async ({ latitude, longitude }) => {
      const q = new URLSearchParams({
        lat: latitude.toString(),
        lon: longitude.toString()
      });
      const data = await fetchConfluence(`/environment?${q.toString()}`);
      const trend = data.meta?.trend_24h || {};

      let out = `# 24-Hour Environmental Trends: ${data.location?.name || `${latitude}, ${longitude}`}\n\n`;
      out += `| Parameter | Current Value | 24h Previous | 24h Delta |\n`;
      out += `|---|---|---|---|\n`;

      const formatDelta = (param, unit) => {
        const item = trend[param];
        if (!item) return `| ${param} | N/A | N/A | N/A |\n`;
        return `| **${param}** | ${item.current} ${unit} | ${item.previous} ${unit} | **${item.change}** |\n`;
      };

      out += formatDelta("temperature_c", "°C");
      out += formatDelta("pressure_hpa", "hPa");
      out += formatDelta("humidity_pct", "%");
      out += formatDelta("wind_speed_kmh", "km/h");
      out += formatDelta("wave_height_m", "m");
      out += formatDelta("pm25", "µg/m³");
      out += formatDelta("uv_index", "");

      const rapidFall = data.meta?.derived_insights?.rapid_pressure_fall;
      if (rapidFall) {
        out += `\n**Barometric Tendency Analysis:**\n`;
        out += `- 24h Change: ${rapidFall.change_24h_hpa} hPa\n`;
        out += `- Latitude-Normalized Bergeron Threshold: ${rapidFall.latitude_normalized_threshold_hpa} hPa\n`;
        out += `- Rapid Fall Status: ${rapidFall.rapid_fall ? "⚠️ RAPID DROP DETECTED" : "Steady/Normal"}\n`;
      }

      return {
        content: [{ type: "text", text: out }]
      };
    }
  );

  // --------------------------------------------------------------------------
  // TOOL 5: ask_coastal_assistant
  // --------------------------------------------------------------------------
  server.tool(
    "ask_coastal_assistant",
    "Queries Confluence's sensor-grounded Coastal Assistant chatbot. Synthesizes real-time environmental telemetry with verified maritime guidelines.",
    {
      query: z.string().describe("User's analytical or operational marine query (e.g. 'Is it safe to sail a small craft off Chennai today?')")
    },
    async ({ query }) => {
      const payload = { question: query };

      const res = await fetchConfluence("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      let out = `### Coastal Assistant Response\n\n${res.answer || res.response || JSON.stringify(res)}\n\n`;
      if (res.location_matched) {
        out += `*Grounded to station: ${res.location_matched}*\n`;
      }
      if (res.active_alerts && res.active_alerts.length > 0) {
        out += `*Active Alerts Triggered:* ${res.active_alerts.map(a => a.title || a.rule_id || a).join(", ")}\n`;
      }

      return {
        content: [{ type: "text", text: out }]
      };
    }
  );

  // --------------------------------------------------------------------------
  // RESOURCE 1: confluence://locations
  // --------------------------------------------------------------------------
  server.resource(
    "locations",
    "confluence://locations",
    async (uri) => {
      const locations = await fetchConfluence("/locations");
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: "application/json",
            text: JSON.stringify(locations, null, 2)
          }
        ]
      };
    }
  );

  // --------------------------------------------------------------------------
  // RESOURCE 2: confluence://methodology
  // --------------------------------------------------------------------------
  server.resource(
    "methodology",
    "confluence://methodology",
    async (uri) => {
      const text = `# Confluence Environmental Intelligence Methodology

Confluence uses strictly deterministic physical regressions and official standards — zero ungrounded guessing:

1. **NOAA Heat Index Regression**: Rothfusz multivariable polynomial using ambient dry-bulb temperature and relative humidity with arid and humid adjustments.
2. **Magnus-Tetens Dew Point**: Saturation vapor pressure formula parameterized by Alduchov and Eskridge (1996).
3. **WMO Beaufort Wind Force**: Standard WMO Table 1200 relating 10m sustained wind speed to sea state and nautical force (0 to 12).
4. **NWS Small Craft Marine Advisory**: Standard 3-tiered advisory based on sustained wind >37 km/h (20 knots) or significant wave height >2.0m.
5. **Inverse Barometer Surge Effect**: Hydrostatic sea surface elevation response to atmospheric pressure drop (~1.01 cm surge per 1 hPa below standard 1013.25 hPa).
6. **Bergeron-Sanders-Gyakum Pressure Fall**: Latitude-normalized explosive cyclogenesis threshold ($24 \\times \\frac{\\sin \\phi}{\\sin 60^\\circ}$ hPa in 24h).
`;
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: "text/markdown",
            text
          }
        ]
      };
    }
  );

  // --------------------------------------------------------------------------
  // PROMPT 1: coastal-safety-audit
  // --------------------------------------------------------------------------
  server.prompt(
    "coastal-safety-audit",
    {
      location_name: z.string().describe("Coastal location to audit (e.g. 'Chennai', 'Mumbai')")
    },
    ({ location_name }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: `Perform a comprehensive coastal safety audit for ${location_name}.
1. Use the get_coastal_snapshot tool to retrieve live conditions.
2. Check for heat stress risk on outdoor port workers (NOAA Heat Index).
3. Check for maritime small craft advisories (wave height and wind speed).
4. Check for barometric depression and storm surge risks.
5. Formulate actionable, time-critical operational recommendations for harbor and vessel personnel.`
          }
        }
      ]
    })
  );

  // --------------------------------------------------------------------------
  // PROMPT 2: cyclone-readiness-check
  // --------------------------------------------------------------------------
  server.prompt(
    "cyclone-readiness-check",
    {
      location_name: z.string().describe("Coastal port/region to evaluate")
    },
    ({ location_name }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: `Run a cyclone and depression readiness evaluation for ${location_name}.
1. Fetch 24-hour trends via get_historical_trends.
2. Check the Bergeron rapid pressure fall criterion and IMD cyclone category.
3. Assess significant wave height and sustained wind gusts.
4. Report whether early cyclone warning conditions exist and what protective measures are required.`
          }
        }
      ]
    })
  );

  // --------------------------------------------------------------------------
  // START STDIO TRANSPORT
  // --------------------------------------------------------------------------
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Confluence MCP Server running on stdio");
}
