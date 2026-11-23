
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const USER_STORAGE_KEY = "studyspot_current_user";
const TOKEN_STORAGE_KEY = "studyspot_access_token";

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

export function getAuthToken() {
  try { 
    const raw = localStorage.getItem(TOKEN_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {

    return null;
    
  }
}

export function setCurrentUser(user, token = null) {
  if (!user) {
    localStorage.removeItem(USER_STORAGE_KEY);
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } else {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(token));
  }
}


export function logoutUser() {
  localStorage.removeItem(USER_STORAGE_KEY);
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}


async function tryFetch(path, options = {}) {
  const token = getAuthToken();
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
    setCurrentUser(data.user,data.access_token);
    return data.user;
  } catch (err) {
    return err;
  }
}

export async function apiSignup(payload) {
  try {
    const data = await tryFetch("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setCurrentUser(data.user,data.access_token);
    return data.user;
  } catch (err) {
    return err;
    
  }
}

export async function apiSearchUsers(query = "", viewerRoll = "") {
  try {
    const params = new URLSearchParams({ q: query, viewer_roll: viewerRoll });
    const data = await tryFetch(`/api/users/search?${params.toString()}`);
    return data.users;
  } catch (err) {
    return err;
  }
}

export async function apiGetUserProfile(rollNumber, viewerRoll = "") {
  try {
    const params = new URLSearchParams({ viewer_roll: viewerRoll });
    const data = await tryFetch(
      `/api/users/${encodeURIComponent(rollNumber)}?${params.toString()}`
    );
    return data.profile;
  } catch (err) {
    return err;
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
  } catch (err) {
    return err;
  }
}

export async function apiGetFriendsOverview(rollNumber) {
  try {
    return await tryFetch(`/api/friends/${encodeURIComponent(rollNumber)}`);
  } catch (err) {
      return err;
  }
}

export async function apiSendFriendRequest(sender_roll, receiver_roll) {
  try {
    return await tryFetch("/api/friends/request", {
      method: "POST",
      body: JSON.stringify({ sender_roll, receiver_roll }),
    });
  } catch (err) {
    return err;
  }
}

export async function apiRespondFriendRequest(sender_roll, receiver_roll, action) {
  try {
    return await tryFetch("/api/friends/respond", {
      method: "POST",
      body: JSON.stringify({ sender_roll, receiver_roll, action }),
    });
  } catch (err) {
    return err;
  }
}

export async function apiRemoveFriend(userA, userB) {
  try {
    return await tryFetch(
      `/api/friends/${encodeURIComponent(userA)}/${encodeURIComponent(userB)}`,
      { method: "DELETE" }
    );
  } catch (err) {
    return err;
  }
}

export async function apiGetActiveHands() {
  try {
    const data = await tryFetch("/api/hands");
    return data.active_hands;
  } catch (err) {
    return err;
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
  } catch (err) {
    return err;
  }
}

export async function apiConfirmHand(user_roll, extend_minutes = 60) {
  try {
    const data = await tryFetch("/api/hands/confirm", {
      method: "POST",
      body: JSON.stringify({ user_roll, extend_minutes }),
    });
    return data.active_hand;
  } catch (err) {
    return err;
  }
}

export async function apiLowerHand(user_roll) {
  try {
    await tryFetch(`/api/hands/${encodeURIComponent(user_roll)}`, {
      method: "DELETE",
    });
    return null;
  } catch (err) {
    return err;
  }
}

export async function apiGetRSVPs(zoneName = null) {
  try {
    const q = zoneName ? `?zone_name=${encodeURIComponent(zoneName)}` : "";
    const data = await tryFetch(`/api/rsvps${q}`);
    return data.rsvps;
  } catch (err) {
    return err;
  }
}

export async function apiCreateRSVP(payload) {
  try {
    const data = await tryFetch("/api/rsvps", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return data.rsvp;
  } catch (err) {
    return err;
  }
}

export async function apiToggleRSVP(rsvp_id, user_roll) {
  try {
    const data = await tryFetch(`/api/rsvps/${encodeURIComponent(rsvp_id)}/toggle`, {
      method: "POST",
      body: JSON.stringify({ user_roll }),
    });
    return data.rsvp;
  } catch (err) {
    return err;
  }
}

export async function apiFetchOccupancy() {
  try {
    return await tryFetch("/api/occupancy");
  } catch {
    return null;
  }
}
