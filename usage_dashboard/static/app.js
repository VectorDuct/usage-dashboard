"use strict";
const $ = (id) => document.getElementById(id);
const words = {
  en: {
    overview: "Workspace overview",
    refresh: "Refresh",
    waiting: "Waiting for data",
    sources: "Data sources",
    models: "Model usage",
    source: "Source",
    all: "All sources",
    history: "Recent daily snapshots",
    historyNote:
      "Latest observation per source and day, not a billing statement.",
    footer:
      "Usage is reported by your configured sources. Unknown values stay unknown.",
    unknown: "Unknown",
    used: "Used in this window",
    limit: "Limit",
    remaining: "Remaining",
    requests: "Requests",
    rate: "Success rate",
    tokens: "Tokens",
    requestsUnit: "Requests",
    estimated: "Estimated quota",
    partial: "Partial usage; total balance is unknown.",
    demo: "Demo mode: all displayed demo values are fictional.",
    degraded: "Some sources are unavailable. Total balances are unknown.",
    historyFailed: "History is currently unavailable.",
    network: "Unable to refresh. Check the connection and try again.",
    empty: "No fresh usage data is available for this selection.",
    ok: "Fresh",
    unavailable: "Unavailable",
    stale: "Out of date",
    disabled: "Disabled",
    updated: "Updated",
    date: "Date",
    timezone: "Timezone",
    model: "Model",
    unit: "Unit",
    historyEmpty: "No snapshots yet.",
    theme: "Toggle color theme",
    healthy: "sources fresh",
  },
  "zh-CN": {
    overview: "用量总览",
    refresh: "刷新",
    waiting: "等待数据",
    sources: "数据源",
    models: "模型用量",
    source: "数据源",
    all: "全部数据源",
    history: "最近每日快照",
    historyNote: "保留每个数据源每天最后一次观测，不代表账单结算。",
    footer: "用量来自已配置的数据源；缺失的数值显示为未知。",
    unknown: "未知",
    used: "本窗口已用",
    limit: "额度上限",
    remaining: "剩余额度",
    requests: "请求数",
    rate: "成功率",
    tokens: "Token",
    requestsUnit: "请求",
    estimated: "估算额度",
    partial: "用量不完整，总余额未知。",
    demo: "演示模式：演示数据均为虚构。",
    degraded: "部分数据源不可用，总余额暂无法确认。",
    historyFailed: "历史快照暂不可用。",
    network: "刷新失败，请检查连接后重试。",
    empty: "当前选择暂无新鲜的用量数据。",
    ok: "数据新鲜",
    unavailable: "不可用",
    stale: "已过期",
    disabled: "已停用",
    updated: "更新于",
    date: "日期",
    timezone: "时区",
    model: "模型",
    unit: "单位",
    historyEmpty: "尚无快照。",
    theme: "切换明暗主题",
    healthy: "个数据源新鲜",
  },
};
const storage = {
  get(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {}
  },
};
let lang = storage.get("language"),
  state = null,
  history = [],
  busy = false,
  timer,
  historyFailed = false;
if (!words[lang]) lang = null;
document.documentElement.dataset.theme =
  storage.get("theme") === "dark" ? "dark" : "light";
