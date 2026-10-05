"use strict";
const $ = (id) => document.getElementById(id);
let config,
  health,
  batch = false,
  active = false,
  jobId = "",
  selected = 0,
  latest;
const node = (tag, text, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
async function api(path, body) {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-VOI-CSRF": config.csrf,
          },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
function error(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function lamp(id, text, state, title) {
  const el = $(id);
  el.replaceChildren(node("i"), document.createTextNode(text));
  el.className = "status " + state;
  el.title = title || text;
}
function lights() {
  if (!health) return;
  lamp(
    "ollamaStatus",
    health.online ? "Ollama connected" : "Ollama offline",
    health.online ? "good" : "bad",
  );
  const model = $("model").value,
    installed = health.models.some((m) => m.name === model),
    loaded = health.loaded.find((m) => m.name === model);
  lamp(
    "modelStatus",
    loaded
      ? "Model loaded"
      : installed
        ? "Model installed · not loaded"
        : "Model not selected",
    loaded ? "good" : "warn",
    model || "Select a local model",
  );
  const onGpu = loaded && loaded.size_vram > 0,
    device = health.gpu.devices?.[0];
  lamp(
    "gpuStatus",
    onGpu
      ? "Model on GPU"
      : device
        ? "GPU detected"
        : loaded
          ? "Model on CPU"
          : "GPU unverified",
    onGpu || device ? "good" : "warn",
    device
      ? `${device.name}; ${device.free_mb} / ${device.total_mb} MB free. Capacity is not guaranteed.`
      : "No supported GPU observation; AMD/Apple hardware may still be usable.",
  );
  if (health.queue_paused) lamp("ollamaStatus", "Coordinator paused", "warn");
}
async function refresh() {
  $("refreshStatus").disabled = true;
  try {
    health = await api("/api/status");
    const previous = $("model").value;
    $("model").replaceChildren(node("option", "Select a local model"));
    $("model").firstChild.value = "";
    for (const m of health.models) {
      const o = node("option", m.name);
      o.value = m.name;
      $("model").append(o);
    }
    if (health.models.some((m) => m.name === previous))
      $("model").value = previous;
    else
      $("model").value =
        (
          health.models.find((m) => m.name === "qwen3.5:4b") ||
          health.models.find(
            (m) => m.name.startsWith("qwen") && !m.name.includes("embed"),
          )
        )?.name || "";
    lights();
  } catch (e) {
    lamp("ollamaStatus", "Status unavailable", "bad");
    lamp("modelStatus", "Model unverified", "warn");
    lamp("gpuStatus", "GPU unverified", "warn");
  } finally {
    $("refreshStatus").disabled = false;
  }
}
function mode(value) {
  batch = value;
  $("singleTab").setAttribute("aria-pressed", String(!batch));
  $("batchTab").setAttribute("aria-pressed", String(batch));
  $("singleName").hidden = batch;
  $("batchInput").hidden = !batch;
  $("run").querySelector("span").textContent = batch
    ? "Rank batch"
    : "Find candidates";
}
function busy(value) {
  active = value;
  for (const id of [
    "singleTab",
    "batchTab",
    "run",
    "example",
    "vocabulary",
    "engine",
    "model",
    "singleName",
    "batchNames",
    "caseName",
    "csvFile",
    "csvMode",
  ])
    $(id).disabled = value;
  $("cancel").hidden = !value;
}
function candidate(row) {
  $("candidateArea").hidden = false;
  $("selectedName").textContent = row.name;
  $("selectedState").textContent = row.state || "pending";
  $("selectedState").className = "pill " + (row.state || "");
  $("rowNote").textContent =
    row.note || "Batch in progress; duplicate checks follow.";
  $("candidates").replaceChildren();
  row.candidates.forEach((c, i) => {
    const li = node("li", undefined, "candidate");
    li.append(node("span", String(i + 1).padStart(2, "0"), "rank"));
    const detail = node("div");
    detail.append(
      node("div", c.name, "candidate-title"),
      node("div", c.warning || c.description || c.basis, "candidate-sub"),
    );
    const score = node("div", undefined, "score");
    score.append(
      document.createTextNode(c.score + " "),
      node("small", "/ 100"),
    );
    const meter = node("meter");
    meter.min = 0;
    meter.max = 100;
    meter.value = c.score;
    meter.setAttribute("aria-label", `${c.name}: ${c.score} out of 100`);
    score.append(meter);
    li.append(detail, score);
    $("candidates").append(li);
  });
  if (!row.candidates.length)
    $("candidates").append(
      node("li", "No plausible candidate returned.", "row-note"),
    );
}
function render(job) {
  latest = job;
  $("empty").hidden = job.rows.length > 0;
  $("progressArea").hidden = false;
  $("progress").max = job.total;
  $("progress").value = job.done;
  $("progressText").textContent = `${job.done} / ${job.total} · ${job.message}`;
  $("resultMeta").textContent =
    `${job.catalogue_version} · ${job.mode === "llm" ? "Local LLM · " + job.model : "Name similarity"} · ${job.state}`;
  $("scoreLabel").textContent =
    job.mode === "llm" ? "RELEVANCE / 100" : "SIMILARITY / 100";
  const multi = job.total > 1;
  $("summary").hidden = !multi;
  $("batchTable").hidden = !multi;
  if (multi) {
    const proposed = job.rows.filter((r) => r.state === "proposed").length,
      conflicts = job.rows.filter((r) => r.state === "conflict").length;
    $("summary").replaceChildren();
    for (const [n, label] of [
      [job.done, "processed"],
      [proposed, "proposed"],
      [conflicts, "conflicts"],
    ]) {
      const span = node("span");
      span.append(node("strong", n + " "), document.createTextNode(label));
      $("summary").append(span);
    }
    const table = node("table"),
      head = node("thead"),
      hr = node("tr");
    ["Case", "Original name", "Top candidate", "State"].forEach((t) =>
      hr.append(node("th", t)),
    );
    head.append(hr);
    table.append(head);
    const body = node("tbody");
    job.rows.forEach((r, i) => {
      const tr = node("tr");
      if (i === selected) tr.className = "selected";
      tr.append(node("td", r.case || "—"));
      const td = node("td"),
        b = node("button", r.name);
      b.addEventListener("click", () => {
        selected = i;
        render(latest);
      });
      td.append(b);
      tr.append(
        td,
        node("td", r.candidates[0]?.name || "—"),
        node("td", r.state || "pending"),
      );
      body.append(tr);
    });
    table.append(body);
    $("batchTable").replaceChildren(table);
  }
  if (job.rows.length) {
    selected = Math.min(selected, job.rows.length - 1);
    candidate(job.rows[selected]);
  }
}
async function poll() {
  try {
    const job = await api("/api/jobs/" + jobId);
    render(job);
    if (["running", "cancelling"].includes(job.state)) {
      setTimeout(poll, 700);
      return;
    }
    busy(false);
    $("export").disabled = !job.rows.length;
    if (job.error) error(job.error);
    refresh();
  } catch (e) {
    error(
      e.message +
        " Refresh the page to reconnect; the batch may still be running.",
    );
    busy(false);
  }
}
async function run() {
  error("");
  $("export").disabled = true;
  $("candidateArea").hidden = true;
  $("batchTable").hidden = true;
  $("summary").hidden = true;
  $("empty").hidden = false;
  selected = 0;
  $("progressArea").hidden = false;
  $("progress").value = 0;
  $("progressText").textContent = "Preparing request";
  $("resultMeta").textContent = "Preparing candidates";
  try {
    if ($("engine").value === "llm" && !$("model").value)
      throw new Error("Select an installed local model.");
    busy(true);
    const job = await api("/api/jobs", {
      text: batch ? $("batchNames").value : $("singleName").value,
      csv: batch && $("csvMode").checked,
      case: batch ? $("caseName").value : "",
      vocabulary: $("vocabulary").value,
      mode: $("engine").value,
      model: $("model").value,
    });
    jobId = job.id;
    sessionStorage.setItem("voi-job", jobId);
    poll();
  } catch (e) {
    busy(false);
    error(e.message);
  }
}
$("singleTab").onclick = () => mode(false);
$("batchTab").onclick = () => mode(true);
$("run").onclick = run;
$("singleName").onkeydown = (e) => {
  if (e.key === "Enter" && !active) run();
};
$("refreshStatus").onclick = refresh;
$("model").onchange = lights;
$("example").onclick = () => {
  if (batch) {
    $("batchNames").value =
      "Heart\nHerz\nLunge links\nRIVA\nPTV_1\nVena cava\nLung_R";
    $("caseName").value = "DEMO_A";
    $("csvMode").checked = false;
  } else $("singleName").value = "Lunge links";
};
$("csvMode").onchange = () => {
  $("caseName").disabled = $("csvMode").checked;
};
$("csvFile").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  if (file.size > 500000) {
    error("CSV is too large (maximum 500 KB).");
    return;
  }
  $("batchNames").value = await file.text();
  $("csvMode").checked = true;
  $("caseName").disabled = true;
};
$("engine").onchange = () => {
  $("modelField").classList.toggle("inactive", $("engine").value !== "llm");
};
$("cancel").onclick = async () => {
  try {
    await api("/api/jobs/" + jobId + "/cancel", {});
    $("progressText").textContent =
      "Stop requested; waiting for the current request to end.";
  } catch (e) {
    error(e.message);
  }
};
$("export").onclick = () => {
  if (jobId) window.location.href = "/api/jobs/" + jobId + "/export";
};
$("vocabulary").onchange = () => {
  const c = config.catalogues.find((c) => c.id === $("vocabulary").value);
  $("catalogueFooter").textContent = c.label;
  $("catalogueNote").textContent =
    c.id === "tg263"
      ? "AAPM worksheet v20170815 · primary names; not a target-name generator."
      : "Study vocabulary · CardTV is a terminology grouping, not contour equivalence.";
};
async function init() {
  try {
    config = await api("/api/config");
    $("endpoint").textContent = config.endpoint;
    $("connectionText").textContent =
      "Ollama endpoint: " + config.endpoint + ". Configured at server startup.";
    $("vocabulary").replaceChildren();
    for (const c of config.catalogues) {
      const o = node(
        "option",
        `${c.id === "tg263" ? "AAPM TG-263" : "STOPSTORM"} · ${c.count} names`,
      );
      o.value = c.id;
      $("vocabulary").append(o);
    }
    $("vocabulary").onchange();
    if (!config.catalogues.some((c) => c.id === "tg263"))
      $("catalogueNote").textContent +=
        " TG-263 not installed; see repository setup.";
    await refresh();
    const saved = sessionStorage.getItem("voi-job");
    if (saved) {
      try {
        const job = await api("/api/jobs/" + saved);
        jobId = saved;
        mode(job.total > 1);
        $("vocabulary").value = job.vocabulary;
        $("vocabulary").onchange();
        $("engine").value = job.mode;
        if (job.model) $("model").value = job.model;
        lights();
        if (job.total === 1 && job.rows.length)
          $("singleName").value = job.rows[0].name;
        render(job);
        if (["running", "cancelling"].includes(job.state)) {
          busy(true);
          poll();
        } else $("export").disabled = !job.rows.length;
      } catch (e) {
        sessionStorage.removeItem("voi-job");
      }
    }
    setInterval(refresh, 15000);
  } catch (e) {
    error(e.message);
  }
}
init();
