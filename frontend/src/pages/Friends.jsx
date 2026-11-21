import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import Navbar, { getInitials } from "../components/Navbar";
import {
  apiConfirmHand,
  apiGetActiveHands,
  apiGetFriendsOverview,
  apiLowerHand,
  apiRaiseHand,
  apiRespondFriendRequest,
  apiSearchUsers,
  apiSendFriendRequest,
  getCurrentUser,
} from "../utils/api";

export default function Friends() {
  const navigate = useNavigate();
  const [user] = useState(() => getCurrentUser());
  const [activeTab, setActiveTab] = useState("studying"); // "studying" | "requests" | "all"
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [activeHand, setActiveHand] = useState(null);
  const [overview, setOverview] = useState({
    friends: [],
    studying_now: [],
    incoming_requests: [],
    outgoing_requests: [],
  });

  const refreshAll = async (q = searchQuery) => {
    if (!user) return;
    const [fData, hands, usersFound] = await Promise.all([
      apiGetFriendsOverview(user.roll_number),
      apiGetActiveHands(),
      apiSearchUsers(q, user.roll_number),
    ]);
    setOverview(fData);
    const myHand = hands.find(
      (h) => h.user_roll.toUpperCase() === user.roll_number.toUpperCase()
    );
    setActiveHand(myHand || null);
    setSearchResults(
      usersFound.filter(
        (u) => u.roll_number.toUpperCase() !== user.roll_number.toUpperCase()
      )
    );
  };

  useEffect(() => {
    if (!user) {
      navigate("/login");
      return;
    }
    refreshAll("");
  }, [user]);

  const handleSearch = async (val) => {
    setSearchQuery(val);
    if (!user) return;
    const found = await apiSearchUsers(val, user.roll_number);
    setSearchResults(
      found.filter(
        (u) => u.roll_number.toUpperCase() !== user.roll_number.toUpperCase()
      )
    );
  };

  const handleSendRequest = async (receiverRoll) => {
    if (!user) return;
    await apiSendFriendRequest(user.roll_number, receiverRoll);
    await refreshAll();
  };

  const handleRespondRequest = async (senderRoll, action) => {
    if (!user) return;
    await apiRespondFriendRequest(senderRoll, user.roll_number, action);
    await refreshAll();
  };

  const handleJoinFriendStudy = async (hand) => {
    if (!user || !hand) return;
    await apiRaiseHand({
      user_roll: user.roll_number,
      zone_name: hand.zone_name,
      room_id: hand.room_id,
      room_name: hand.room_name,
      note: `Studying with ${hand.full_name}`,
      duration_minutes: 120,
    });
    await refreshAll();
  };

  if (!user) return null;

  return (
    <div className="bg-roomgreen min-h-screen">
      <Navbar
        user={user}
        activeHand={activeHand}
        onConfirmHand={async () => {
          const updated = await apiConfirmHand(user.roll_number, 60);
          setActiveHand(updated);
        }}
        onLowerHand={async () => {
          await apiLowerHand(user.roll_number);
          setActiveHand(null);
        }}
        pendingRequestsCount={overview.incoming_requests.length}
      />

      <main className="max-w-[1380px] px-5 py-8 mx-auto lg:px-10 lg:py-10">
        {/* Header */}
        <section className="flex flex-col md:flex-row justify-between md:items-end gap-4">
          <div>
            <div className="mb-1 text-sm font-medium text-lightgreenfont">
              CAMPUS COMMUNITY
            </div>
            <h1 className="text-3xl font-bold text-greenfont">
              Friends & Study Mates
            </h1>
            <p className="mt-2 text-gray-500 text-sm">
              Search IITB students by roll number or name, view profiles, and
              see who has their hand raised.
            </p>
          </div>
          <Link
            to="/room"
            className="w-fit px-4 py-2.5 rounded-xl bg-white border border-[#e3e8e5] text-greenfont text-xs font-bold hover:shadow-sm"
          >
            ← Back to Live Spaces
          </Link>
        </section>

        {/* Search College Mates by Roll Number or Name */}
        <section className="mt-8 bg-white border border-[#e3e8e5] rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-greenfont">
            Find College Mates
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Search by old/new IITB Roll Number (e.g. 23B1002, 200050012,
            19D070021) or Name (e.g. Aarav, Sneha, Kabir)
          </p>

          <div className="mt-4 flex items-center bg-roomgreen rounded-xl px-4 py-3 border border-[#dcebe5]">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Type a roll number or student name..."
              className="w-full bg-transparent text-greenfont placeholder:text-grayfont font-medium text-sm outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => handleSearch("")}
                className="text-xs text-gray-500 font-bold hover:text-greenfont"
              >
                Clear
              </button>
            )}
          </div>

          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {searchResults.map((student) => (
              <div
                key={student.roll_number}
                className="rounded-xl border border-[#e3e8e5] bg-[#fafcfb] p-4 flex flex-col justify-between gap-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#dcebe5] text-[#36594f] font-bold flex items-center justify-center text-sm shrink-0">
                      {getInitials(student.full_name)}
                    </div>
                    <div>
                      <Link
                        to={`/profile/${student.roll_number}`}
                        className="font-bold text-greenfont text-sm hover:underline"
                      >
                        {student.full_name}
                      </Link>
                      <div className="text-xs text-gray-500">
                        {student.roll_number} • {student.branch}
                      </div>
                      <div className="text-xs text-gray-400">
                        {student.hostel}
                      </div>
                    </div>
                  </div>
                </div>

                {student.active_hand && (
                  <div className="text-xs bg-green-50 text-green-800 border border-green-200 rounded-lg px-2.5 py-1.5 font-medium">
                    ✋ At {student.active_hand.zone_name} (
                    {student.active_hand.room_name})
                  </div>
                )}

                <div className="flex items-center justify-between gap-2 pt-2 border-t border-[#eef2ef]">
                  <Link
                    to={`/profile/${student.roll_number}`}
                    className="text-xs font-bold text-lightgreenfont hover:underline"
                  >
                    View Profile →
                  </Link>

                  {student.relationship === "FRIENDS" && (
                    <span className="px-2.5 py-1 rounded-lg bg-[#dcebe5] text-greenfont text-xs font-bold">
                      Friends ✓
                    </span>
                  )}
                  {student.relationship === "OUTGOING_PENDING" && (
                    <span className="px-2.5 py-1 rounded-lg bg-gray-100 text-gray-600 text-xs font-bold">
                      Request Sent
                    </span>
                  )}
                  {student.relationship === "INCOMING_PENDING" && (
                    <button
                      type="button"
                      onClick={() =>
                        handleRespondRequest(student.roll_number, "ACCEPT")
                      }
                      className="px-3 py-1 rounded-lg bg-greenfont text-white text-xs font-bold"
                    >
                      Accept Request
                    </button>
                  )}
                  {student.relationship === "NONE" && (
                    <button
                      type="button"
                      onClick={() => handleSendRequest(student.roll_number)}
                      className="px-3 py-1 rounded-lg bg-greenfont text-white text-xs font-bold hover:opacity-95"
                    >
                      + Add Friend
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Tabs: Studying Now | Friend Requests | All Friends */}
        <section className="mt-8">
          <div className="flex flex-wrap gap-2 bg-[#e9eeeb] p-1 rounded-xl w-fit">
            <button
              type="button"
              onClick={() => setActiveTab("studying")}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
                activeTab === "studying"
                  ? "bg-white text-[#285446] shadow-sm"
                  : "text-[#75807b]"
              }`}
            >
              ✋ Studying Now ({overview.studying_now.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("requests")}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
                activeTab === "requests"
                  ? "bg-white text-[#285446] shadow-sm"
                  : "text-[#75807b]"
              }`}
            >
              Friend Requests ({overview.incoming_requests.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("all")}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
                activeTab === "all"
                  ? "bg-white text-[#285446] shadow-sm"
                  : "text-[#75807b]"
              }`}
            >
              All Friends ({overview.friends.length})
            </button>
          </div>

          {/* TAB 1: STUDYING NOW */}
          {activeTab === "studying" && (
            <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              {overview.studying_now.length === 0 ? (
                <div className="col-span-2 bg-white rounded-xl p-6 text-sm text-gray-500 border border-[#e3e8e5]">
                  None of your friends currently have their hand raised.
                </div>
              ) : (
                overview.studying_now.map((friend) => (
                  <div
                    key={friend.roll_number}
                    className="bg-white rounded-xl p-5 border border-[#e3e8e5] shadow-sm flex flex-col justify-between gap-4"
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div className="flex items-center gap-3">
                        <div className="w-11 h-11 rounded-xl bg-[#dcebe5] text-[#36594f] font-bold flex items-center justify-center">
                          {getInitials(friend.full_name)}
                        </div>
                        <div>
                          <Link
                            to={`/profile/${friend.roll_number}`}
                            className="text-lg font-bold text-greenfont hover:underline"
                          >
                            {friend.full_name}
                          </Link>
                          <div className="text-xs text-gray-500">
                            {friend.roll_number} • {friend.branch}
                          </div>
                        </div>
                      </div>
                      <span className="px-2.5 py-1 rounded-full bg-green-100 text-green-800 text-xs font-bold">
                        ✋ Hand Raised ({friend.active_hand.remaining_minutes}m
                        left)
                      </span>
                    </div>

                    <div className="rounded-xl bg-roomgreen p-3.5 text-sm">
                      <div className="font-bold text-greenfont">
                        📍 {friend.active_hand.zone_name} •{" "}
                        {friend.active_hand.room_name}
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        Note: &ldquo;{friend.active_hand.note}&rdquo;
                      </div>
                    </div>

                    <div className="flex justify-between items-center">
                      <Link
                        to={`/profile/${friend.roll_number}`}
                        className="text-xs font-bold text-lightgreenfont hover:underline"
                      >
                        View Profile
                      </Link>
                      <button
                        type="button"
                        onClick={() => handleJoinFriendStudy(friend.active_hand)}
                        className="px-3.5 py-2 rounded-xl bg-greenfont text-white text-xs font-bold hover:opacity-95"
                      >
                        ✋ Raise Hand With {friend.full_name.split(" ")[0]}
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* TAB 2: FRIEND REQUESTS */}
          {activeTab === "requests" && (
            <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              {overview.incoming_requests.length === 0 &&
              overview.outgoing_requests.length === 0 ? (
                <div className="col-span-2 bg-white rounded-xl p-6 text-sm text-gray-500 border border-[#e3e8e5]">
                  No pending friend requests right now.
                </div>
              ) : (
                <>
                  {overview.incoming_requests.map((req) => (
                    <div
                      key={req.roll_number}
                      className="bg-white rounded-xl p-5 border border-[#e3e8e5] flex justify-between items-center gap-4"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-[#dcebe5] text-[#36594f] font-bold flex items-center justify-center text-sm">
                          {getInitials(req.full_name)}
                        </div>
                        <div>
                          <Link
                            to={`/profile/${req.roll_number}`}
                            className="font-bold text-greenfont hover:underline"
                          >
                            {req.full_name}
                          </Link>
                          <div className="text-xs text-gray-500">
                            {req.roll_number} • {req.branch}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            handleRespondRequest(req.roll_number, "ACCEPT")
                          }
                          className="px-3 py-1.5 rounded-lg bg-greenfont text-white text-xs font-bold"
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            handleRespondRequest(req.roll_number, "DECLINE")
                          }
                          className="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-xs font-bold"
                        >
                          Decline
                        </button>
                      </div>
                    </div>
                  ))}
                  {overview.outgoing_requests.map((req) => (
                    <div
                      key={req.roll_number}
                      className="bg-white rounded-xl p-5 border border-[#e3e8e5] flex justify-between items-center gap-4"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-roomgreen text-[#36594f] font-bold flex items-center justify-center text-sm">
                          {getInitials(req.full_name)}
                        </div>
                        <div>
                          <Link
                            to={`/profile/${req.roll_number}`}
                            className="font-bold text-greenfont hover:underline"
                          >
                            {req.full_name}
                          </Link>
                          <div className="text-xs text-gray-500">
                            {req.roll_number} • {req.branch}
                          </div>
                        </div>
                      </div>
                      <span className="px-3 py-1 rounded-lg bg-gray-100 text-gray-600 text-xs font-bold">
                        Outgoing Request Pending
                      </span>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}

          {/* TAB 3: ALL FRIENDS */}
          {activeTab === "all" && (
            <div className="mt-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {overview.friends.map((friend) => (
                <div
                  key={friend.roll_number}
                  className="bg-white rounded-xl p-5 border border-[#e3e8e5] flex flex-col justify-between gap-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#dcebe5] text-[#36594f] font-bold flex items-center justify-center text-sm">
                      {getInitials(friend.full_name)}
                    </div>
                    <div>
                      <Link
                        to={`/profile/${friend.roll_number}`}
                        className="font-bold text-greenfont hover:underline"
                      >
                        {friend.full_name}
                      </Link>
                      <div className="text-xs text-gray-500">
                        {friend.roll_number} • {friend.branch}
                      </div>
                      <div className="text-xs text-gray-400">
                        {friend.hostel}
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t border-[#eef2ef]">
                    <span className="text-xs text-gray-500">
                      {friend.active_hand
                        ? `✋ Studying at ${friend.active_hand.zone_name}`
                        : "Offline"}
                    </span>
                    <Link
                      to={`/profile/${friend.roll_number}`}
                      className="text-xs font-bold text-lightgreenfont hover:underline"
                    >
                      View Profile →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
