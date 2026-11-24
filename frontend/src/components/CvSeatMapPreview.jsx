import { useEffect, useState } from "react";

const CV_API_BASE = import.meta.env.VITE_CV_API_URL || "http://127.0.0.1:8001";
const STATE_STYLE = {
  AVAILABLE: "bg-emerald-100 text-emerald-800 border-emerald-200",
  OCCUPIED: "bg-rose-100 text-rose-800 border-rose-200",
  UNKNOWN: "bg-amber-100 text-amber-900 border-amber-200",
};

/** Draft, NON-reservable first-frame chair mapping. Not the actual hostel seat grid. */
export default function CvSeatMapPreview() {
  const [preview, setPreview] = useState(null);
  const [problem, setProblem] = useState("Loading draft seat map from MongoDB…");

  useEffect(() => {
    let mounted = true;
    let running;
    async function refresh() {
      running?.abort();
      running = new AbortController();
      try {
        const res = await fetch(`${CV_API_BASE}/api/cv/rooms/demo-study-hall/seat-preview`, {
          signal: running.signal,
          cache: "no-store",
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(json.detail || `HTTP ${res.status}`);
        if (!mounted) return;
        setPreview(json);
        setProblem("");
      } catch (err) {
        if (!mounted || err.name === "AbortError") return;
        setProblem(err.message || "Seat map is temporarily unavailable");
      }
    }
    refresh();
    const timer = setInterval(refresh, 2500);
    return () => { mounted = false; clearInterval(timer); running?.abort(); };
  }, []);

  return (
    <section className="mb-5 rounded-xl border border-[#d9e6df] bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#173e35]">Study hall — draft seat mapping</h2>
          <p className="text-xs text-[#60766e]">Persistent S01… candidate labels stored in MongoDB, evaluated against the latest saved Roboflow sample</p>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-900">UNVERIFIED · NOT RESERVABLE</span>
      </div>

      {preview && (
        <>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-sm">
            <span>Seat candidates: <strong>{preview.counts?.total ?? 0}</strong></span>
            <span>Available in reference: <strong className="text-emerald-700">{preview.counts?.available ?? 0}</strong></span>
            <span>Occupied in reference: <strong className="text-rose-700">{preview.counts?.occupied ?? 0}</strong></span>
            <span>Unknown: <strong className="text-amber-800">{preview.counts?.unknown ?? 0}</strong></span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-8">
            {(preview.seats || []).map((seat) => (
              <div key={seat.seat_id} title={seat.reason} className={`rounded-lg border px-2 py-3 text-center text-xs ${STATE_STYLE[seat.state] || STATE_STYLE.UNKNOWN}`}>
                <div className="font-bold">{seat.seat_id}</div>
                <div>{String(seat.state).toLowerCase()}</div>
                {typeof seat.confidence === "number" && <div>{Math.round(seat.confidence * 100)}% detection</div>}
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-[#60766e]">
            Saved sample {Number(preview.source_frame_index) + 1}/6 · t={Number(preview.video_time_seconds).toFixed(1)}s ·
            Reference sample {Number(preview.reference_frame_index) + 1} · Last saved {preview.source_published_at || "unknown"}
          </p>
          <p className="mt-2 rounded-lg bg-amber-50 p-3 text-xs font-medium text-amber-900">{preview.warning}</p>
        </>
      )}
      {problem && <p role="status" className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{problem}</p>}
      {!preview && <p className="mt-2 text-xs text-[#60766e]">Run <code>python -m camera_cloud_capture.seat_monitor_v1.propose_demo_seat_map</code> in the SLA terminal to save a draft map.</p>}
    </section>
  );
}
