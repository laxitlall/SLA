import { createContext, useState } from "react";
export const CvAdminContext = createContext("");

const CV_API = import.meta.env.VITE_CV_API_URL || "http://127.0.0.1:8001";

export default function CvAccessGate({children}) {
  const [password, setPassword] = useState("");
  const [allowed, setAllowed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const check = async (event) => {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const response = await fetch(`${CV_API}/api/cv/h15-room-1/admin-check`, {
        method: "POST", headers: { "X-CV-Upload-Password": password }, cache: "no-store",
      });
      if (!response.ok) throw new Error(response.status === 401 ? "Incorrect admin password" : `Admin server returned HTTP ${response.status}`);
      setAllowed(true);
    } catch(e) { setError(e?.message || "Cannot reach admin service"); }
    finally { setBusy(false); }
  };
  if (allowed) return <CvAdminContext.Provider value={password}>{children}</CvAdminContext.Provider>;
  return (
    <form onSubmit={check} className="mx-auto max-w-md rounded-xl border bg-white p-6 shadow-sm">
      <h2 className="text-lg font-bold text-[#173e35]">Admin camera monitoring</h2>
      <p className="my-2 text-sm text-gray-600">Raw video detections and upload are restricted. Students can view seat status without this page.</p>
      <input type="password" minLength={16} required value={password} autoComplete="off"
        onChange={e=>setPassword(e.target.value)} placeholder="CV upload admin password"
        className="my-3 w-full rounded-md border border-gray-300 p-2" />
      {error && <p role="alert" className="mb-2 text-red-700 text-sm">{error}</p>}
      <button disabled={busy} type="submit" className="rounded-lg bg-[#185b49] px-4 py-2 text-white font-bold disabled:opacity-50">{busy ? "Checking…" : "Open monitoring"}</button>
    </form>
  );
}
