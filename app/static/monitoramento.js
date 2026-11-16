const themeButton = document.querySelector("#theme-toggle");
const statusText = document.querySelector("#status span:last-child");
const status = document.querySelector("#status");
const updated = document.querySelector("#updated");
const history = Object.fromEntries(["cpu", "memoria", "swap", "disco"].map((key) => [key, []]));
let lastSample = null;
let instanceInfo = null;

function setInstanceValue(id, text) {
  document.getElementById(`instance-${id}`).textContent = text;
}

function updateUptime() {
  const boot = Date.parse(instanceInfo?.iniciada_em);
  if (!Number.isFinite(boot) || boot > Date.now()) {
    setInstanceValue("uptime", "Indisponível");
    return;
  }
  const minutes = Math.floor((Date.now() - boot) / 60000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  setInstanceValue("uptime", `${days ? `${days}d ` : ""}${hours}h ${minutes % 60}min`);
}

async function refreshInstance() {
  try {
    const response = await fetch("/api/instancia", { cache: "no-store" });
    if (!response.ok) throw new Error("Informações indisponíveis");
    instanceInfo = await response.json();
    setInstanceValue("name", instanceInfo.nome || "Nome indisponível");
    setInstanceValue("type", instanceInfo.tipo || "Indisponível");
    setInstanceValue("os", instanceInfo.sistema_operacional || "Indisponível");
    setInstanceValue("arch", instanceInfo.arquitetura || "Indisponível");
    updateUptime();
  } catch {
    for (const id of ["name", "type", "os", "arch", "uptime"]) setInstanceValue(id, "Indisponível");
  } finally {
    window.setTimeout(refreshInstance, 60000);
  }
}

function updateThemeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  themeButton.setAttribute("aria-label", dark ? "Ativar tema claro" : "Ativar tema escuro");
  themeButton.title = themeButton.getAttribute("aria-label");
}

themeButton.addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("theme", theme); } catch { /* A escolha vale nesta página. */ }
  updateThemeButton();
});
window.addEventListener("storage", (event) => {
  if (event.key === "theme" && ["light", "dark"].includes(event.newValue)) {
    document.documentElement.dataset.theme = event.newValue;
    updateThemeButton();
  }
});
updateThemeButton();

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: unit ? 1 : 0 })} ${units[unit]}`;
}

function renderMetric(key, metric, addSample) {
  const card = document.querySelector(`[data-metric="${key}"]`);
  const value = card.querySelector(".metric-value");
  const detail = card.querySelector(".metric-detail");
  const percentage = metric?.percentual;
  const available = Number.isFinite(percentage);
  value.textContent = available ? `${percentage.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%` : "—";
  if (!metric) detail.textContent = "Métrica indisponível";
  else if (key === "cpu") detail.textContent = metric.nucleos ? `${metric.nucleos} CPUs virtuais` : "CPUs virtuais indisponíveis";
  else if (metric.total_bytes === 0) detail.textContent = "Não configurada";
  else detail.textContent = `${formatBytes(metric.usado_bytes)} de ${formatBytes(metric.total_bytes)} em uso`;

  if (addSample) {
    history[key].push(available ? Math.max(0, Math.min(100, percentage)) : null);
    if (history[key].length > 60) history[key].shift();
  }
  // Interrupções de coleta não são ligadas por uma linha que sugeriria dados ausentes.
  const lastGap = history[key].lastIndexOf(null);
  const points = history[key].slice(lastGap + 1);
  card.querySelector("polyline").setAttribute("points", points.map((v, i) => `${(60 - points.length + i) * 300 / 59},${69 - v * 68 / 100}`).join(" "));
}

async function refreshMetrics() {
  try {
    const response = await fetch("/api/metricas", { cache: "no-store" });
    if (!response.ok) throw new Error("Falha ao carregar métricas");
    const data = await response.json();
    if (!data.coletado_em || Number.isNaN(Date.parse(data.coletado_em))) throw new Error("Amostra indisponível");
    const isNew = data.coletado_em !== lastSample;
    for (const key of Object.keys(history)) renderMetric(key, data[key], isNew);
    setInstanceValue("cpu", data.cpu?.nucleos ? String(data.cpu.nucleos) : "Indisponível");
    setInstanceValue("memory", formatBytes(data.memoria?.total_bytes));
    setInstanceValue("disk", formatBytes(data.disco?.total_bytes));
    if (instanceInfo) updateUptime();
    lastSample = data.coletado_em;
    const stale = Date.now() - Date.parse(lastSample) > 20000;
    status.classList.toggle("status-error", stale);
    statusText.textContent = stale ? "Atualização atrasada" : "Aplicação respondendo";
    updated.textContent = `Última coleta às ${new Date(lastSample).toLocaleTimeString("pt-BR")}`;
  } catch {
    status.classList.add("status-error");
    statusText.textContent = "Sem conexão · tentando novamente";
    for (const id of ["cpu", "memory", "disk"]) setInstanceValue(id, "Indisponível");
  } finally {
    window.setTimeout(refreshMetrics, 5000);
  }
}

refreshInstance();
refreshMetrics();
