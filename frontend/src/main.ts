import { api, subscribeSession } from "./api";
import type { SessionSnapshot } from "./api";

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("#app missing");
}

app.innerHTML = `
  <main>
    <h1>Camera Cloud Capture</h1>
    <p class="muted">Start a capture session; frames upload to GCS as a numbered sequence.</p>
    <form id="start-form">
      <label>Source <input name="source" value="0" /></label>
      <label>Mode
        <select name="mode">
          <option value="interval">interval</option>
          <option value="session">session</option>
        </select>
      </label>
      <label>Every seconds <input name="interval" type="number" step="0.1" value="2" /></label>
      <button type="submit">Start</button>
      <button type="button" id="stop">Stop latest</button>
    </form>
    <pre id="status">Connecting…</pre>
    <h2>Devices</h2>
    <pre id="devices"></pre>
    <h2>Archive</h2>
    <pre id="archive"></pre>
  </main>
`;

const statusEl = document.querySelector<HTMLPreElement>("#status")!;
const devicesEl = document.querySelector<HTMLPreElement>("#devices")!;
const archiveEl = document.querySelector<HTMLPreElement>("#archive")!;
let latestSession: string | null = null;
let unsubscribe: (() => void) | null = null;

function renderSession(snapshot: SessionSnapshot) {
  statusEl.textContent = JSON.stringify(snapshot, null, 2);
}

document.querySelector("#start-form")!.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target as HTMLFormElement;
  const data = new FormData(form);
  const snapshot = await api.startSession({
    source: String(data.get("source") || "0"),
    mode: (data.get("mode") as "interval" | "session") || "interval",
    interval_seconds: Number(data.get("interval") || 2),
  });
  latestSession = snapshot.session_id;
  renderSession(snapshot);
  unsubscribe?.();
  unsubscribe = subscribeSession(snapshot.session_id, renderSession);
});

document.querySelector("#stop")!.addEventListener("click", async () => {
  if (!latestSession) {
    return;
  }
  const snapshot = await api.stopSession(latestSession);
  renderSession(snapshot);
});

async function boot() {
  try {
    await api.health();
    const devices = await api.listDevices();
    devicesEl.textContent = JSON.stringify(devices.devices, null, 2);
    const archive = await api.listArchiveSessions();
    archiveEl.textContent = JSON.stringify(archive, null, 2);
    statusEl.textContent = "API connected. Start a session.";
  } catch (error) {
    statusEl.textContent = `API unavailable: ${error instanceof Error ? error.message : String(error)}`;
  }
}

void boot();
