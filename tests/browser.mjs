// Optional UI integration check. Start a local demo and set DASHBOARD_URL first.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "playwright"
);
const url = process.env.DASHBOARD_URL || "http://127.0.0.1:8900";
assert(
  ["127.0.0.1", "localhost"].includes(new URL(url).hostname),
  "Use an isolated loopback demo",
);
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
  ...(process.env.BROWSER_EXECUTABLE
    ? { executablePath: process.env.BROWSER_EXECUTABLE }
    : {}),
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1080 },
  });
  const errors = [],
    external = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", (route) => {
    if (new URL(route.request().url()).origin !== new URL(url).origin) {
      external.push(route.request().url());
      return route.abort();
    }
    return route.continue();
  });
  await page.goto(url);
  await page.locator(".model").first().waitFor();
  assert((await page.locator("#notice").innerText()).includes("Demo"));
  assert.equal(await page.locator(".model").count(), 3);
  assert((await page.locator(".model").nth(2).innerText()).includes("Unknown"));
  await page.locator("#language").click();
  assert.equal(await page.locator("html").getAttribute("lang"), "zh-CN");
  assert((await page.locator("#notice").innerText()).includes("虚构"));
  await mkdir("docs", { recursive: true });
  await page.screenshot({ path: "docs/demo-desktop.png", fullPage: true });
  await page.locator("#source-filter").selectOption("demo");
  assert.equal(await page.locator(".model").count(), 3);
  await page.locator("#theme").click();
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
  await page.setViewportSize({ width: 390, height: 844 });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "Mobile horizontal overflow",
  );
  await page.screenshot({ path: "docs/demo-mobile.png", fullPage: true });
  // Untrusted allowed text must render as literal text, never markup.
  await page.route("**/api/dashboard", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.site.title = "<img src=x onerror=alert(1)>";
    data.models[0].label = "<script>alert(1)</script>";
    await route.fulfill({ response, json: data });
  });
  await page.locator("#source-filter").selectOption("");
  await page.locator("#refresh").click();
  await page.waitForFunction(() =>
    document.getElementById("title").textContent.startsWith("<img"),
  );
  assert.equal(await page.locator("#title img").count(), 0);
  assert.equal(await page.locator(".model script").count(), 0);
  await page.unroute("**/api/dashboard");
  // Network loss must remove balances even if the visitor changes language.
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({ status: 503, body: "{}" }),
  );
  await page.locator("#refresh").click();
  await page.waitForFunction(
    () => document.querySelectorAll(".model").length === 0,
  );
  await page.locator("#language").click();
  assert.equal(await page.locator(".model").count(), 0);
  await page.unroute("**/api/dashboard");
  await page.locator("#refresh").click();
  await page.locator(".model").first().waitFor();
  assert.equal(await page.locator(".model").count(), 3);
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  console.log(
    "PASS: desktop, mobile, languages, theme, filter, literal labels, connection loss, recovery; no external requests or JS exceptions",
  );
} finally {
  await browser.close();
}
