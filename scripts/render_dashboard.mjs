#!/usr/bin/env node
import fs from "node:fs/promises";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import { spawn } from "node:child_process";

const DEFAULT_URL = "http://localhost:8767/";
const DEFAULT_OUTPUT_DIR = "output/playwright";
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
].filter(Boolean);

const VIEWPORTS = [
  { label: "desktop", width: 2048, height: 1400 },
  { label: "narrow", width: 720, height: 1200 },
];

function parseArgs(argv) {
  const args = {
    url: DEFAULT_URL,
    outputDir: DEFAULT_OUTPUT_DIR,
    timeoutMs: 45000,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--url") args.url = argv[++i];
    else if (arg === "--output-dir") args.outputDir = argv[++i];
    else if (arg === "--timeout-ms") args.timeoutMs = Number(argv[++i]);
    else if (arg === "--help") {
      console.log("Usage: node scripts/render_dashboard.mjs [--url URL] [--output-dir DIR] [--timeout-ms MS]");
      process.exit(0);
    }
  }
  return args;
}

async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function findChrome() {
  for (const candidate of CHROME_CANDIDATES) {
    if (await fileExists(candidate)) return candidate;
  }
  throw new Error("Chrome or Chromium was not found. Set CHROME_PATH to a headless-capable browser.");
}

async function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`GET ${url} returned ${res.statusCode}: ${body}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });
    req.once("error", reject);
    req.setTimeout(3000, () => {
      req.destroy(new Error(`Timed out requesting ${url}`));
    });
  });
}

async function waitForJson(url, timeoutMs) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      return await getJson(url);
    } catch (error) {
      lastError = error;
      await delay(250);
    }
  }
  throw lastError || new Error(`Timed out waiting for ${url}`);
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    });
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(payload);
    });
  }

  close() {
    if (this.ws) this.ws.close();
  }
}

async function waitForDashboard(client, timeoutMs) {
  const started = Date.now();
  let lastText = "";
  while (Date.now() - started < timeoutMs) {
    const result = await client.send("Runtime.evaluate", {
      returnByValue: true,
      expression: `(() => {
        const text = document.body ? document.body.innerText : "";
        const ready = text.includes("Big Day Optimizer") && text.includes("Stop plan");
        return { ready, text: text.slice(0, 500) };
      })()`,
    });
    const value = result.result?.value || {};
    lastText = value.text || lastText;
    if (value.ready) return;
    await delay(500);
  }
  throw new Error(`Dashboard did not finish rendering. Last visible text: ${JSON.stringify(lastText)}`);
}

async function renderViewport({ chromePath, url, outputDir, timeoutMs, viewport }) {
  const port = await getFreePort();
  const userDataDir = path.join("/private/tmp", `bbd-chrome-render-${process.pid}-${viewport.label}`);
  const outputPath = path.join(outputDir, `dashboard-${viewport.label}.png`);
  const chrome = spawn(chromePath, [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-features=MediaRouter,OptimizationHints,Translate",
    "--hide-scrollbars",
    "--no-default-browser-check",
    "--no-first-run",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    `--window-size=${viewport.width},${viewport.height}`,
    url,
  ], {
    stdio: ["ignore", "ignore", "pipe"],
  });

  let stderr = "";
  chrome.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  let client;
  try {
    const pages = await waitForJson(`http://127.0.0.1:${port}/json/list`, timeoutMs);
    const page = pages.find((entry) => entry.type === "page" && entry.webSocketDebuggerUrl);
    if (!page) throw new Error("Chrome did not expose a page target.");

    client = new CdpClient(page.webSocketDebuggerUrl);
    await client.connect();
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await waitForDashboard(client, timeoutMs);
    await delay(750);

    const screenshot = await client.send("Page.captureScreenshot", {
      captureBeyondViewport: false,
      format: "png",
      fromSurface: true,
    });
    await fs.writeFile(outputPath, Buffer.from(screenshot.data, "base64"));
    console.log(`Rendered ${viewport.label}: ${outputPath}`);
  } finally {
    if (client) client.close();
    chrome.kill("SIGTERM");
  }

  return { outputPath, stderr };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const chromePath = await findChrome();
  await fs.mkdir(args.outputDir, { recursive: true });

  for (const viewport of VIEWPORTS) {
    await renderViewport({
      chromePath,
      outputDir: args.outputDir,
      timeoutMs: args.timeoutMs,
      url: args.url,
      viewport,
    });
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
