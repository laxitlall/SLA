import { Link } from "react-router";
import CvDemoPanel from "../components/CvDemoPanel";

export default function CvMonitoring() {
  return (
    <div className="min-h-screen bg-[#eef4f1] text-[#173e35]">
      <header className="border-b border-[#dfe8e4] bg-white">
        <div className="mx-auto flex max-w-[1380px] flex-wrap items-center justify-between gap-3 px-5 py-5 lg:px-10">
          <div>
            <p className="text-sm text-[#729087]">Study Spot / Camera monitoring</p>
            <h1 className="text-2xl font-bold">CV Monitoring</h1>
          </div>
          <Link className="rounded-lg bg-[#185b49] px-4 py-2 font-semibold text-white hover:bg-[#124837]" to="/room">
            Back to study rooms
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-[1380px] px-5 py-7 lg:px-10">
        <CvDemoPanel />
      </main>
    </div>
  );
}
