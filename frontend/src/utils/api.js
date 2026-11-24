const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const USER_STORAGE_KEY = "studyspot_current_user";
const FALLBACK_STORE_KEY = "studyspot_fallback_store_v3";

export function getCurrentUser() {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    let data;
    if(raw){
      data = JSON.parse(raw);
    }
    else{
      data = null;
    }
    return data;
  } catch {
    return null;
  }
}

export function setCurrentUser(user) {
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

export function logoutUser() {
  localStorage.removeItem(USER_STORAGE_KEY);
}

function getDefaultFallbackStore() {
  return {
    users: [
      {
        roll_number: "26M0821",
        full_name: "Laxit Lall",
        email: "26m0821@iitb.ac.in",
        password: "password123",
        branch: "Computer Science",
        hostel: "Hostel 15",
        bio: "Ghare jaake sutti babu",
      },
      {
        roll_number: "26M0829",
        full_name: "Ayush Raj",
        email: "26m0829@iitb.ac.in",
        password: "password123",
        branch: "Computer Science",
        hostel: "Hostel 15",
        bio: "Ghare jaake sutti babu",
      },
      {
        roll_number: "26M0828",
        full_name: "sushil kumar",
        email: "26m0828@iitb.ac.in",
        password: "password123",
        branch: "Computer Science",
        hostel: "Hostel 10",
        bio: "Ghare jaake sutti babu",
      },
    ],
    friendships: [],
    active_hands: [],
    rsvps: [],
  };
}

function readFallbackStore() {
  try {
    const raw = localStorage.getItem(FALLBACK_STORE_KEY);
    const store = raw ? JSON.parse(raw) : getDefaultFallbackStore();
    const now = Date.now();
    store.active_hands = (store.active_hands || []).filter(
      (h) => new Date(h.expires_at).getTime() > now
    );
    localStorage.setItem(FALLBACK_STORE_KEY, JSON.stringify(store));
    return store;
  } catch {
    return getDefaultFallbackStore();
  }
}

function writeFallbackStore(store) {
  localStorage.setItem(FALLBACK_STORE_KEY, JSON.stringify(store));
}

function enrichHand(h, users) {
  const u = users.find(
    (usr) => usr.roll_number.toUpperCase() === h.user_roll.toUpperCase()
  );
  const remaining = Math.max(
    0,
    Math.floor((new Date(h.expires_at).getTime() - Date.now()) / 60000)
  );
  return {
    ...h,
    full_name: u ? u.full_name : h.user_roll,
    branch: u ? u.branch : "",
    hostel: u ? u.hostel : "",
    remaining_minutes: remaining,
    needs_confirmation: remaining <= 15,
  };
}

function getRel(store, userA, userB) {
  if (!userA || !userB) return "NONE";
  const a = userA.toUpperCase();
  const b = userB.toUpperCase();
  if (a === b) return "SELF";
  for (const f of store.friendships) {
    const s = f.sender_roll.toUpperCase();
    const r = f.receiver_roll.toUpperCase();
    if ((s === a && r === b) || (s === b && r === a)) {
      if (f.status === "ACCEPTED") return "FRIENDS";
      return s === a ? "OUTGOING_PENDING" : "INCOMING_PENDING";
    }
  }
  return "NONE";
}

async function tryFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

export async function apiLogin(roll_number, password) {
  try {
    const data = await tryFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ roll_number, password }),
    });
    setCurrentUser(data.user);
    return data.user;
  } catch (err) {
    if (err.message === "Invalid roll number or password.") throw err;
    const store = readFallbackStore();
    const user = store.users.find(
      (u) => u.roll_number.toUpperCase() === roll_number.trim().toUpperCase()
    );
    if (!user || (user.password && user.password !== password)) {
      throw new Error("Invalid roll number or password.");
    }
    const { password: _, ...safeUser } = user;
    setCurrentUser(safeUser);
    return safeUser;
  }
}

