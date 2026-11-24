// Study Spot Study Circles: explicit WhatsApp share + local calendar reminder.
// No phone numbers, WhatsApp API credentials, or background messaging required.

function formatHour(hour) {
  const h = hour % 12 || 12;
  return `${h} ${hour < 12 ? "AM" : "PM"}`;
}

export function studyCircleReminderText(booking) {
  const date = String(booking.date || "");
  const parts = date.split("-");
  const readableDate = parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : date;
  const hour = Number(String(booking.slot || "").slice(0, 2));
  const when = Number.isInteger(hour) && hour >= 0 && hour <= 23
    ? `${formatHour(hour)} – ${formatHour(hour + 1)} IST`
    : String(booking.slot || "");
  const location = `${booking.zone_name || "Hostel 15"}, ${booking.room_name || "Study Room 2"}`;
  return [
    "📚 Study Spot — Study Circle Reminder",
    `Topic: ${booking.topic || "Group study"}`,
    `Date: ${readableDate}`,
    `Time: ${when}`,
    `Place: ${location}`,
    `Organizer: ${booking.organizer_roll || "Study Circle organizer"}`,
    "Please check your Study Spot invitation and arrive on time.",
  ].join("\n");
}

export function studyCircleWhatsAppUrl(booking) {
  // WhatsApp click-to-chat: opens a prefilled draft, not an automatic send.
  return `https://wa.me/?text=${encodeURIComponent(studyCircleReminderText(booking))}`;
}

function escapeIcs(value) {
  return String(value ?? "")
    .replace(/\\/g, "\\\\")
    .replace(/\r?\n/g, "\\n")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,");
}

function toIcsUtc(milliseconds) {
  return new Date(milliseconds).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

export function studyCircleCalendarIcs(booking, now = new Date()) {
  const parts = String(booking.date || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const hours = String(booking.slot || "").match(/^(\d{2}):00$/);
  if (!parts || !hours) throw new Error("Invalid booking date or time.");
  const [, year, month, day] = parts.map(Number);
  const hour = Number(hours[1]);
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour < 0 || hour > 23) {
    throw new Error("Invalid booking date or time.");
  }
  // Booking is in Asia/Kolkata (UTC+05:30), independent of browser time zone.
  const start = Date.UTC(year, month - 1, day, hour, 0) - (5 * 60 + 30) * 60_000;
  const correctDate = new Date(Date.UTC(year, month - 1, day));
  if (correctDate.getUTCFullYear() !== year || correctDate.getUTCMonth() !== month - 1 || correctDate.getUTCDate() !== day) {
    throw new Error("Invalid booking date.");
  }
  const id = String(booking.booking_id || `${booking.date}-${booking.slot}`).replace(/[^a-zA-Z0-9_-]/g, "-");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "CALSCALE:GREGORIAN",
    "PRODID:-//Study Spot//Study Circles//EN",
    "BEGIN:VEVENT",
    `UID:study-circle-${id}@studyspot.local`,
    `DTSTAMP:${toIcsUtc(now.getTime())}`,
    `DTSTART:${toIcsUtc(start)}`,
    `DTEND:${toIcsUtc(start + 60 * 60_000)}`,
    `SUMMARY:${escapeIcs(`Study Spot: ${booking.topic || "Group study"}`)}`,
    `LOCATION:${escapeIcs(`${booking.zone_name || "Hostel 15"}, ${booking.room_name || "Study Room 2"}`)}`,
    `DESCRIPTION:${escapeIcs("Study Circle booking prototype. Check Study Spot for participants and status.")}`,
    "BEGIN:VALARM",
    "TRIGGER:-PT15M",
    "ACTION:DISPLAY",
    "DESCRIPTION:Your study circle starts in 15 minutes",
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.join("\r\n") + "\r\n";
}

export function downloadStudyCircleCalendar(booking) {
  const text = studyCircleCalendarIcs(booking);
  const blob = new Blob([text], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `study-circle-${booking.date}-${booking.slot.replace(":", "")}.ics`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  }
}
