// Optional UI smoke test: npm install --no-save playwright; start the GUI first.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1360, height: 1050 },
    deviceScaleFactor: 1,
  });
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await page.goto(process.env.VOI_GUI_URL || "http://127.0.0.1:8876");
  await page.waitForFunction(
    () => document.querySelector("#model").options.length > 1,
  );
  await page.click("#example");
  await page.click("#run");
  await page.waitForFunction(() =>
    document
      .querySelector("#progressText")
      .textContent.includes("Review ready"),
  );
  assert.equal(
    await page.locator(".candidate-title").first().textContent(),
    "Lung Left",
  );
  assert.equal(await page.locator(".candidate").count(), 5);
  assert.equal(
    await page.locator("body").evaluate((el) => el.scrollWidth > innerWidth),
    false,
  );
  fs.mkdirSync(path.join(__dirname, "../results/browser"), { recursive: true });
  await page.screenshot({
    path: path.join(__dirname, "../docs/gui-tester.png"),
    fullPage: true,
  });
  await page.selectOption("#vocabulary", "tg263");
  await page.fill("#singleName", "Lunge links");
  await page.click("#run");
  await page.waitForFunction(() =>
    document
      .querySelector("#progressText")
      .textContent.includes("Review ready"),
  );
  assert.equal(
    await page.locator(".candidate-title").first().textContent(),
    "Lung_L",
  );
  await page.selectOption("#vocabulary", "stopstorm");
  await page.click("#batchTab");
  await page.click("#example");
  await page.click("#run");
  await page.waitForFunction(() =>
    document.querySelector("#progressText").textContent.includes("7 / 7"),
  );
  assert.equal(await page.locator("#batchTable tbody tr").count(), 7);
  assert.equal(
    await page
      .locator("#batchTable tbody tr")
      .first()
      .locator("td")
      .last()
      .textContent(),
    "conflict",
  );
  await page.locator("#batchTable tbody tr").nth(3).locator("button").click();
  assert.equal(await page.locator("#selectedName").textContent(), "RIVA");
  const downloaded = page.waitForEvent("download");
  await page.click("#export");
  const download = await downloaded;
  assert.equal(download.suggestedFilename(), "voi-ranking.csv");
  await page.screenshot({
    path: path.join(__dirname, "../docs/gui-batch.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.locator("body").evaluate((el) => el.scrollWidth > innerWidth),
    false,
  );
  await page.screenshot({
    path: path.join(__dirname, "../results/browser/mobile.png"),
    fullPage: true,
  });
  await page.locator('#csvFile').setInputFiles({
    name:'synthetic.csv', mimeType:'text/csv',
    buffer:Buffer.from('Case,ROI_ID,StructureName\nA,1,Heart\nA,2,Herz\nB,1,Lung_R\n')
  });
  await page.waitForFunction(()=>document.querySelector('#csvMode').checked);
  await page.click('#run');
  await page.waitForFunction(()=>document.querySelector('#progressText').textContent.includes('3 / 3'));
  assert.equal(await page.locator('#batchTable tbody tr').count(),3);
  assert.equal(await page.locator('#batchTable tbody tr').first().locator('td').last().textContent(),'conflict');
  await page.click("#singleTab");
  await page.fill("#singleName", "");
  await page.click("#run");
  await page.waitForSelector("#error:not([hidden])");
  assert.match(await page.locator("#error").textContent(), /between 1 and 500/);
  await page.fill("#singleName", "<img src=x onerror=alert(1)>");
  await page.click("#run");
  await page.waitForFunction(() =>
    document.querySelector("#selectedName").textContent.includes("<img"),
  );
  assert.equal(await page.locator("#selectedName img").count(), 0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(
    await page
      .locator("#run")
      .evaluate((e) => getComputedStyle(e).transitionDuration),
    "0s",
  );
  await page.route('**/api/status',route=>route.fulfill({json:{online:false,models:[],loaded:[],gpu:{detected:null}}}));
  await page.click('#refreshStatus');
  await page.waitForFunction(()=>document.querySelector('#ollamaStatus').textContent.includes('offline'));
  assert.match(await page.locator('#gpuStatus').textContent(),/unverified/);
  await page.locator('#run').focus();
  assert.equal(await page.locator('#run').evaluate(e=>e===document.activeElement),true);
  assert.deepEqual(failures, []);
  console.log(
    "PASS: desktop/mobile, TG-263, CSV import/export, batch conflicts, row selection, empty input, escaped names, reduced motion, offline status, keyboard focus.",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
