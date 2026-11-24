import { useContext, useEffect, useState } from "react";
import { CvAdminContext } from "./CvAccessGate";

const API = "http://127.0.0.1:8001";

export default function CvVideoUploader() {
  const [password, setPassword] = useState("");
  const gatePassword = useContext(CvAdminContext);
  useEffect(() => { if (gatePassword) setPassword(gatePassword); }, [gatePassword]);
  const [video, setVideo] = useState(null);
  const [interval, setIntervalSeconds] = useState(10);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [frameUrl, setFrameUrl] = useState(null);

  async function upload(e) {
    e.preventDefault();
    if (!video || !password) return;
    setBusy(true);
    setError("");
    setJob(null);
    setJobId(null);
    setFrameUrl(null);
    const data = new FormData();
    data.append("file", video);
    data.append("interval_seconds", String(interval));
    data.append("max_samples", "36");
    data.append("confidence_threshold", "0.50");
    try {
      const res = await fetch(`${API}/api/cv/demo-videos/upload`, {
        method: "POST",
        headers: { "X-CV-Upload-Password": password },
        body: data,
      });
      const reply = await res.json();
      if (!res.ok) throw new Error(typeof reply.detail === "string" ? reply.detail : `HTTP ${res.status}`);
      setJobId(reply.job_id);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!jobId || !password) return;
    let canceled = false;
    let timer;
    const poll = async () => {
      try {
        const result = await fetch(`${API}/api/cv/demo-videos/jobs/${jobId}`, {
          headers: { "X-CV-Upload-Password": password },
          cache: "no-store",
        });
        if (!result.ok) throw new Error(`Job status HTTP ${result.status}`);
        const state = await result.json();
        if (canceled) return;
        setJob(state);
        if (["queued", "processing"].includes(state.status)) timer = setTimeout(poll, 2000);
      } catch (err) {
        if (!canceled) setError(String(err.message || err));
      }
    };
    poll();
    return () => { canceled = true; clearTimeout(timer); };
  }, [jobId, password]);

  useEffect(() => {
    if (!jobId || !password || job?.latest_index == null) return;
    let canceled = false;
    let objectUrl;
    fetch(`${API}/api/cv/demo-videos/jobs/${jobId}/frames/${job.latest_index}`, {
      headers: { "X-CV-Upload-Password": password }, cache: "no-store"
    }).then((res) => {
      if (!res.ok) throw new Error(`Frame HTTP ${res.status}`);
      return res.blob();
    }).then((blob) => {
      objectUrl = URL.createObjectURL(blob);
      if (!canceled) setFrameUrl(objectUrl);
      else URL.revokeObjectURL(objectUrl);
    }).catch(() => {});
    return () => { canceled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [jobId, job?.latest_index, password]);

  return (
    <section className="mb-6 rounded-2xl border border-[#dae7df] bg-white p-6 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[#173e35]">H15 Study Room 1 — upload prerecorded video</h2>
          <p className="mt-1 text-sm text-gray-600">Admin-only upload. Actual RF-DETR predictions are saved to MongoDB.</p>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800">RECORDED • NOT LIVE</span>
      </div>
      <form onSubmit={upload} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
        <label className="text-sm font-semibold text-[#173e35]">
          Admin upload password
          <input type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-gray-300 p-2" placeholder="Not saved in browser" required minLength={16}/>
        </label>
        <label className="text-sm font-semibold text-[#173e35]">
          Select 4–5 minute MP4
          <input type="file" accept="video/mp4,.mp4" onChange={(e) => setVideo(e.target.files?.[0] || null)}
            className="mt-1 w-full rounded-lg border border-gray-300 p-2" required />
        </label>
        <button type="submit" disabled={busy} className="rounded-lg bg-[#185b49] px-5 py-2.5 font-bold text-white disabled:opacity-50">
          {busy ? "Uploading…" : "Process video"}
        </button>
        <label className="text-sm text-gray-600 md:col-span-3">
          Sample every {interval} seconds (maximum 36 model calls)
          <input type="range" min="6" max="30" step="2" value={interval}
            onChange={(e) => setIntervalSeconds(Number(e.target.value))} className="ml-3 align-middle"/>
        </label>
      </form>
      {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {job && <div className="mt-4 rounded-lg bg-[#eef4f1] p-4 text-sm text-[#173e35]">
        <p><strong>Status:</strong> {job.status} • {job.finished_samples} / {job.total_samples ?? "?"} sampled frames processed</p>
        {job.latest_counts && <p className="mt-1">Latest frame: {job.latest_counts.available} available detections, {job.latest_counts.occupied} occupied, {job.latest_counts.unknown} unknown.</p>}
        {job.status === "failed" && <p className="mt-2 text-red-700">{job.error || "Processing failed"}</p>}
        <p className="mt-2 text-xs text-amber-900">Detection numbers D01… reset each frame and cannot yet change permanent S01… seat identities. RSVP is untouched.</p>
      </div>}
      {frameUrl && <img src={frameUrl} alt="Actual last sampled Roboflow predictions, not permanent seat identities" className="mt-4 max-h-[480px] w-full rounded-lg object-contain"/>}
    </section>
  );
}
