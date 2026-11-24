import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { apiStudyCircleBookings, apiRespondStudyCircle } from "../utils/api";

function describeSlot(value) {
  const hour = Number(value?.slice(0, 2));
  if (!Number.isInteger(hour) || hour < 0 || hour > 23) return value || "Unknown time";
  const display = (n) => `${n % 12 || 12} ${n < 12 ? "AM" : "PM"}`;
  return `${display(hour)} – ${display(hour + 1)}`;
}

function upcoming(booking) {
  if (!booking?.date || !booking?.slot) return false;
  const start = new Date(`${booking.date}T${booking.slot}:00+05:30`);
  return !Number.isNaN(start.getTime()) && start.getTime() + 60 * 60 * 1000 > Date.now();
}

/** Displays MongoDB Study Circle invitations and organizer reminders on the student's own Profile page. */
export default function StudyCircleProfileInbox({ userRoll }) {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const roll = (userRoll || "").toUpperCase();

  const refresh = useCallback(async ({ quiet = false } = {}) => {
    if (!roll) return;
    if (!quiet) setLoading(true);
    try {
      const data = await apiStudyCircleBookings(roll);
      setBookings(data.bookings || []);
      setError("");
    } catch (e) {
      setError(e.message || "Unable to load Study Circles.");
      if (!quiet) setBookings([]);
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [roll]);

  useEffect(() => {
    refresh();
    const timer = setInterval(() => refresh({ quiet: true }), 15000);
    return () => clearInterval(timer);
  }, [refresh]);

  const sessions = useMemo(() => bookings.filter(upcoming).sort((a, b) =>
    `${a.date}T${a.slot}`.localeCompare(`${b.date}T${b.slot}`)
  ), [bookings]);

  async function respond(bookingId, decision) {
    setBusyId(bookingId);
    setError("");
    setNotice("");
    try {
      await apiRespondStudyCircle(bookingId, roll, decision);
      setNotice(decision === "ACCEPTED" ? "Invitation accepted." : "Invitation declined.");
      await refresh({ quiet: true });
    } catch (e) {
      setError(e.message || "Unable to respond to invitation.");
    } finally {
      setBusyId("");
    }
  }

  return (
    <div className="mt-3 space-y-3" aria-label="My Study Circles notifications">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-[#36594f]">Study Circles invitations & messages</span>
        <button type="button" onClick={() => refresh()} disabled={loading} className="text-xs font-semibold text-lightgreenfont underline disabled:opacity-50">Refresh</button>
      </div>
      {loading && <p className="text-xs text-gray-500">Loading Study Circles…</p>}
      {!loading && sessions.length === 0 && !error && (
        <p className="text-xs text-gray-500">No upcoming Study Circles invitations or bookings.</p>
      )}
      {sessions.map((booking) => {
        const organizer = booking.organizer_roll?.toUpperCase() === roll;
        const invitation = (booking.invitees || []).find((i) => i.roll_number?.toUpperCase() === roll);
        const reminders = (booking.reminders || []).filter((r) => (r.recipient_rolls || []).some((id) => id.toUpperCase() === roll));
        const status = organizer ? "ORGANIZER" : invitation?.status || "UNKNOWN";
        return (
          <div key={booking.booking_id} className="rounded-xl border border-[#dcebe5] bg-roomgreen p-3.5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <span className="text-sm font-bold text-greenfont">{booking.topic}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${status === "PENDING" ? "bg-amber-100 text-amber-800" : status === "DECLINED" ? "bg-gray-200 text-gray-700" : "bg-green-100 text-green-800"}`}>
                {status === "PENDING" ? "Invitation pending" : status === "ACCEPTED" ? "Confirmed" : status === "ORGANIZER" ? "Your booking" : status}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-600">📍 {booking.zone_name} · {booking.room_name}</p>
            <p className="mt-1 text-xs text-gray-600">📅 {booking.date} · {describeSlot(booking.slot)} IST</p>
            {!organizer && <p className="mt-1 text-xs text-gray-600">Invited by {booking.organizer_roll}</p>}
            {!organizer && status === "PENDING" && (
              <div className="mt-2 flex gap-2">
                <button type="button" disabled={!!busyId} onClick={() => respond(booking.booking_id, "ACCEPTED")} className="rounded-lg bg-greenfont px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50">Accept</button>
                <button type="button" disabled={!!busyId} onClick={() => respond(booking.booking_id, "DECLINED")} className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-semibold text-gray-700 disabled:opacity-50">Decline</button>
              </div>
            )}
            {!organizer && reminders.length > 0 && (
              <div className="mt-3 space-y-2 border-t border-[#d6e4dd] pt-2">
                <div className="text-xs font-bold text-greenfont">Messages from organizer</div>
                {reminders.slice(-3).map((reminder) => (
                  <div key={reminder.reminder_id} className="rounded-lg border border-green-200 bg-white px-3 py-2">
                    <p className="text-xs text-gray-800">{reminder.message}</p>
                    <p className="mt-1 text-[10px] text-gray-500">Sent {new Date(reminder.sent_at).toLocaleString()}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      {error && <p role="alert" className="rounded-lg bg-red-50 px-2 py-2 text-xs text-red-700">{error}</p>}
      {notice && <p role="status" className="rounded-lg bg-green-50 px-2 py-2 text-xs text-green-700">{notice}</p>}
      <Link to="/study-circles" className="inline-block text-xs font-bold text-lightgreenfont underline">Open Study Circles →</Link>
    </div>
  );
}
