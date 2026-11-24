import { useEffect, useState } from "react";

const CV_API_BASE = import.meta.env.VITE_CV_API_URL || "http://127.0.0.1:8001";
const COLORS = {
  AVAILABLE: "border-green-200 bg-green-100 text-green-800",
  OCCUPIED: "border-red-200 bg-red-100 text-red-800",
  UNKNOWN: "border-amber-200 bg-amber-100 text-amber-900",
};

/** MongoDB-backed demonstration feed. NEVER use this data to enable reservations. */
export default function CvDatabaseFeed() {
  const [snapshot, setSnapshot] = useState(null);
  const [status, setStatus] = useState("Loading saved CV observations…");
  const [lastRead, setLastRead] = useState("");

  useEffect(() => {
    let mounted = true;
    let controller;
    async function refresh() {
      if (controller) controller.abort();
      controller = new AbortController();
      try {
        const response = await fetch(`${CV_API_BASE}/api/cv/rooms/demo-study-hall`, {
          signal: controller.signal,
          cache: "no-store",
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
        if (!mounted) return;
        setSnapshot(body);
        setStatus("");
        setLastRead(new Date().toLocaleTimeString());
      } catch (error) {
        if (!mounted || error.name === "AbortError") return;
        setStatus(error.message || "Could not read MongoDB-backed CV observations");
      }
    }
    refresh();
    const interval = window.setInterval(refresh, 2500);
    return () => { mounted = false; window.clearInterval(interval); controller?.abort(); };
  }, []);

  return (
    <section className="mb-5 rounded-xl border border-[#d9e6df] bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-[#173e35]">MongoDB → React CV feed</h2>
          <p className="text-xs text-[#60766e]">Read from the cv_demo_snapshots collection, refreshed every 2.5 seconds</p>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-900">RECORDED DEMO · NOT LIVE</span>
      </div>
      {snapshot ? (
        <>
          <div className="mt-4 flex flex-wrap gap-4 text-sm">
            <span>Available detections: <strong className="text-green-700">{snapshot.counts?.available ?? 0}</strong></span>
            <span>Occupied detections: <strong className="text-red-700">{snapshot.counts?.occupied ?? 0}</strong></span>
            <span>Unknown detections: <strong className="text-amber-700">{snapshot.counts?.unknown ?? 0}</strong></span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-8">
            {(snapshot.detections || []).map((d) => (
              <div key={d.detection_label} className={`rounded-lg border px-2 py-2 text-center text-xs ${COLORS[d.state] || COLORS.UNKNOWN}`}>
                <div className="font-bold">{d.detection_label}</div>
                <div>{d.state.toLowerCase()}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-[#60766e]">
            Saved model: {snapshot.model_id} · Recorded clip t={Number(snapshot.video_time_seconds).toFixed(1)}s ·
            MongoDB write: {snapshot.published_at || "unknown"} · Last fetched: {lastRead}
          </p>
          <p className="mt-1 text-xs font-medium text-amber-800">These D-labels change each frame and are NOT physical seat IDs. Live reservations remain unchanged.</p>
        </>
      ) : null}
      {status ? <p role="status" className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{status}</p> : null}
      {!snapshot ? <p className="mt-2 text-xs text-gray-500">Start the port 8001 CV server, connect MongoDB, then publish recorded frames from your PyCharm terminal.</p> : null}
    </section>
  );
}
