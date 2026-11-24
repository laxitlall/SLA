import { useEffect, useState } from "react";
import { apiCreateStudyCircle, apiStudyCircleBookings, apiStudyCircleSlots, apiRespondStudyCircle, apiCancelStudyCircle, apiGetFriendsOverview, apiSendStudyCircleReminder } from "../utils/api";
import { studyCircleWhatsAppUrl, downloadStudyCircleCalendar } from "../utils/studyCircleReminders";

const HOURS = Array.from({ length: 13 }, (_, i) => `${String(i + 9).padStart(2, "0")}:00`);
const CAPACITY = 6;
function localDate(offset = 0) {
  const today = new Date();
  today.setDate(today.getDate() + offset);
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}
function formatSlot(value) {
  const h = Number(value.slice(0, 2));
  const label = (v) => `${v % 12 || 12} ${v < 12 ? "AM" : "PM"}`;
  return `${label(h)} – ${label(h + 1)}`;
}

export default function StudyCircles({ user }) {
  const [date, setDate] = useState(() => localDate());
  const [slot, setSlot] = useState("18:00");
  const [topic, setTopic] = useState("Group Study Session");
  const [selectedFriends, setSelectedFriends] = useState([]);
  const [friends, setFriends] = useState([]);
  const [bookedSlots, setBookedSlots] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reminderDrafts, setReminderDrafts] = useState({});
  const roll = user?.roll_number || "";

  async function refresh() {
    if (!roll) return;
    setLoading(true);
    try {
      const [slotsData, mine] = await Promise.all([
        apiStudyCircleSlots(date), apiStudyCircleBookings(roll),
      ]);
      setBookedSlots(slotsData.booked_slots || []);
      setBookings(mine.bookings || []);
      setError("");
    } catch (e) {
      setError(e.message || "Booking service unavailable.");
      setBookedSlots([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    apiGetFriendsOverview(roll).then((result) => {
      if (active) setFriends(result.friends || []);
    }).catch(() => {});
    return () => { active = false; };
  }, [roll]);

  useEffect(() => {
    if (!roll) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([apiStudyCircleSlots(date), apiStudyCircleBookings(roll)])
      .then(([slotsData, mine]) => {
        if (!cancelled) {
          setBookedSlots(slotsData.booked_slots || []);
          setBookings(mine.bookings || []);
          setError("");
        }
      })
      .catch((e) => { if (!cancelled) setError(e.message || "Booking service unavailable."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [date, roll]);

  async function act(task, success) {
    setBusy(true); setError(""); setNotice("");
    try {
      await task();
      setNotice(success);
      await refresh();
    } catch (e) {
      setError(e.message || "Action failed.");
    } finally { setBusy(false); }
  }

  const booked = bookedSlots.includes(slot);
  const selectedDateStart = new Date(`${date}T${slot}:00`);
  const past = selectedDateStart.getTime() <= Date.now();
  const owned = bookings.filter((b) => b.organizer_roll === roll);
  const invited = bookings.filter((b) => b.organizer_roll !== roll);

  if (!user) return null;
  return (
    <section id="study-circles" className="mt-9 rounded-2xl border border-[#cbded6] bg-white p-5 sm:p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-wide text-[#40816e]">New · Study Spot</div>
          <h2 className="mt-1 text-2xl font-bold text-greenfont">Study Circles — Book a Group Room</h2>
          <p className="mt-1 text-sm text-gray-500">Hostel 15 · Study Room 2 · One-hour slots · Up to {CAPACITY} students</p>
          <p className="mt-1 text-xs text-gray-500">Prototype reservations, not official campus room bookings. Room 1 CV monitoring is separate.</p>
        </div>
        <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-900">First confirmed booking wins</span>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <form onSubmit={(e) => {
          e.preventDefault();
          if (booked || past) return;
          act(() => apiCreateStudyCircle({organizer_roll: roll, date, slot, topic: topic.trim(), invitees: selectedFriends}), "Room reserved! Invitations are ready for your friends.");
        }} className="space-y-4 rounded-xl bg-roomgreen p-4 border border-[#dcebe5]">
          <h3 className="font-bold text-greenfont">Reserve a time slot</h3>
          <div>
            <label htmlFor="circle-date" className="mb-1 block text-xs font-semibold text-gray-700">Date</label>
            <input id="circle-date" type="date" required value={date} min={localDate()} max={localDate(14)} onChange={(e) => setDate(e.target.value)} className="w-full rounded-lg border border-[#cdd8d3] bg-white px-3 py-2 text-sm text-greenfont" />
          </div>
          <div>
            <label htmlFor="circle-slot" className="mb-1 block text-xs font-semibold text-gray-700">Time · IST</label>
            <select id="circle-slot" value={slot} onChange={(e) => setSlot(e.target.value)} className="w-full rounded-lg border border-[#cdd8d3] bg-white px-3 py-2 text-sm text-greenfont">
              {HOURS.map((t) => <option key={t} value={t}>{formatSlot(t)} {bookedSlots.includes(t) ? "· Booked" : ""}</option>)}
            </select>
            <div className={`mt-1 text-xs font-semibold ${booked || past ? "text-red-700" : "text-green-700"}`}>
              {loading ? "Checking slots…" : booked ? "Already booked — choose a different time" : past ? "This time has already started" : "Available for booking"}
            </div>
          </div>
          <div>
            <label htmlFor="circle-topic" className="mb-1 block text-xs font-semibold text-gray-700">Study topic</label>
            <input id="circle-topic" value={topic} required minLength={3} maxLength={100} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. CS601 Graphs + DP" className="w-full rounded-lg border border-[#cdd8d3] bg-white px-3 py-2 text-sm text-greenfont" />
          </div>
          <div>
            <div className="mb-1 text-xs font-semibold text-gray-700">Invite friends ({selectedFriends.length}/{CAPACITY - 1})</div>
            {friends.length ? (
              <div className="flex flex-wrap gap-2">
                {friends.map((friend) => {
                  const selected = selectedFriends.includes(friend.roll_number);
                  return (
                    <button key={friend.roll_number} type="button" onClick={() => setSelectedFriends((prev) => selected ? prev.filter((x) => x !== friend.roll_number) : prev.length >= CAPACITY - 1 ? prev : [...prev, friend.roll_number])}
                      className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${selected ? "border-green-600 bg-green-100 text-green-900" : "border-gray-300 bg-white text-gray-600"}`}>
                      {selected ? "✓ " : "+ "}{friend.full_name || friend.roll_number}
                    </button>
                  );
                })}
              </div>
            ) : <p className="text-xs text-gray-500">No accepted friends found yet. You can still reserve the room and invite friends later in a future version.</p>}
          </div>
          <button type="submit" disabled={busy || loading || booked || past || !topic.trim()} className="w-full rounded-xl bg-greenfont px-4 py-3 font-bold text-sm text-white disabled:cursor-not-allowed disabled:opacity-50">
            {busy ? "Saving…" : "Confirm room reservation"}
          </button>
        </form>

        <div className="space-y-3 rounded-xl border border-[#e3e8e5] p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-bold text-greenfont">My study circles</h3>
            <button type="button" onClick={refresh} disabled={loading || busy} className="text-xs font-semibold text-lightgreenfont underline">Refresh</button>
          </div>
          {bookings.length === 0 && <p className="text-sm text-gray-500">No bookings or invitations yet.</p>}
          {owned.map((b) => <div key={b.booking_id} className="rounded-xl border border-green-200 bg-green-50 p-3">
            <div className="text-sm font-bold text-greenfont">✓ {b.topic}</div>
            <p className="mt-1 text-xs text-gray-600">{b.date} · {formatSlot(b.slot)} · {b.room_name}</p>
            <p className="mt-2 text-xs text-gray-600">Group: You + {(b.invitees || []).filter((i) => i.status === "ACCEPTED").length} confirmed · {(b.invitees || []).filter((i) => i.status === "PENDING").length} pending</p>
            {!!b.invitees?.length && <div className="mt-1 text-xs text-gray-500">{b.invitees.map((i) => `${friends.find((f) => f.roll_number === i.roll_number)?.full_name || i.roll_number} (${i.status.toLowerCase()})`).join(", ")}</div>}
            {!!b.invitees?.length && (
              <div className="mt-3 rounded-lg border border-[#c6dfd3] bg-white p-2.5">
                <label htmlFor={`circle-reminder-${b.booking_id}`} className="block text-xs font-bold text-greenfont">Send a message to invited friends' profiles</label>
                <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                  <input id={`circle-reminder-${b.booking_id}`} type="text" maxLength={220}
                    value={reminderDrafts[b.booking_id] ?? "Study circle reminder: please arrive 5 minutes early."}
                    onChange={(e) => setReminderDrafts((prev) => ({ ...prev, [b.booking_id]: e.target.value }))}
                    className="min-w-0 flex-1 rounded-lg border border-[#cdd8d3] px-3 py-2 text-xs"
                    placeholder="Type a short reminder…" />
                  <button type="button" disabled={busy || !(reminderDrafts[b.booking_id] ?? "Study circle reminder: please arrive 5 minutes early.").trim()}
                    onClick={() => act(() => apiSendStudyCircleReminder(b.booking_id, roll,
                      reminderDrafts[b.booking_id] ?? "Study circle reminder: please arrive 5 minutes early."),
                      "Reminder saved. Invited friends will see it on their profile.")}
                    className="rounded-lg bg-greenfont px-3 py-2 text-xs font-bold text-white disabled:opacity-50">
                    Send in-app reminder
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-gray-500">Visible in invited students' Upcoming Study RSVPs section. No phone number needed.</p>
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <a href={studyCircleWhatsAppUrl(b)} target="_blank" rel="noopener noreferrer" className="rounded-lg bg-[#1f7a50] px-3 py-1.5 text-xs font-bold text-white">WhatsApp reminder</a>
              <button type="button" onClick={() => downloadStudyCircleCalendar(b)} className="rounded-lg border border-green-300 bg-white px-3 py-1.5 text-xs font-bold text-green-800">Add 15-min calendar alert</button>
              <button type="button" disabled={busy} onClick={() => { if (window.confirm("Cancel this booking and release the time slot?")) act(() => apiCancelStudyCircle(b.booking_id, roll), "Booking cancelled. Slot is available again."); }} className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-bold text-red-700">Cancel booking</button>
            </div>
          </div>)}
          {invited.map((b) => {
            const invite = b.invitees.find((i) => i.roll_number === roll);
            return <div key={b.booking_id} className="rounded-xl border border-blue-200 bg-blue-50 p-3">
              <div className="text-sm font-bold text-greenfont">Invitation · {b.topic}</div>
              <p className="mt-1 text-xs text-gray-600">{b.date} · {formatSlot(b.slot)} · Organizer: {b.organizer_roll}</p>
              <p className="mt-1 text-xs text-gray-600">Your response: {invite?.status || "UNKNOWN"}</p>
              {invite?.status === "ACCEPTED" && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <a href={studyCircleWhatsAppUrl(b)} target="_blank" rel="noopener noreferrer" className="rounded-lg bg-[#1f7a50] px-3 py-1.5 text-xs font-bold text-white">WhatsApp reminder</a>
                  <button type="button" onClick={() => downloadStudyCircleCalendar(b)} className="rounded-lg border border-green-300 bg-white px-3 py-1.5 text-xs font-bold text-green-800">Add 15-min calendar alert</button>
                </div>
              )}
              {invite?.status === "PENDING" && <div className="mt-2 flex gap-2">
                <button disabled={busy} type="button" onClick={() => act(() => apiRespondStudyCircle(b.booking_id, roll, "ACCEPTED"), "Invitation accepted!")} className="rounded-lg bg-greenfont px-3 py-1.5 text-xs font-bold text-white">Accept</button>
                <button disabled={busy} type="button" onClick={() => act(() => apiRespondStudyCircle(b.booking_id, roll, "DECLINED"), "Invitation declined.")} className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-bold text-gray-700">Decline</button>
              </div>}
            </div>;
          })}
          <p className="text-xs text-gray-500">WhatsApp opens a prewritten message; you choose the chat and tap Send. It does not send automatically. The calendar file includes a reminder 15 minutes before the session (once added to your calendar).</p>
          <p className="text-xs text-gray-500">Invitations update on refresh. A confirmed booking blocks the full hour, even when friends haven't responded yet.</p>
        </div>
      </div>
      {error && <div role="alert" className="mt-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
      {notice && <div role="status" className="mt-4 rounded-lg border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-800">{notice}</div>}
    </section>
  );
}