export async function apiSignup(payload) {
  try {
    const data = await tryFetch("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setCurrentUser(data.user);
    return data.user;
  } catch (err) {
    if (err.message.includes("already exists")) throw err;
    const store = readFallbackStore();
    const roll = payload.roll_number.trim().toUpperCase();
    if (store.users.some((u) => u.roll_number.toUpperCase() === roll)) {
      throw new Error("An account with this university roll number already exists.");
    }
    const newUser = {
      roll_number: roll,
      full_name: payload.full_name.trim(),
      email: payload.email.trim().toLowerCase(),
      password: payload.password,
      branch: payload.branch || "Computer Science",
      hostel: payload.hostel || "Hostel 4",
      bio: "Studying on campus via StudySpot.",
    };
    store.users.push(newUser);
    writeFallbackStore(store);
    const { password: _, ...safeUser } = newUser;
    setCurrentUser(safeUser);
    return safeUser;
  }
}

export async function apiSearchUsers(query = "", viewerRoll = "") {
  try {
    const params = new URLSearchParams({ q: query, viewer_roll: viewerRoll });
    const data = await tryFetch(`/api/users/search?${params.toString()}`);
    return data.users;
  } catch {
    const store = readFallbackStore();
    const q = query.trim().toLowerCase();
    return store.users
      .filter(
        (u) =>
          !q ||
          u.roll_number.toLowerCase().includes(q) ||
          u.full_name.toLowerCase().includes(q) ||
          (u.branch || "").toLowerCase().includes(q) ||
          (u.hostel || "").toLowerCase().includes(q)
      )
      .map((u) => {
        const rel = getRel(store, viewerRoll, u.roll_number);
        const hand = store.active_hands.find(
          (h) => h.user_roll.toUpperCase() === u.roll_number.toUpperCase()
        );
        return {
          ...u,
          relationship: rel,
          active_hand:
            (rel === "FRIENDS" || rel === "SELF") && hand
              ? enrichHand(hand, store.users)
              : null,
        };
      });
  }
}

export async function apiGetUserProfile(rollNumber, viewerRoll = "") {
  try {
    const params = new URLSearchParams({ viewer_roll: viewerRoll });
    const data = await tryFetch(
      `/api/users/${encodeURIComponent(rollNumber)}?${params.toString()}`
    );
    return data.profile;
  } catch {
    const store = readFallbackStore();
    const u = store.users.find(
      (usr) => usr.roll_number.toUpperCase() === rollNumber.trim().toUpperCase()
    );
    if (!u) throw new Error("Student not found.");
    const rel = getRel(store, viewerRoll, u.roll_number);
    const canSee = rel === "FRIENDS" || rel === "SELF";
    const hand = store.active_hands.find(
      (h) => h.user_roll.toUpperCase() === u.roll_number.toUpperCase()
    );
    const friendsCount = store.friendships.filter(
      (f) =>
        f.status === "ACCEPTED" &&
        (f.sender_roll.toUpperCase() === u.roll_number.toUpperCase() ||
          f.receiver_roll.toUpperCase() === u.roll_number.toUpperCase())
    ).length;
    const rsvps = canSee
      ? store.rsvps.filter((r) =>
          r.participants.some(
            (p) => p.roll_number.toUpperCase() === u.roll_number.toUpperCase()
          )
        )
      : [];
    return {
      ...u,
      relationship: rel,
      friends_count: friendsCount,
      active_hand: canSee && hand ? enrichHand(hand, store.users) : null,
      rsvps,
    };
  }
}

export async function apiUpdateProfile(rollNumber, updates) {
  try {
    const data = await tryFetch(`/api/users/${encodeURIComponent(rollNumber)}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    });
    const current = getCurrentUser();
    if (current && current.roll_number.toUpperCase() === rollNumber.toUpperCase()) {
      setCurrentUser(data.user);
    }
    return data.user;
  } catch {
    const store = readFallbackStore();
    const idx = store.users.findIndex(
      (u) => u.roll_number.toUpperCase() === rollNumber.toUpperCase()
    );
    if (idx !== -1) {
      store.users[idx] = { ...store.users[idx], ...updates };
      writeFallbackStore(store);
      const { password: _, ...safe } = store.users[idx];
      const current = getCurrentUser();
      if (current && current.roll_number.toUpperCase() === rollNumber.toUpperCase()) {
        setCurrentUser(safe);
      }
      return safe;
    }
    throw new Error("User not found");
  }
}

export async function apiGetFriendsOverview(rollNumber) {
  try {
    return await tryFetch(`/api/friends/${encodeURIComponent(rollNumber)}`);
  } catch {
    const store = readFallbackStore();
    const roll = rollNumber.trim().toUpperCase();
    const friends = [];
    const incoming_requests = [];
    const outgoing_requests = [];

    for (const f of store.friendships) {
      const s = f.sender_roll.toUpperCase();
      const r = f.receiver_roll.toUpperCase();
      if (s !== roll && r !== roll) continue;
      const otherRoll = s === roll ? r : s;
      const otherUser = store.users.find(
        (u) => u.roll_number.toUpperCase() === otherRoll
      );
      if (!otherUser) continue;
      const hand = store.active_hands.find(
        (h) => h.user_roll.toUpperCase() === otherRoll
      );
      if (f.status === "ACCEPTED") {
        friends.push({
          ...otherUser,
          active_hand: hand ? enrichHand(hand, store.users) : null,
        });
      } else if (r === roll) {
        incoming_requests.push(otherUser);
      } else {
        outgoing_requests.push(otherUser);
      }
    }

    return {
      friends,
      studying_now: friends.filter((f) => f.active_hand !== null),
      incoming_requests,
      outgoing_requests,
    };
  }
}

export async function apiSendFriendRequest(sender_roll, receiver_roll) {
  try {
    return await tryFetch("/api/friends/request", {
      method: "POST",
      body: JSON.stringify({ sender_roll, receiver_roll }),
    });
  } catch {
    const store = readFallbackStore();
    const s = sender_roll.toUpperCase();
    const r = receiver_roll.toUpperCase();
    const existing = store.friendships.find(
      (f) =>
        (f.sender_roll.toUpperCase() === s && f.receiver_roll.toUpperCase() === r) ||
        (f.sender_roll.toUpperCase() === r && f.receiver_roll.toUpperCase() === s)
    );
    if (!existing) {
      store.friendships.push({ sender_roll: s, receiver_roll: r, status: "PENDING" });
      writeFallbackStore(store);
    }
    return { status: "OUTGOING_PENDING" };
  }
}

export async function apiRespondFriendRequest(sender_roll, receiver_roll, action) {
  try {
    return await tryFetch("/api/friends/respond", {
      method: "POST",
      body: JSON.stringify({ sender_roll, receiver_roll, action }),
    });
  } catch {
    const store = readFallbackStore();
    const s = sender_roll.toUpperCase();
    const r = receiver_roll.toUpperCase();
    if (action === "ACCEPT") {
      store.friendships.forEach((f) => {
        if (
          f.sender_roll.toUpperCase() === s &&
          f.receiver_roll.toUpperCase() === r
        ) {
          f.status = "ACCEPTED";
        }
      });
      writeFallbackStore(store);
      return { status: "FRIENDS" };
    } else {
      store.friendships = store.friendships.filter(
        (f) =>
          !(
            f.sender_roll.toUpperCase() === s &&
            f.receiver_roll.toUpperCase() === r
          )
      );
      writeFallbackStore(store);
      return { status: "NONE" };
    }
  }
}

export async function apiRemoveFriend(userA, userB) {
  try {
    return await tryFetch(
      `/api/friends/${encodeURIComponent(userA)}/${encodeURIComponent(userB)}`,
      { method: "DELETE" }
    );
  } catch {
    const store = readFallbackStore();
    const a = userA.toUpperCase();
    const b = userB.toUpperCase();
    store.friendships = store.friendships.filter(
      (f) =>
        !(
          (f.sender_roll.toUpperCase() === a &&
            f.receiver_roll.toUpperCase() === b) ||
          (f.sender_roll.toUpperCase() === b &&
            f.receiver_roll.toUpperCase() === a)
        )
    );
    writeFallbackStore(store);
    return { status: "NONE" };
  }
}

export async function apiGetActiveHands() {
  try {
    const data = await tryFetch("/api/hands");
    return data.active_hands;
  } catch {
    const store = readFallbackStore();
    return store.active_hands.map((h) => enrichHand(h, store.users));
  }
}

export async function apiRaiseHand({
  user_roll,
  zone_name,
  room_id,
  room_name,
  note = "Studying",
  duration_minutes = 120,
}) {
  try {
    const data = await tryFetch("/api/hands/raise", {
      method: "POST",
      body: JSON.stringify({
        user_roll,
        zone_name,
        room_id,
        room_name,
        note,
        duration_minutes,
      }),
    });
    return data.active_hand;
  } catch {
    const store = readFallbackStore();
    const roll = user_roll.toUpperCase();
    const now = Date.now();
    const hand = {
      user_roll: roll,
      zone_name,
      room_id,
      room_name,
      note,
      raised_at: new Date(now).toISOString(),
      expires_at: new Date(now + duration_minutes * 60000).toISOString(),
    };
    store.active_hands = store.active_hands.filter(
      (h) => h.user_roll.toUpperCase() !== roll
    );
    store.active_hands.push(hand);
    writeFallbackStore(store);
    return enrichHand(hand, store.users);
  }
}

export async function apiConfirmHand(user_roll, extend_minutes = 60) {
  try {
    const data = await tryFetch("/api/hands/confirm", {
      method: "POST",
      body: JSON.stringify({ user_roll, extend_minutes }),
    });
    return data.active_hand;
  } catch {
    const store = readFallbackStore();
    const roll = user_roll.toUpperCase();
    const hand = store.active_hands.find((h) => h.user_roll.toUpperCase() === roll);
    if (!hand) return null;
    hand.expires_at = new Date(Date.now() + extend_minutes * 60000).toISOString();
    writeFallbackStore(store);
    return enrichHand(hand, store.users);
  }
}

export async function apiLowerHand(user_roll) {
  try {
    await tryFetch(`/api/hands/${encodeURIComponent(user_roll)}`, {
      method: "DELETE",
    });
    return null;
  } catch {
    const store = readFallbackStore();
    const roll = user_roll.toUpperCase();
    store.active_hands = store.active_hands.filter(
      (h) => h.user_roll.toUpperCase() !== roll
    );
    writeFallbackStore(store);
    return null;
  }
}

export async function apiGetRSVPs(zoneName = null) {
  try {
    const q = zoneName ? `?zone_name=${encodeURIComponent(zoneName)}` : "";
    const data = await tryFetch(`/api/rsvps${q}`);
    return data.rsvps;
  } catch {
    const store = readFallbackStore();
    return zoneName
      ? store.rsvps.filter((r) => r.zone_name === zoneName)
      : store.rsvps;
  }
}

export async function apiCreateRSVP(payload) {
  try {
    const data = await tryFetch("/api/rsvps", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return data.rsvp;
  } catch {
    const store = readFallbackStore();
    const user = store.users.find(
      (u) => u.roll_number.toUpperCase() === payload.creator_roll.toUpperCase()
    );
    const creatorName = user ? user.full_name : payload.creator_roll;
    const newRsvp = {
      rsvp_id: `rsvp-${Date.now()}`,
      creator_roll: payload.creator_roll.toUpperCase(),
      creator_name: creatorName,
      zone_name: payload.zone_name,
      room_id: payload.room_id,
      room_name: payload.room_name,
      start_time: payload.start_time,
      end_time: payload.end_time,
      topic: payload.topic,
      participants: [
        { roll_number: payload.creator_roll.toUpperCase(), full_name: creatorName },
      ],
    };
    store.rsvps.unshift(newRsvp);
    writeFallbackStore(store);
    return newRsvp;
  }
}

export async function apiToggleRSVP(rsvp_id, user_roll) {
  try {
    const data = await tryFetch(`/api/rsvps/${encodeURIComponent(rsvp_id)}/toggle`, {
      method: "POST",
      body: JSON.stringify({ user_roll }),
    });
    return data.rsvp;
  } catch {
    const store = readFallbackStore();
    const roll = user_roll.toUpperCase();
    const user = store.users.find((u) => u.roll_number.toUpperCase() === roll);
    const fullName = user ? user.full_name : roll;
    const rsvp = store.rsvps.find((r) => r.rsvp_id === rsvp_id);
    if (!rsvp) return null;
    const exists = rsvp.participants.some(
      (p) => p.roll_number.toUpperCase() === roll
    );
    if (exists) {
      rsvp.participants = rsvp.participants.filter(
        (p) => p.roll_number.toUpperCase() !== roll
      );
    } else {
      rsvp.participants.push({ roll_number: roll, full_name: fullName });
    }
    if (rsvp.participants.length === 0) {
      store.rsvps = store.rsvps.filter((r) => r.rsvp_id !== rsvp_id);
    }
    writeFallbackStore(store);
    return rsvp;
  }
}

export async function apiFetchOccupancy() {
  try {
    return await tryFetch("/api/occupancy");
  } catch {
    return null;
  }
}

// ===== Study Circles: MongoDB-only room bookings (no localStorage fallback) =====
const STUDY_CIRCLES_BASE = import.meta.env.VITE_STUDY_CIRCLES_API_URL || "http://localhost:8002";

async function circlesFetch(path, options = {}) {
  let response;
  try {
    response = await fetch(`${STUDY_CIRCLES_BASE}/api/study-circles${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Study Circles booking server is unavailable. Start port 8002 and check MongoDB.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : `Booking request failed (${response.status}).`);
  }
  return data;
}

export function apiStudyCircleSlots(date) {
  return circlesFetch(`/slots?date=${encodeURIComponent(date)}`);
}
export function apiStudyCircleBookings(userRoll) {
  return circlesFetch(`/bookings?user_roll=${encodeURIComponent(userRoll)}`);
}
export function apiCreateStudyCircle({ organizer_roll, date, slot, topic, invitees }) {
  return circlesFetch("/bookings", {
    method: "POST",
    body: JSON.stringify({ organizer_roll, date, slot, topic, invitees }),
  });
}
export function apiRespondStudyCircle(bookingId, userRoll, decision) {
  return circlesFetch(`/bookings/${encodeURIComponent(bookingId)}/respond`, {
    method: "POST",
    body: JSON.stringify({ user_roll: userRoll, decision }),
  });
}
export function apiCancelStudyCircle(bookingId, userRoll) {
  return circlesFetch(`/bookings/${encodeURIComponent(bookingId)}?user_roll=${encodeURIComponent(userRoll)}`, {
    method: "DELETE",
  });
}

// Study Circles in-app reminder (MongoDB-only; never falls back to localStorage).
export function apiSendStudyCircleReminder(bookingId, senderRoll, message) {
  return circlesFetch(`/bookings/${encodeURIComponent(bookingId)}/remind`, {
    method: "POST",
    body: JSON.stringify({ sender_roll: senderRoll, message }),
  });
}
