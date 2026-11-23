import { useEffect, useState } from "react";
import { Link } from "react-router";

// Separate, read-only inference preview. Not a source of reservable seat status.
const CV_SERVER = "http://127.0.0.1:8001";
const STATUS_CLASSES = {
  AVAILABLE: "border-green-200 bg-green-100 text-green-800",
  OCCUPIED: "border-red-200 bg-red-100 text-red-800",
  UNKNOWN: "border-yellow-200 bg-yellow-100 text-yellow-900",
};

/** React-native playback of actual cached Roboflow samples (not a live seat map). */
export default function CvDemoPanel({ compact = false }) {
  const [expanded, setExpanded] = useState(!compact);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(!compact);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [retryNumber, setRetryNumber] = useState(0);

  useEffect(() => {
    if (!expanded) return undefined;
    const controller = new AbortController();
    fetch(`${CV_SERVER}/api/cv-preview/samples`, {
      method: "GET",
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`CV preview returned HTTP ${response.status}`);
        return response.json();
      })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!Array.isArray(result.samples) || result.samples.length === 0) {
          throw new Error("The CV server has no sampled detections yet.");
        }
        setReport(result);
        setError("");
        setLoading(false);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setError(reason?.message || "Cannot connect to the recorded CV server");
        setLoading(false);
      });
    return () => controller.abort();
  }, [expanded, retryNumber]);

  const samples = report?.samples || [];
  const position = Math.min(selected, Math.max(0, samples.length - 1));
  const frame = samples[position];

  useEffect(() => {
    if (!playing || !expanded || samples.length < 2) return undefined;
    const timer = window.setInterval(() => {
      setSelected((previous) => {
        if (previous >= samples.length - 1) {
          setPlaying(false);
          return previous;
        }
        return previous + 1;
      });
    }, 1100);
    return () => window.clearInterval(timer);
  }, [playing, expanded, samples.length]);

  const move = (next) => {
    setPlaying(false);
    setSelected(Math.max(0, Math.min(next, samples.length - 1)));
  };

  return (
    <section className="rounded-xl border border-[#d9e6df] bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#173e35]">📹 Roboflow camera verification</h2>
          <p className="mt-1 text-xs text-[#60766e]">Your real saved model predictions — separate from student booking data</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-[#fff1ce] px-3 py-1.5 text-xs font-bold text-[#754a00]">RECORDED — NOT LIVE</span>
          {compact ? (
            <button
              type="button"
              onClick={() => { setExpanded((open) => !open); setPlaying(false); }}
              className="rounded-lg bg-[#185b49] px-3 py-2 text-xs font-semibold text-white"
            >
              {expanded ? "Hide detections" : "Show detections"}
            </button>
          ) : null}
        </div>
      </div>

      {expanded ? (
        <div className="mt-4">
          {error ? (
            <div role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
              <strong>Cannot read saved Roboflow samples.</strong>
              <p className="mt-1">{error}</p>
              <p className="mt-2 text-xs">Start the standalone CV server on port 8001, then retry.</p>
              <button
                type="button"
                className="mt-3 rounded-lg bg-[#185b49] px-3 py-2 text-xs font-semibold text-white"
                onClick={() => { setLoading(true); setRetryNumber((n) => n + 1); }}
              >
                Retry connection
              </button>
            </div>
          ) : loading ? (
            <p className="rounded-lg bg-[#f2f6f4] p-4 text-sm text-[#5d756c]">Loading saved detections…</p>
          ) : frame ? (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(290px,1fr)]">
              <div>
                <img
                  src={`${CV_SERVER}/api/cv-preview/frame/${position}`}
                  alt={`Roboflow detected chairs at ${frame.video_time_seconds.toFixed(1)} seconds of recorded video`}
                  className="w-full rounded-lg bg-[#172923] object-contain"
                />
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => move(position - 1)}
                    disabled={position === 0}
                    className="rounded-lg bg-[#e6efeb] px-3 py-2 text-xs font-semibold disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="rounded-lg bg-[#185b49] px-3 py-2 text-xs font-semibold text-white"
                    onClick={() => {
                      if (position === samples.length - 1 && !playing) setSelected(0);
                      setPlaying((old) => !old);
                    }}
                  >
                    {playing ? "Pause" : "▶ Play samples"}
                  </button>
                  <button
                    type="button"
                    onClick={() => move(position + 1)}
                    disabled={position >= samples.length - 1}
                    className="rounded-lg bg-[#e6efeb] px-3 py-2 text-xs font-semibold disabled:opacity-40"
                  >
                    Next
                  </button>
                  <input
                    aria-label="Select sampled video frame"
                    type="range"
                    min="0"
                    max={samples.length - 1}
                    value={position}
                    onChange={(event) => move(Number(event.target.value))}
                    className="min-w-24 flex-1 accent-[#185b49]"
                  />
                  <span className="text-xs font-bold text-[#173e35]">{frame.video_time_seconds.toFixed(1)}s</span>
                </div>
                <p className="mt-2 text-xs text-[#65766f]">Sample {position + 1}/{samples.length} · sampled inference, not continuous tracking</p>
              </div>
              <div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  {[
                    ["Available", frame.counts.available, "text-green-700"],
                    ["Occupied", frame.counts.occupied, "text-red-700"],
                    ["Unknown", frame.counts.unknown, "text-yellow-700"],
                  ].map(([label, count, color]) => (
                    <div key={label} className="rounded-lg bg-[#f2f6f4] px-2 py-3">
                      <div className={`text-2xl font-bold ${color}`}>{count}</div>
                      <div className="text-xs text-[#65766f]">{label}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {frame.detections.map((detection) => (
                    <div
                      key={`${position}-${detection.detection_label}`}
                      title={`${detection.class_name} · ${Math.round(detection.confidence * 100)}% confidence`}
                      className={`rounded-lg border px-2 py-2 text-center text-xs font-semibold ${STATUS_CLASSES[detection.state] || STATUS_CLASSES.UNKNOWN}`}
                    >
                      <div>{detection.detection_label}</div>
                      <div className="mt-1">{detection.state.toLowerCase()}</div>
                    </div>
                  ))}
                </div>
                <p className="mt-3 rounded-lg bg-[#fff7e7] p-3 text-xs leading-5 text-[#755218]">
                  <strong>Not reservable:</strong> D01–D08 reset each frame. Since this video camera moved, these are not permanent seat IDs. Your Study Spot S01–S08 indicators and RSVP stay unchanged.
                </p>
                <p className="mt-2 text-xs text-[#65766f]">Model: {report.model_id}</p>
              </div>
            </div>
          ) : null}
          {compact ? (
            <p className="mt-3 text-xs"><Link className="font-semibold text-[#185b49] underline" to="/cv-monitor">Open the full CV monitoring view</Link></p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