function t(key) {
  return words[lang || "en"][key] || key;
}
function el(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
}
function fmt(value) {
  return value == null
    ? t("unknown")
    : new Intl.NumberFormat(lang || "en").format(value);
}
function unit(value) {
  return t(value === "tokens" ? "tokens" : "requestsUnit");
}
function labelUI() {
  document.documentElement.lang = lang || "en";
  for (const [id, key] of Object.entries({
    "intro-label": "overview",
    refresh: "refresh",
    "source-heading": "sources",
    "models-heading": "models",
    "filter-label": "source",
    "history-heading": "history",
    "history-note": "historyNote",
    "footer-note": "footer",
  }))
    $(id).textContent = t(key);
  $("language").textContent = lang === "zh-CN" ? "English" : "中文";
  $("theme").setAttribute("aria-label", t("theme"));
}
function card(row) {
  const node = el("article", undefined, "model"),
    header = el("div", undefined, "model-header");
  header.append(el("h3", row.label), el("span", unit(row.unit), "unit"));
  node.append(header);
  node.append(
    el("p", `${row.window.date} / ${row.window.timezone}`, "window"),
    el("div", fmt(row.used), "usage-number"),
    el("p", t("used"), "usage-label"),
  );
  if (row.percent != null) {
    const progress = el("progress", undefined, "quota-bar");
    progress.max = 100;
    progress.value = Math.min(100, row.percent);
    progress.setAttribute("aria-label", `${row.label}: ${row.percent}%`);
    node.append(progress);
  }
  const balance = el("div", undefined, "balance");
  for (const [key, value] of [
    ["limit", row.limit],
    ["remaining", row.remaining],
  ]) {
    const part = el("span", t(key) + " ");
    part.append(el("strong", fmt(value)));
    balance.append(part);
  }
  node.append(balance);
  const stats = el("dl", undefined, "model-stats");
  for (const [key, value] of [
    ["requests", fmt(row.requests)],
    ["rate", row.success_rate == null ? t("unknown") : `${row.success_rate}%`],
  ]) {
    const item = el("div");
    item.append(el("dt", t(key)), el("dd", value));
    stats.append(item);
  }
  node.append(stats);
  if (row.partial || row.estimated)
    node.append(
      el("p", row.partial ? t("partial") : t("estimated"), "model-note"),
    );
  return node;
}
function render() {
  labelUI();
  if (!state) return;
  document.title = state.site.title;
  $("brand-name").textContent = state.site.title;
  $("title").textContent = state.site.title;
  $("description").textContent = state.site.description;
  const observations = state.sources
    .filter((s) => s.ok)
    .map((s) => Date.parse(s.data.generated_at));
  $("updated").textContent = observations.length
    ? t("updated") +
      " " +
      new Intl.DateTimeFormat(lang, {
        timeZone: state.timezone,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZoneName: "short",
      }).format(new Date(Math.min(...observations)))
    : t("waiting");
  const messages = [];
  if (state.demo) messages.push(t("demo"));
  if (!state.ok) messages.push(t("degraded"));
  if (historyFailed || !state.history_ok) messages.push(t("historyFailed"));
  $("notice").hidden = !messages.length;
  $("notice").textContent = messages.join(" ");
  $("sources").replaceChildren();
  for (const source of state.sources) {
    const row = el("div", undefined, "source");
    row.append(
      el("strong", source.label),
      el("span", t(source.status), source.ok ? "state-ok" : "state-bad"),
    );
    if (source.demo) row.append(el("span", lang === "zh-CN" ? "演示" : "Demo"));
    $("sources").append(row);
  }
  const active = state.sources.filter((s) => s.status !== "disabled");
  $("source-summary").textContent =
    `${active.filter((s) => s.ok).length} / ${active.length} ${t("healthy")}`;
  const selection = $("source-filter").value;
  $("source-filter").replaceChildren(new Option(t("all"), ""));
  for (const source of active)
    $("source-filter").append(new Option(source.label, source.id));
  $("source-filter").value = active.some((s) => s.id === selection)
    ? selection
    : "";
  const selected = state.sources.find((s) => s.id === $("source-filter").value);
  const models = selected
    ? selected.ok
      ? selected.data.models.map((m) => ({
          ...m,
          window: selected.data.window,
          partial: false,
        }))
      : []
    : state.models;
  $("models").replaceChildren(...models.map(card));
  $("empty").hidden = !!models.length;
  $("empty").textContent = t("empty");
  $("history-columns").replaceChildren(
    ...["date", "timezone", "source", "model", "unit", "used", "limit"].map(
      (key) => el("th", t(key)),
    ),
  );
  const names = Object.fromEntries(state.sources.map((s) => [s.id, s.label])),
    rows = [];
  for (const snap of history) {
    if (selected && snap.source_id !== selected.id) continue;
    for (const model of snap.data.models) {
      const row = el("tr");
      for (const value of [
        snap.data.window.date,
        snap.data.window.timezone,
        names[snap.source_id] || snap.source_id,
        model.label,
        unit(model.unit),
        fmt(model.used),
        fmt(model.limit),
      ])
        row.append(el("td", value));
      rows.push(row);
      if (rows.length >= 40) break;
    }
    if (rows.length >= 40) break;
  }
  if (!rows.length) {
    const row = el("tr"),
      cell = el("td", t("historyEmpty"));
    cell.colSpan = 7;
    row.append(cell);
    rows.push(row);
  }
  $("history").replaceChildren(...rows);
}
async function getJSON(path) {
  const response = await fetch(path, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw Error("unavailable");
  return response.json();
}
async function refresh() {
  if (busy) return;
  busy = true;
  clearTimeout(timer);
  $("refresh").disabled = true;
  try {
    const results = await Promise.allSettled([
      getJSON("/api/dashboard"),
      getJSON("/api/history"),
    ]);
    if (results[0].status !== "fulfilled") throw Error("unavailable");
    state = results[0].value;
    if (!lang) lang = state.site.language;
    historyFailed = results[1].status !== "fulfilled";
    history = historyFailed ? [] : results[1].value.snapshots;
    render();
  } catch {
    labelUI();
    $("notice").hidden = false;
    $("notice").textContent = t("network");
    $("models").replaceChildren();
    $("sources").replaceChildren();
    $("source-summary").textContent = "";
    $("empty").hidden = false;
    $("empty").textContent = t("empty");
    // Do not let the source selector or language toggle resurrect cached balances.
    state = null;
    $("source-filter").replaceChildren(new Option(t("all"), ""));
  } finally {
    busy = false;
    $("refresh").disabled = false;
    timer = setTimeout(
      refresh,
      Math.max(1000, (state?.poll_interval || 30) * 1000),
    );
  }
}
$("refresh").addEventListener("click", refresh);
$("source-filter").addEventListener("change", render);
$("language").addEventListener("click", () => {
  lang = lang === "zh-CN" ? "en" : "zh-CN";
  storage.set("language", lang);
  render();
});
$("theme").addEventListener("click", () => {
  const next =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  storage.set("theme", next);
});
labelUI();
refresh();
