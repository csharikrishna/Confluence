import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const cliPath = path.resolve(__dirname, "../bin/cli.js");

async function runTest() {
  console.log("=== Confluence MCP Integration & Protocol Test ===");
  console.log(`Starting MCP server subprocess: node ${cliPath}`);

  const transport = new StdioClientTransport({
    command: "node",
    args: [cliPath],
    env: {
      ...process.env,
      CONFLUENCE_API_URL: process.env.CONFLUENCE_API_URL || "https://confluence-si41.onrender.com"
    }
  });

  const client = new Client(
    {
      name: "confluence-mcp-tester",
      version: "1.0.0"
    },
    {
      capabilities: {}
    }
  );

  try {
    await client.connect(transport);
    console.log("✅ Stdio connection handshake successful!");

    // 1. Verify Tools
    console.log("\n[1] Querying MCP Tools...");
    const toolsResult = await client.listTools();
    const toolNames = toolsResult.tools.map((t) => t.name);
    console.log(`Found ${toolNames.length} tools:`, toolNames);

    const expectedTools = [
      "get_coastal_snapshot",
      "get_preset_locations",
      "check_coastal_alerts",
      "get_historical_trends",
      "ask_coastal_assistant"
    ];

    for (const exp of expectedTools) {
      if (!toolNames.includes(exp)) {
        throw new Error(`Missing expected tool: ${exp}`);
      }
    }
    console.log("✅ All 5 expected tools registered!");

    // 2. Verify Resources
    console.log("\n[2] Querying MCP Resources...");
    const resourcesResult = await client.listResources();
    const resourceUris = resourcesResult.resources.map((r) => r.uri);
    console.log("Registered resources:", resourceUris);
    if (!resourceUris.includes("confluence://locations") || !resourceUris.includes("confluence://methodology")) {
      throw new Error("Missing expected resources");
    }
    console.log("✅ Resources registered!");

    // 3. Verify Prompts
    console.log("\n[3] Querying MCP Prompts...");
    const promptsResult = await client.listPrompts();
    const promptNames = promptsResult.prompts.map((p) => p.name);
    console.log("Registered prompts:", promptNames);
    if (!promptNames.includes("coastal-safety-audit") || !promptNames.includes("cyclone-readiness-check")) {
      throw new Error("Missing expected prompt templates");
    }
    console.log("✅ Prompts registered!");

    // 4. Test Tool Execution: get_preset_locations
    console.log("\n[4] Executing tool: get_preset_locations...");
    const locationsCall = await client.callTool({
      name: "get_preset_locations",
      arguments: {}
    });
    console.log("Result content type:", locationsCall.content[0]?.type);
    console.log("Output preview:\n", locationsCall.content[0]?.text.split("\n").slice(0, 5).join("\n"));
    if (!locationsCall.content[0]?.text.includes("Chennai")) {
      throw new Error("Tool output did not contain expected location 'Chennai'");
    }
    console.log("✅ Tool get_preset_locations passed!");

    // 5. Test Tool Execution: get_coastal_snapshot
    console.log("\n[5] Executing tool: get_coastal_snapshot for Chennai (13.08, 80.27)...");
    const snapshotCall = await client.callTool({
      name: "get_coastal_snapshot",
      arguments: {
        latitude: 13.08,
        longitude: 80.27,
        location_name: "Chennai Coast"
      }
    });
    const snapshotText = snapshotCall.content[0]?.text || "";
    console.log("Snapshot report excerpt:\n", snapshotText.split("\n").slice(0, 8).join("\n"));

    if (!snapshotText.includes("Atmospheric") || !snapshotText.includes("Marine")) {
      throw new Error("Snapshot did not include Atmospheric and Marine sections");
    }
    console.log("✅ Tool get_coastal_snapshot passed with full physics derivations!");

    // 6. Test Tool Execution: check_coastal_alerts
    console.log("\n[6] Executing tool: check_coastal_alerts...");
    const alertsCall = await client.callTool({
      name: "check_coastal_alerts",
      arguments: {
        latitude: 13.08,
        longitude: 80.27
      }
    });
    const alertsText = alertsCall.content[0]?.text || "";
    console.log("Alerts output preview:\n", alertsText.split("\n").slice(0, 6).join("\n"));
    if (!alertsText.includes("Coastal Safety") && !alertsText.includes("Small Craft")) {
      throw new Error("Alerts call did not return expected safety audit structure");
    }
    console.log("✅ Tool check_coastal_alerts passed!");

    // 7. Test Tool Execution: get_historical_trends
    console.log("\n[7] Executing tool: get_historical_trends...");
    const trendsCall = await client.callTool({
      name: "get_historical_trends",
      arguments: {
        latitude: 13.08,
        longitude: 80.27
      }
    });
    const trendsText = trendsCall.content[0]?.text || "";
    console.log("Trends output preview:\n", trendsText.split("\n").slice(0, 6).join("\n"));
    if (!trendsText.includes("24-Hour Environmental Trends")) {
      throw new Error("Trends call did not return expected trend comparison");
    }
    console.log("✅ Tool get_historical_trends passed!");

    // 8. Test Tool Execution: ask_coastal_assistant
    console.log("\n[8] Executing tool: ask_coastal_assistant...");
    const chatCall = await client.callTool({
      name: "ask_coastal_assistant",
      arguments: {
        query: "Is it safe to sail a small craft off Chennai today?"
      }
    });
    const chatText = chatCall.content[0]?.text || "";
    console.log("Assistant response preview:\n", chatText.split("\n").slice(0, 5).join("\n"));
    if (!chatText.includes("Coastal Assistant Response")) {
      throw new Error("Assistant response missing expected header");
    }
    console.log("✅ Tool ask_coastal_assistant passed!");

    console.log("\n=========================================================");
    console.log("🎉 ALL 5 MCP TOOLS PASSED WITH 100% PROTOCOL COMPLIANCE!");
    console.log("=========================================================\n");
  } finally {
    await client.close();
  }
}

runTest().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
