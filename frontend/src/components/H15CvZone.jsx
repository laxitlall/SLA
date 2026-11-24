import { useEffect, useState } from "react";
import ZoneCard from "./ZoneCard";

const CV_API = import.meta.env.VITE_CV_API_URL || "http://127.0.0.1:8001";

function overlayH15(zone, latest) {
  if (zone.name !== "Hostel 15" || !zone.rooms?.length || !latest?.seats?.length) return zone;
  const rooms = zone.rooms.map((room, idx) => {
    // H15 Study Room 1 ONLY: maintain teammates' other room data and RSVP IDs.
    if (idx !== 0) return room;
    const originalIds = room.seats || [];
    const seats = latest.seats.slice(0, 8).map((obs, i) => ({
      ...(originalIds[i] || {}),
      seat_id: originalIds[i]?.seat_id || `${room.room_id}-S${String(i + 1).padStart(2,"0")}`,
      computed_state: ["AVAILABLE", "OCCUPIED", "UNKNOWN"].includes(obs.state) ? obs.state : "UNKNOWN",
      confidence_score: obs.confidence ?? null,
      source: "CV_RECORDED_DEMO",
    }));
    return {
      ...room, seats, totalSeats: seats.length,
      availableSeats: seats.filter(s => s.computed_state === "AVAILABLE").length,
      occupiedSeats: seats.filter(s => s.computed_state === "OCCUPIED").length,
      unknownSeats: seats.filter(s => s.computed_state === "UNKNOWN").length,
      spotHeldSeats: 0,
    };
  });
  const totalSeats = rooms.reduce((n, r) => n + r.totalSeats, 0);
  const availableSeats = rooms.reduce((n, r) => n + r.availableSeats, 0);
  return {
    ...zone, rooms, totalSeats, availableSeats,
    spotHeldSeats: rooms.reduce((n,r) => n + (r.spotHeldSeats || 0), 0),
    occupancyPercentage: totalSeats > 0 ? Math.round(100 * (totalSeats - availableSeats) / totalSeats) : 0,
  };
}

export default function H15CvZone(props) {
  const [latest, setLatest] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (props.zone.name !== "Hostel 15") return;
    let disposed = false;
    let controller = null;
    async function refresh() {
      if (controller) controller.abort();
      controller = new AbortController();
      try {
        const r = await fetch(`${CV_API}/api/cv/h15-room-1/seat-status`, {
          signal: controller.signal, cache: "no-store",
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (!disposed) { setLatest(data); setError(false); }
      } catch (e) {
        if (!disposed && e?.name !== "AbortError") setError(true);
      }
    }
    refresh();
    const timer = setInterval(refresh, 2500);
    return () => { disposed = true; clearInterval(timer); controller?.abort(); };
  }, [props.zone.name]);
  return (
    <div>
      <ZoneCard {...props} zone={overlayH15(props.zone, latest)} />
      {props.zone.name === "Hostel 15" && (
        <p className="px-3 py-1 text-xs text-gray-500" aria-live="polite">
          H15 Study Room 1: {error ? "CV feed disconnected — displaying last known/fallback data" : latest?.status === "REPLAYING" ? `Recorded video replay · frame ${latest.frame_index + 1} · updating ~6 s` : latest?.status === "CALIBRATING" ? "Finding eight fixed chair positions…" : latest?.status === "FINISHED" ? "Recorded replay finished" : "Awaiting video upload"}
          {latest?.mapping === "AUTO_PROPOSED_UNVERIFIED" ? " · automatic mapping (review before real use)" : ""}
        </p>
      )}
    </div>
  );
}
