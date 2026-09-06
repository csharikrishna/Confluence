#!/usr/bin/env node

import { main } from "../src/server.js";

main().catch((error) => {
  console.error("Fatal error in Confluence MCP server:", error);
  process.exit(1);
});
