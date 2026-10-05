// Explicit opt-in synthetic integration test. Uses the GUI's configured endpoint.
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
(async () => {
  if (!process.env.VOI_LIVE_MODEL)
    throw new Error("Set VOI_LIVE_MODEL to opt into local inference.");
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({
      viewport: { width: 1360, height: 1050 },
    });
    await page.goto(process.env.VOI_GUI_URL || "http://127.0.0.1:8876");
    await page.waitForFunction(
      () => document.querySelector("#model").options.length > 1,
    );
    await page.selectOption("#engine", "llm");
    await page.selectOption("#model", process.env.VOI_LIVE_MODEL);
    await page.fill("#singleName", "Lunge links");
    await page.click("#run");
    await page.waitForFunction(
      () => !document.querySelector("#run").disabled,
      {},
      { timeout: 600000 },
    );
    assert.equal(await page.locator("#error").isVisible(), false);
    assert.equal(
      await page.locator(".candidate-title").first().textContent(),
      "Lung Left",
    );
    assert.equal(
      await page.locator("#scoreLabel").textContent(),
      "RELEVANCE / 100",
    );
    await page.screenshot({
      path: path.join(__dirname, "../docs/gui-llm.png"),
      fullPage: true,
    });
    const first = await page.evaluate(
      async () =>
        await (
          await fetch("/api/jobs/" + sessionStorage.getItem("voi-job"))
        ).json(),
    );
    await page.reload();
    await page.waitForFunction(
      () => document.querySelector("#engine").value === "llm",
    );
    assert.equal(await page.locator("#singleName").inputValue(), "Lunge links");
    await page.selectOption("#vocabulary", "tg263");
    await page.fill("#singleName", "esophagus");
    await page.click("#run");
    await page.waitForFunction(
      () => !document.querySelector("#run").disabled,
      {},
      { timeout: 600000 },
    );
    assert.equal(await page.locator("#error").isVisible(), false);
    const second = await page.evaluate(
      async () =>
        await (
          await fetch("/api/jobs/" + sessionStorage.getItem("voi-job"))
        ).json(),
    );
    assert.equal(second.state, "completed");
    assert.ok(second.rows[0].candidates.length > 0);
    fs.mkdirSync(path.join(__dirname, "../results/browser"), {
      recursive: true,
    });
    fs.writeFileSync(
      path.join(__dirname, "../results/browser/live-inference.json"),
      JSON.stringify({ first, second }, null, 2),
    );
    console.log(
      "PASS: live Qwen STOPSTORM and TG-263 requests, result validation, reload recovery.",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
