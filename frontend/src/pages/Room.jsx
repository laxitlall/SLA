import { useEffect, useState } from "react";
import { Link } from "react-router";
import Navbar from "../components/Navbar";
import ZoneCard from "../components/ZoneCard";
import {
  apiConfirmHand,
  apiCreateRSVP,
  apiFetchOccupancy,
  apiGetActiveHands,
  apiGetFriendsOverview,
  apiGetRSVPs,
  apiLowerHand,
  apiRaiseHand,
  apiToggleRSVP,
  getCurrentUser,
} from "../utils/api";
import { getCampusOccupancySummary } from "../utils/getOccupancy";

export default function Room() {
  const [user, setUser] = useState(() => getCurrentUser());
  const [occupancyData, setOccupancyData] = useState(null);
  const { summary: zonesSummary } = getCampusOccupancySummary(occupancyData);

  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");

  const [activeHand, setActiveHand] = useState(null);
  const [friendsOverview, setFriendsOverview] = useState({
    friends: [],
    studying_now: [],
    incoming_requests: [],
  });
  const [rsvps, setRsvps] = useState([]);
  const [showRsvpSection, setShowRsvpSection] = useState(false);

  const [rsvpModalRoom, setRsvpModalRoom] = useState(null);
  const [rsvpTopic, setRsvpTopic] = useState("Endsem Group Study");
  const [rsvpStartTime, setRsvpStartTime] = useState("Today, 8:00 PM");
  const [rsvpEndTime, setRsvpEndTime] = useState("Today, 10:30 PM");

  const loadSocialData = async (currentUser) => {
    const liveOcc = await apiFetchOccupancy();
    if (liveOcc && liveOcc.zones) {
      setOccupancyData(liveOcc);
    }
    const allRsvps = await apiGetRSVPs();
    setRsvps(allRsvps);

    if (!currentUser) {
      setActiveHand(null);
      return;
    }

    const [hands, fOverview] = await Promise.all([
      apiGetActiveHands(),
      apiGetFriendsOverview(currentUser.roll_number),
    ]);

    const myHand = hands.find(
      (h) => h.user_roll.toUpperCase() === currentUser.roll_number.toUpperCase()
    );
    setActiveHand(myHand || null);
    setFriendsOverview(fOverview);
  };

  useEffect(() => {
    const currentUser = getCurrentUser();
    setUser(currentUser);
    loadSocialData(currentUser);
  }, []);

  const handleRaiseHand = async ({
    zone_name,
    room_id,
    room_name,
    duration_minutes = 120,
  }) => {
    if (!user) return;
    const hand = await apiRaiseHand({
      user_roll: user.roll_number,
      zone_name,
      room_id,
      room_name,
      note: "Studying here now",
      duration_minutes,
    });
    setActiveHand(hand);
  };

  const handleConfirmHand = async () => {
    if (!user) return;
    const updated = await apiConfirmHand(user.roll_number, 60);
    setActiveHand(updated);
  };

  const handleLowerHand = async () => {
    if (!user) return;
    await apiLowerHand(user.roll_number);
    setActiveHand(null);
  };

  const handleSimulateExpiryPrompt = async () => {
    if (!user) return;
    const targetZone = activeHand ? activeHand.zone_name : "Central Library";
    const targetRoomId = activeHand
      ? activeHand.room_id
      : "central-lib-room-1";
    const targetRoomName = activeHand
      ? activeHand.room_name
      : "Reading Hall 1";
    // Set remaining duration to 10 minutes so the auto-unraise check-in prompt appears
    const hand = await apiRaiseHand({
      user_roll: user.roll_number,
      zone_name: targetZone,
      room_id: targetRoomId,
      room_name: targetRoomName,
      note: "Studying (demo expiry warning)",
      duration_minutes: 10,
    });
    setActiveHand(hand);
  };

  const handleCreateRsvp = async (e) => {
    e.preventDefault();
    if (!user || !rsvpModalRoom) return;
    await apiCreateRSVP({
      creator_roll: user.roll_number,
      zone_name: rsvpModalRoom.zone_name,
      room_id: rsvpModalRoom.room_id,
      room_name: rsvpModalRoom.room_name,
      start_time: rsvpStartTime,
      end_time: rsvpEndTime,
      topic: rsvpTopic,
    });
    setRsvpModalRoom(null);
    setShowRsvpSection(true);
    const updated = await apiGetRSVPs();
    setRsvps(updated);
  };

  const handleToggleRsvp = async (rsvp_id) => {
    if (!user) return;
    await apiToggleRSVP(rsvp_id, user.roll_number);
    const updated = await apiGetRSVPs();
    setRsvps(updated);
  };

  const filteredZones = zonesSummary.filter((zone) => {
    const matchesSearch = zone.name
      .toLowerCase()
      .includes(searchQuery.trim().toLowerCase());
    const matchesFilter =
      activeFilter === "all" || zone.zone_type === activeFilter;
    return matchesSearch && matchesFilter;
  });

  const filteredAvailableSeats = filteredZones.reduce(
    (sum, zone) => sum + zone.availableSeats,
    0
  );

  const myNextRsvp = user
    ? rsvps.find((r) =>
        r.participants?.some(
          (p) => p.roll_number.toUpperCase() === user.roll_number.toUpperCase()
        )
      )
    : null;

  return (
    <div className="bg-roomgreen min-h-screen">
      <Navbar
        user={user}
        showSearch={true}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        activeHand={activeHand}
        pendingRequestsCount={friendsOverview.incoming_requests?.length || 0}
      />

      <main className="max-w-[1380px] px-5 py-8 mx-auto lg:px-10 lg:py-10">
        <section className="flex flex-col gap-5 justify-between items-end md:flex-row">
          <div className="w-full md:w-fit">
            <div className="mb-2 text-sm font-medium text-lightgreenfont">
              {user ? `Hello, ${user.full_name}` : "LIVE CAMPUS OVERVIEW"}
            </div>
            <h1 className="text-3xl font-bold text-greenfont">
              Find your place to focus
            </h1>
            <div className="mt-3 text-gray-500">
              Live CCTV seat availability across IIT Bombay.
            </div>
          </div>
          <div className="flex w-full items-center h-fit gap-2 px-4 py-3 rounded-xl border border-[#e3e8e5] bg-white text-sm font-medium md:w-fit">
            <span className="w-2 h-2 rounded-full bg-green-600 inline-block" />
            <span className="text-[#43554e]">Live Now</span>
            <span className="text-[#929a96]">Updated just now</span>
          </div>
        </section>

        {/* Mobile Search Bar */}
        <div className="mt-5 flex bg-white border border-[#e3e8e5] rounded-xl px-3 py-2.5 md:hidden">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search for libraries and study rooms"
            className="w-full bg-transparent text-greenfont placeholder:text-grayfont font-medium text-sm outline-none"
          />
        </div>

        {/* Logged-in Social & Raise-Hand Summary Banner (Merged from PersonalRoom.jsx) */}
        {user && (
          <section className="mt-8 flex flex-col gap-5 justify-between md:flex-row">
            <div className="flex flex-col sm:flex-row flex-2 justify-between gap-4 rounded-xl bg-greenfont p-5 text-white">
              {activeHand ? (
                <>
                  <div className="flex flex-col">
                    <div className="font-bold text-[#9bcabd] text-sm">
                      ✋ YOUR HAND IS RAISED ({activeHand.remaining_minutes}m
                      left before auto-unraise)
                    </div>
                    <div className="text-xl font-bold mt-1">
                      {activeHand.zone_name} • {activeHand.room_name}
                    </div>
                    <div className="text-xs text-[#cde3dc] mt-1">
                      Friends can see you are studying here.
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 my-auto">
                    <button
                      type="button"
                      onClick={handleConfirmHand}
                      className="bg-white text-greenfont py-2.5 px-3 rounded-xl font-bold text-xs hover:opacity-95"
                    >
                      Still here (+1h)
                    </button>
                    <button
                      type="button"
                      onClick={handleSimulateExpiryPrompt}
                      className="bg-[#285c4d] text-white py-2.5 px-3 rounded-xl font-medium text-xs hover:bg-[#316e5c]"
                      title="Simulate the auto-unraise check-in prompt when timer is about to expire"
                    >
                      Test Expiry Prompt
                    </button>
                    <button
                      type="button"
                      onClick={handleLowerHand}
                      className="bg-red-500/90 text-white py-2.5 px-3 rounded-xl font-bold text-xs hover:bg-red-600"
                    >
                      Unraise
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex flex-col">
                    <div className="font-bold text-[#9bcabd] text-sm">
                      Your next study plan
                    </div>
                    <div className="text-xl font-bold mt-1">
                      {myNextRsvp
                        ? `${myNextRsvp.topic} — ${myNextRsvp.zone_name} (${myNextRsvp.start_time})`
                        : "Quiet Study Room (No active hand raised)"}
                    </div>
                    <div className="text-xs text-[#cde3dc] mt-1">
                      Click any study room below to ✋ Raise your hand or 📅
                      Schedule an RSVP lobby.
                    </div>
                  </div>
                  <div className="flex items-center gap-2 my-auto shrink-0">
                    <button
                      type="button"
                      onClick={() => setShowRsvpSection((prev) => !prev)}
                      className="bg-white text-greenfont py-3 px-4 rounded-xl font-bold text-sm hover:opacity-95"
                    >
                      {showRsvpSection ? "Hide RSVPs" : "View RSVPs"} (
                      {rsvps.length})
                    </button>
                  </div>
                </>
              )}
            </div>

            <Link
              to="/friends"
              className="flex flex-1 items-center justify-between gap-5 rounded-xl bg-white border border-[#e3e8e5] p-5 text-greenfont hover:shadow-md transition"
            >
              <div className="flex flex-col">
                <div className="text-xs font-medium text-gray-500">
                  FRIENDS ON CAMPUS
                </div>
                <div className="mt-2 text-xl font-bold text-[#2c473e]">
                  {friendsOverview.studying_now?.length || 0} STUDYING NOW
                </div>
                <div className="mt-1 text-sm text-lightgreenfont font-medium">
                  See where they are & find friends →
                </div>
              </div>
            </Link>
          </section>
        )}

        {/* Pokémon GO Style RSVP Lobbies Section */}
        {user && showRsvpSection && (
          <section className="mt-6 bg-white border border-[#e3e8e5] rounded-xl p-5">
            <div className="flex flex-wrap justify-between items-center gap-3 mb-4">
              <div>
                <h2 className="text-lg font-bold text-greenfont">
                  📅 Upcoming Study RSVP Lobbies
                </h2>
                <p className="text-xs text-gray-500">
                  See when college mates are planning to study and join their
                  time slot.
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  setRsvpModalRoom({
                    zone_name: "Central Library",
                    room_id: "central-lib-room-1",
                    room_name: "Reading Hall 1",
                  })
                }
                className="px-3.5 py-2 rounded-xl bg-greenfont text-white text-xs font-bold"
              >
                + Schedule New RSVP
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {rsvps.map((rsvp) => {
                const isJoined = rsvp.participants?.some(
                  (p) =>
                    p.roll_number.toUpperCase() ===
                    user.roll_number.toUpperCase()
                );
                return (
                  <div
                    key={rsvp.rsvp_id}
                    className="rounded-xl bg-roomgreen p-4 flex flex-col justify-between gap-3 border border-[#dcebe5]"
                  >
                    <div>
                      <div className="flex justify-between items-start gap-2">
                        <span className="font-bold text-greenfont text-base">
                          {rsvp.topic}
                        </span>
                        <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-white text-lightgreenfont">
                          {rsvp.start_time} – {rsvp.end_time}
                        </span>
                      </div>
                      <div className="text-xs text-gray-600 mt-1 font-medium">
                        📍 {rsvp.zone_name} • {rsvp.room_name}
                      </div>
                      <div className="flex flex-wrap gap-1.5 mt-2.5">
                        {rsvp.participants?.map((p) => (
                          <Link
                            key={p.roll_number}
                            to={`/profile/${p.roll_number}`}
                            className="text-[11px] px-2 py-0.5 rounded-full bg-white text-greenfont border border-[#cdd8d3] font-medium hover:underline"
                          >
                            {p.full_name}
                          </Link>
                        ))}
                      </div>
                    </div>

                    <div className="flex justify-between items-center pt-2 border-t border-[#dcebe5]">
                      <span className="text-xs text-gray-500">
                        {rsvp.participants?.length || 0} interested
                      </span>
                      <button
                        type="button"
                        onClick={() => handleToggleRsvp(rsvp.rsvp_id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                          isJoined
                            ? "bg-white text-red-700 border border-red-200 hover:bg-red-50"
                            : "bg-greenfont text-white hover:opacity-95"
                        }`}
                      >
                        {isJoined ? "Leave RSVP" : "Join RSVP"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Spaces Near You & Filters */}
        <section className="mt-10">
          <div className="flex flex-col justify-between md:flex-row">
            <div className="pb-4 md:pb-0">
              <div className="text-xl text-greenfont font-bold">
                Spaces near you
              </div>
              <div className="mt-1 text-sm text-gray-500">
                {filteredAvailableSeats} seats available across{" "}
                {filteredZones.length}{" "}
                {filteredZones.length === 1 ? "space" : "spaces"}
              </div>
            </div>
            <div className="flex w-fit rounded-xl bg-[#e9eeeb] p-1 items-center">
              <button
                type="button"
                onClick={() => setActiveFilter("all")}
                className={`rounded-lg px-4 py-2 text-xs font-bold transition ${
                  activeFilter === "all"
                    ? "bg-white text-[#285446] shadow-sm"
                    : "text-[#75807b]"
                }`}
              >
                All spaces
              </button>
              <button
                type="button"
                onClick={() => setActiveFilter("library")}
                className={`rounded-lg px-4 py-2 text-xs font-bold transition ${
                  activeFilter === "library"
                    ? "bg-white text-[#285446] shadow-sm"
                    : "text-[#75807b]"
                }`}
              >
                Library
              </button>
              <button
                type="button"
                onClick={() => setActiveFilter("hostel")}
                className={`rounded-lg px-4 py-2 text-xs font-bold transition ${
                  activeFilter === "hostel"
                    ? "bg-white text-[#285446] shadow-sm"
                    : "text-[#75807b]"
                }`}
              >
                Study room
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-2 mt-5">
            {filteredZones.map((zone) => {
              const friendsInZone = (friendsOverview.studying_now || []).filter(
                (f) => f.active_hand?.zone_name === zone.name
              );
              return (
                <ZoneCard
                  key={zone.name}
                  zone={zone}
                  user={user}
                  activeHand={activeHand}
                  friendsInZone={friendsInZone}
                  onRaiseHand={handleRaiseHand}
                  onLowerHand={handleLowerHand}
                  onOpenRSVPModal={(roomInfo) => setRsvpModalRoom(roomInfo)}
                />
              );
            })}
          </div>
        </section>
      </main>

      {/* RSVP Creation Modal */}
      {rsvpModalRoom && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-xl font-bold text-greenfont">
              Schedule Study RSVP
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              📍 {rsvpModalRoom.zone_name} • {rsvpModalRoom.room_name}
            </p>
            <form onSubmit={handleCreateRsvp} className="mt-4 flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold text-gray-700">
                  Study Topic / Goal
                </label>
                <input
                  type="text"
                  required
                  value={rsvpTopic}
                  onChange={(e) => setRsvpTopic(e.target.value)}
                  placeholder="e.g. DSA Practice / Endsem Revision"
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-greenfont"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-bold text-gray-700">
                    Start Time
                  </label>
                  <input
                    type="text"
                    required
                    value={rsvpStartTime}
                    onChange={(e) => setRsvpStartTime(e.target.value)}
                    placeholder="Today, 8:00 PM"
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-greenfont"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-bold text-gray-700">
                    End Time
                  </label>
                  <input
                    type="text"
                    required
                    value={rsvpEndTime}
                    onChange={(e) => setRsvpEndTime(e.target.value)}
                    placeholder="Today, 10:30 PM"
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-greenfont"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-3">
                <button
                  type="button"
                  onClick={() => setRsvpModalRoom(null)}
                  className="px-4 py-2 rounded-lg text-xs font-bold text-gray-600 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-xs font-bold bg-greenfont text-white"
                >
                  Create RSVP Lobby
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
